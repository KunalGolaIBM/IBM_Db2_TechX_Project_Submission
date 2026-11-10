"""Response models for the dashboard: identity and the aggregated overview."""

from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel

from civiclens.domain.models import Category, ComplaintStatus, Hotspot


class MeResponse(BaseModel):
    user_id: str
    role: Literal["analyst", "reviewer"]
    capabilities: list[str]


class CategoryCount(BaseModel):
    category: Category
    count: int
    avg_severity: float
    synthetic: int


class StatusCount(BaseModel):
    status: ComplaintStatus
    count: int


class SeverityCount(BaseModel):
    severity: int
    count: int


class TrendPoint(BaseModel):
    date: dt.date
    count: int


class ComplaintStats(BaseModel):
    total: int
    synthetic: int
    real: int
    last_7d: int
    last_30d: int
    by_category: list[CategoryCount]
    by_status: list[StatusCount]
    by_severity: list[SeverityCount]
    trend_days: int
    trend: list[TrendPoint]


class InvestigationStats(BaseModel):
    total: int
    active: int  # OPEN + RUNNING + PENDING_REVIEW
    by_status: dict[str, int]


class RecommendationStats(BaseModel):
    total: int
    pending_review: int  # status PROPOSED
    by_status: dict[str, int]
    by_generator: dict[str, int]


class HotspotSummary(BaseModel):
    window_days: int
    min_count: int
    total: int  # all qualifying hotspots (counted up to MAX_HOTSPOT_LIMIT); `items` is only the top few
    items: list[Hotspot]


class AgentActivity(BaseModel):
    audit_id: int
    investigation_id: int | None
    action: str
    tool_name: str | None
    success: bool
    output_summary: str | None
    created_at: dt.datetime


class DatabaseInfo(BaseModel):
    status: Literal["ok"]
    product: str
    version: str
    database: str
    schema_name: str


class LlmInfo(BaseModel):
    configured: bool
    provider: str
    model: str | None
    problem: str | None


class AgentInfo(BaseModel):
    max_steps: int
    timeout_s: int
    tools: list[str]


class SystemInfo(BaseModel):
    environment: str
    database: DatabaseInfo
    llm: LlmInfo
    agent: AgentInfo


class Overview(BaseModel):
    generated_at: dt.datetime
    complaints: ComplaintStats
    investigations: InvestigationStats
    recommendations: RecommendationStats
    hotspots: HotspotSummary
    recent_agent_activity: list[AgentActivity]
    system: SystemInfo
