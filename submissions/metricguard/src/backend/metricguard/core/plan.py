"""Structured query plan: the only thing an LLM planner is allowed to produce.

The planner (Stage 2, LangChain) maps a question to a QueryPlan. Everything after that
(validation, SQL generation, execution, verification) is deterministic code.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .registry import DATA_COVERAGE_END, DATA_COVERAGE_START


class MetricRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = Field(examples=["net_revenue"])
    version: str = Field(examples=["1.0.0"])


class DateRange(BaseModel):
    start_date: date = Field(description="Inclusive, UTC calendar date")
    end_date: date = Field(description="Inclusive, UTC calendar date")
    attribution: Literal["order_date"] = "order_date"
    source: Literal["explicit", "default"] = Field(
        "explicit", description="'default' means the question named no period and the registry default was used"
    )

    @model_validator(mode="after")
    def _ordered(self) -> "DateRange":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self

    @classmethod
    def default(cls) -> "DateRange":
        return cls(start_date=DATA_COVERAGE_START, end_date=DATA_COVERAGE_END, source="default")


class FilterClause(BaseModel):
    field: str = Field(examples=["region"])
    operator: Literal["in"] = "in"
    values: list[str] = Field(min_length=1, max_length=20, examples=[["EMEA"]])


class OrderBy(BaseModel):
    field: str = Field(description="A metric name or a dimension name in this plan")
    direction: Literal["asc", "desc"] = "asc"


class QueryPlan(BaseModel):
    metrics: list[MetricRef] = Field(min_length=1, max_length=4)
    dimensions: list[str] = Field(default_factory=list, max_length=2)
    filters: list[FilterClause] = Field(default_factory=list, max_length=5)
    date_range: DateRange
    order_by: list[OrderBy] = Field(default_factory=list, max_length=3)
    limit: int | None = Field(None, ge=1, le=1000, description="Top-N limit; null = no explicit limit")

    @property
    def metric_names(self) -> list[str]:
        return [m.name for m in self.metrics]
