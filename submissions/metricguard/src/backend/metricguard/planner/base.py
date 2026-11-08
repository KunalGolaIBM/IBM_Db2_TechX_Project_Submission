"""Planner interface shared by the LangChain planner and the demo rule planner.

A planner maps a question to a `PlannerOutput`: a closed, typed structure that names
metrics, dimensions, filters, dates and sort order. It never contains SQL. Turning it
into a `QueryPlan`, validating it, compiling SQL and executing it is deterministic code
(`metricguard.analysis.pipeline`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExecutionMode = Literal["LLM", "DEMO_RULE_BASED"]
Provider = Literal["meta", "anthropic", "metricguard-rules"]

DEMO_DISCLOSURE = (
    "Demo mode: this plan was produced by a deterministic rule-based planner for the curated example "
    "questions, not by an LLM. SQL compilation, validation, execution and verification are unchanged."
)


class PlannedFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(description="Filter name from the registry, e.g. 'region'")
    values: list[str] = Field(description="Exact allowed value codes, e.g. ['EMEA']")


class PlannedSort(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str = Field(description="A metric name or dimension name that is part of this plan")
    direction: Literal["asc", "desc"]


class AmbiguousMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")
    term: str = Field(description="The exact word or phrase from the question that is ambiguous, e.g. 'revenue'")
    candidate_metrics: list[str] = Field(description="Approved metric names the term could mean")


class PlannerOutput(BaseModel):
    """Structured planner output. Every field is required so the JSON schema is closed."""

    model_config = ConfigDict(extra="forbid")

    intent: Literal["analysis", "ambiguous", "write_request", "out_of_scope"] = Field(
        description="analysis: answerable read-only question. ambiguous: needs clarification. "
        "write_request: asks to change, delete or create data. out_of_scope: anything else."
    )
    metrics: list[str] = Field(description="Metric names in the order the question mentions them")
    dimensions: list[str] = Field(description="Group-by dimension names (0-2)")
    filters: list[PlannedFilter]
    start_date: date | None = Field(description="Inclusive start date YYYY-MM-DD, or null if no period is named")
    end_date: date | None = Field(description="Inclusive end date YYYY-MM-DD, or null if no period is named")
    order_by: list[PlannedSort]
    limit: int | None = Field(description="Top-N row limit, or null")
    ambiguous_metric: AmbiguousMetric | None
    relative_time_phrase: str | None = Field(
        description="Relative period phrase copied from the question (e.g. 'last quarter'), or null"
    )


@dataclass
class PlannerResult:
    output: PlannerOutput
    name: str
    model: str | None
    execution_mode: ExecutionMode
    elapsed_ms: float
    provider: Provider | None = None
    notes: list[str] = field(default_factory=list)


class PlannerError(Exception):
    """Base class. Messages are safe to show and to audit (no keys, no raw provider payloads)."""

    code = "PLANNER_ERROR"


class PlannerOutputError(PlannerError):
    """The model answered, but not with a valid PlannerOutput (malformed, truncated, refused)."""

    code = "PLAN_SCHEMA_INVALID"


class PlannerUnavailableError(PlannerError):
    """The planner could not be reached or used (no key, auth, timeout, unknown model, 5xx)."""

    code = "PLANNER_UNAVAILABLE"


class Planner:
    name: str
    model: str | None
    execution_mode: ExecutionMode
    provider: Provider

    def plan(self, question: str) -> PlannerResult:  # pragma: no cover - interface
        raise NotImplementedError


def empty_output(intent: str) -> PlannerOutput:
    return PlannerOutput(
        intent=intent, metrics=[], dimensions=[], filters=[], start_date=None, end_date=None, order_by=[],
        limit=None, ambiguous_metric=None, relative_time_phrase=None,
    )
