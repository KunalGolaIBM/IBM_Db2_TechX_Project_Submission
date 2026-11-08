"""Curated example questions with their reference plans and expected governance outcome.

Served by GET /api/examples, used by `metricguard db verify` (executable ones are compared
with the independent oracle), and used in Stage 2 as the planner evaluation set.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

from .plan import DateRange, FilterClause, MetricRef, OrderBy, QueryPlan
from .registry import METRICS

Status = Literal["VERIFIED", "EXECUTED_WITH_WARNINGS", "AMBIGUOUS", "BLOCKED", "EXECUTION_FAILED"]


class Example(BaseModel):
    id: str
    question: str
    category: Literal["trend", "comparison", "ranking", "kpi", "governance"]
    description: str
    expected_status: Status
    reference_plan: QueryPlan | None = None
    reason_code: str | None = None


def _m(*names: str) -> list[MetricRef]:
    return [MetricRef(name=n, version=METRICS[n].version) for n in names]


def _range(start: date, end: date) -> DateRange:
    return DateRange(start_date=start, end_date=end)


H1 = (date(2026, 1, 1), date(2026, 6, 30))
Q1 = (date(2026, 1, 1), date(2026, 3, 31))
Q2 = (date(2026, 4, 1), date(2026, 6, 30))

EXAMPLES: list[Example] = [
    Example(
        id="ex-01-net-revenue-trend",
        question="What was net revenue by month in the first half of 2026?",
        category="trend",
        description="Monthly net revenue; refunds attributed to the order month.",
        expected_status="VERIFIED",
        reference_plan=QueryPlan(metrics=_m("net_revenue"), dimensions=["order_month"], date_range=_range(*H1)),
    ),
    Example(
        id="ex-02-region-refunds-q1",
        question="Compare gross revenue, refund amount and refund rate by region for Q1 2026.",
        category="comparison",
        description="Refund-heavy comparison that a naive refunds x items join double counts.",
        expected_status="VERIFIED",
        reference_plan=QueryPlan(
            metrics=_m("gross_revenue", "refund_amount", "refund_rate"),
            dimensions=["region"],
            date_range=_range(*Q1),
        ),
    ),
    Example(
        id="ex-03-aov-by-channel-q2",
        question="What was the average order value and order count by sales channel in Q2 2026?",
        category="comparison",
        description="Order-grain metrics; cancelled and pending orders excluded.",
        expected_status="VERIFIED",
        reference_plan=QueryPlan(
            metrics=_m("average_order_value", "order_count"), dimensions=["channel"], date_range=_range(*Q2)
        ),
    ),
    Example(
        id="ex-04-category-refund-rate",
        question="Which product categories had the highest refund rate in H1 2026?",
        category="ranking",
        description="Line-grain refund attribution to product category, ranked.",
        expected_status="VERIFIED",
        reference_plan=QueryPlan(
            metrics=_m("refund_rate", "refund_amount", "gross_revenue"),
            dimensions=["product_category"],
            date_range=_range(*H1),
            order_by=[OrderBy(field="refund_rate", direction="desc")],
        ),
    ),
    Example(
        id="ex-05-emea-monthly-q1",
        question="Show net revenue and order count by month for EMEA in Q1 2026.",
        category="trend",
        description="Region filter plus the Jan-31 23:59:59 / Feb-01 00:00:00 boundary canaries.",
        expected_status="VERIFIED",
        reference_plan=QueryPlan(
            metrics=_m("net_revenue", "order_count"),
            dimensions=["order_month"],
            filters=[FilterClause(field="region", values=["EMEA"])],
            date_range=_range(*Q1),
        ),
    ),
    Example(
        id="ex-06-march-kpis",
        question="How many orders did we complete in March 2026, and what was the AOV?",
        category="kpi",
        description="Single-row KPI; the 100%-discounted canary order counts as an order.",
        expected_status="VERIFIED",
        reference_plan=QueryPlan(
            metrics=_m("order_count", "average_order_value", "gross_revenue"),
            date_range=_range(date(2026, 3, 1), date(2026, 3, 31)),
        ),
    ),
    Example(
        id="ex-07-top-web-categories-q2",
        question="What were the top 3 product categories by net revenue on the web channel in Q2 2026?",
        category="ranking",
        description="Top-N with a channel filter.",
        expected_status="VERIFIED",
        reference_plan=QueryPlan(
            metrics=_m("net_revenue"),
            dimensions=["product_category"],
            filters=[FilterClause(field="channel", values=["WEB"])],
            date_range=_range(*Q2),
            order_by=[OrderBy(field="net_revenue", direction="desc")],
            limit=3,
        ),
    ),
    Example(
        id="ex-08-ambiguous-revenue",
        question="What was our revenue last quarter?",
        category="governance",
        description="'Revenue' maps to two approved metrics (gross vs net) and 'last quarter' is relative.",
        expected_status="AMBIGUOUS",
        reason_code="AMBIGUOUS_METRIC",
    ),
    Example(
        id="ex-09-blocked-aov-by-category",
        question="What is the average order value by product category?",
        category="governance",
        description="An order cannot be split across categories, so AOV by category is not an approved breakdown.",
        expected_status="BLOCKED",
        reason_code="DIMENSION_NOT_ALLOWED",
    ),
    Example(
        id="ex-10-blocked-write",
        question="Delete all refunds from March and show the new net revenue.",
        category="governance",
        description="Write intent is never executed.",
        expected_status="BLOCKED",
        reason_code="WRITE_INTENT",
    ),
]
