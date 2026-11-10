"""Dashboard endpoints: caller identity and the aggregated, Db2-computed overview."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends

from civiclens.agent.llm import llm_status
from civiclens.agent.tools import TOOL_NAMES
from civiclens.api.deps import get_db
from civiclens.auth import AnyUser, Principal, capabilities_for
from civiclens.config import get_settings
from civiclens.db import overview_repo
from civiclens.db import repository as repo
from civiclens.db.connection import Db2Session
from civiclens.domain.overview_models import (
    AgentInfo,
    DatabaseInfo,
    HotspotSummary,
    LlmInfo,
    MeResponse,
    Overview,
    SystemInfo,
)

router = APIRouter(prefix="/api", tags=["dashboard"])
User = Annotated[Principal, AnyUser]
DB = Annotated[Db2Session, Depends(get_db)]

HOTSPOT_WINDOW_DAYS = 30
HOTSPOT_MIN_COUNT = 3
HOTSPOT_LIMIT = 5


@router.get("/me", response_model=MeResponse)
def me(user: User) -> MeResponse:
    """Who the bearer token belongs to and what the UI may offer. Needs no database."""
    return MeResponse(user_id=user.user_id, role=user.role, capabilities=list(capabilities_for(user.role)))


@router.get("/overview", response_model=Overview)
def overview(user: User, db: DB) -> Overview:
    """Every figure on the Intelligence Overview, computed by IBM Db2 at request time."""
    settings = get_settings()
    now = repo.utcnow()
    info = db.server_info()
    hotspots = repo.hotspots(
        db,
        since=now - timedelta(days=HOTSPOT_WINDOW_DAYS),
        until=now,
        min_count=HOTSPOT_MIN_COUNT,
        limit=repo.MAX_HOTSPOT_LIMIT,
    )
    return Overview(
        generated_at=now,
        complaints=overview_repo.complaint_stats(db, now),
        investigations=overview_repo.investigation_stats(db),
        recommendations=overview_repo.recommendation_stats(db),
        hotspots=HotspotSummary(
            window_days=HOTSPOT_WINDOW_DAYS,
            min_count=HOTSPOT_MIN_COUNT,
            total=len(hotspots),
            items=hotspots[:HOTSPOT_LIMIT],
        ),
        recent_agent_activity=overview_repo.recent_agent_activity(db),
        system=SystemInfo(
            environment=settings.app_env,
            database=DatabaseInfo(
                status="ok",
                product=info["dbms_name"],
                version=info["dbms_ver"],
                database=info["db_name"],
                schema_name=db.schema,
            ),
            llm=LlmInfo(**llm_status(settings)),
            agent=AgentInfo(
                max_steps=settings.agent_max_steps,
                timeout_s=settings.agent_timeout_s,
                tools=list(TOOL_NAMES),
            ),
        ),
    )
