"""Secure LangChain tools backed by IBM Db2.

Security model
--------------
* The LLM never writes SQL. Each tool maps to one fixed, parameterized query in
  :mod:`civiclens.db.repository`.
* Arguments are validated by Pydantic schemas with hard bounds (row limits, radius,
  time windows) *before* any database call.
* Phase 00 tools are read-only. Any future write tool may only create rows in a
  ``PROPOSED`` state; approval is a human action through the review API.
* Every invocation (success or failure) is appended to ``AUDIT_LOG`` with the
  investigation id, tool name, validated input and a short output summary.
* Results are truncated and returned as plain JSON-serialisable dicts.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import timedelta
from types import ModuleType
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from civiclens.db import repository as default_repository
from civiclens.domain.models import Category, ComplaintStatus

TOOL_NAMES = ("search_complaints", "get_complaint", "find_duplicate_candidates", "hotspot_summary")
MAX_TOOL_ROWS = 25
MAX_RADIUS_M = 2000
MAX_WINDOW_DAYS = 365


class SearchComplaintsArgs(BaseModel):
    category: Category | None = Field(default=None, description="Infrastructure category filter.")
    status: ComplaintStatus | None = Field(default=None, description="Complaint status filter.")
    ward: str | None = Field(default=None, max_length=64, description="Exact ward name.")
    geo_cell: str | None = Field(
        default=None, pattern=r"^C-?\d{1,6}_-?\d{1,6}$", description="Geo-cell id from hotspot_summary."
    )
    days: int = Field(default=30, ge=1, le=MAX_WINDOW_DAYS, description="Look-back window in days.")
    limit: int = Field(default=10, ge=1, le=MAX_TOOL_ROWS)


class GetComplaintArgs(BaseModel):
    complaint_id: int = Field(ge=1, description="Numeric complaint id.")


class DuplicateArgs(BaseModel):
    complaint_id: int = Field(ge=1, description="Complaint to find possible duplicates of.")
    radius_m: float = Field(default=250, gt=0, le=MAX_RADIUS_M)
    window_days: int = Field(default=14, ge=1, le=90)


class HotspotArgs(BaseModel):
    days: int = Field(default=30, ge=1, le=MAX_WINDOW_DAYS)
    category: Category | None = None
    min_count: int = Field(default=3, ge=2, le=1000)
    limit: int = Field(default=10, ge=1, le=MAX_TOOL_ROWS)


def _dump(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_dump(o) for o in obj]
    return obj


def summarise_result(result: Any) -> str:
    """One readable line for the audit log (never the full payload, which can include complaint text)."""
    if isinstance(result, list):
        return f"{len(result)} rows"
    if isinstance(result, dict):
        if result.get("found") is False:
            return f"complaint #{result.get('complaint_id')} not found"
        if isinstance(result.get("complaint_id"), int):
            return f"complaint #{result['complaint_id']} ({result.get('category')}) returned"
    return json.dumps(result, default=str)[:300]


class CivicLensToolkit:
    """Builds audited LangChain tools bound to one Db2 session and investigation."""

    def __init__(
        self,
        db: Any,
        *,
        investigation_id: int | None,
        actor_id: str = "civiclens-agent",
        repository: ModuleType | Any = default_repository,
    ) -> None:
        self.db = db
        self.investigation_id = investigation_id
        self.actor_id = actor_id
        self.repo = repository

    # -- auditing wrapper --------------------------------------------------------
    def _audited(self, name: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        def runner(**kwargs: Any) -> dict[str, Any]:
            try:
                result = _dump(fn(**kwargs))
            except Exception as exc:
                self.repo.write_audit(
                    self.db,
                    actor_type="AGENT",
                    actor_id=self.actor_id,
                    action="TOOL_CALL",
                    investigation_id=self.investigation_id,
                    tool_name=name,
                    input_payload=kwargs,
                    output_summary=f"error: {type(exc).__name__}",
                    success=False,
                )
                return {"ok": False, "error": f"{name} failed ({type(exc).__name__})."}
            summary = summarise_result(result)
            self.repo.write_audit(
                self.db,
                actor_type="AGENT",
                actor_id=self.actor_id,
                action="TOOL_CALL",
                investigation_id=self.investigation_id,
                tool_name=name,
                input_payload={k: (v.value if hasattr(v, "value") else v) for k, v in kwargs.items()},
                output_summary=summary,
            )
            return {"ok": True, "data": result}

        return runner

    # -- tool implementations ------------------------------------------------------
    def _search(self, category=None, status=None, ward=None, geo_cell=None, days=30, limit=10):
        return self.repo.list_complaints(
            self.db,
            category=category,
            status=status,
            ward=ward,
            geo_cell=geo_cell,
            since=self.repo.utcnow() - timedelta(days=days),
            limit=min(limit, MAX_TOOL_ROWS),
        )

    def _get(self, complaint_id: int):
        complaint = self.repo.get_complaint(self.db, complaint_id)
        if complaint is None:
            return {"found": False, "complaint_id": complaint_id}
        return complaint

    def _duplicates(self, complaint_id: int, radius_m: float = 250, window_days: int = 14):
        c = self.repo.get_complaint(self.db, complaint_id)
        if c is None:
            return {"found": False, "complaint_id": complaint_id}
        return self.repo.find_duplicate_candidates(
            self.db,
            category=c.category,
            title=c.title,
            description=c.description,
            latitude=c.latitude,
            longitude=c.longitude,
            reported_at=c.reported_at,
            radius_m=radius_m,
            window_days=window_days,
            exclude_id=c.complaint_id,
        )

    def _hotspots(self, days=30, category=None, min_count=3, limit=10):
        return self.repo.hotspots(
            self.db,
            since=self.repo.utcnow() - timedelta(days=days),
            category=category,
            min_count=min_count,
            limit=min(limit, MAX_TOOL_ROWS),
        )

    def tools(self) -> list[StructuredTool]:
        specs = [
            (
                "search_complaints",
                self._search,
                SearchComplaintsArgs,
                "List recent infrastructure complaints stored in IBM Db2, with optional filters.",
            ),
            ("get_complaint", self._get, GetComplaintArgs, "Fetch one complaint by numeric id from IBM Db2."),
            (
                "find_duplicate_candidates",
                self._duplicates,
                DuplicateArgs,
                "Find likely duplicate complaints near a given complaint "
                "(same category, distance, time window, text similarity).",
            ),
            (
                "hotspot_summary",
                self._hotspots,
                HotspotArgs,
                "Aggregate complaints by geographic cell and category over a time window to find hotspots.",
            ),
        ]
        return [
            StructuredTool.from_function(
                func=self._audited(name, fn),
                name=name,
                description=desc,
                args_schema=schema,
            )
            for name, fn, schema, desc in specs
        ]
