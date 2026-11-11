"""Plan validation against the approved registry. Any issue => BLOCKED (never executed)."""

from __future__ import annotations

from dataclasses import dataclass

from .plan import QueryPlan
from .registry import DIMENSIONS, FILTERS, METRICS


@dataclass(frozen=True)
class PlanIssue:
    code: str
    message: str


def validate_plan(plan: QueryPlan) -> list[PlanIssue]:
    issues: list[PlanIssue] = []

    seen: set[str] = set()
    for ref in plan.metrics:
        if ref.name in seen:
            issues.append(PlanIssue("DUPLICATE_METRIC", f"Metric '{ref.name}' requested twice."))
        seen.add(ref.name)
        metric = METRICS.get(ref.name)
        if metric is None:
            issues.append(PlanIssue("UNKNOWN_METRIC", f"'{ref.name}' is not an approved metric."))
            continue
        if metric.lifecycle_status != "APPROVED":
            issues.append(PlanIssue("METRIC_NOT_APPROVED", f"'{ref.name}' is {metric.lifecycle_status}."))
        if ref.version != metric.version:
            issues.append(
                PlanIssue(
                    "METRIC_VERSION_MISMATCH",
                    f"'{ref.name}' version {ref.version} requested; approved version is {metric.version}.",
                )
            )

    if len(set(plan.dimensions)) != len(plan.dimensions):
        issues.append(PlanIssue("DUPLICATE_DIMENSION", "A dimension is listed twice."))

    known_metrics = [METRICS[r.name] for r in plan.metrics if r.name in METRICS]
    for dim in plan.dimensions:
        if dim not in DIMENSIONS:
            issues.append(PlanIssue("UNKNOWN_DIMENSION", f"'{dim}' is not an approved dimension."))
            continue
        for m in known_metrics:
            if dim not in m.allowed_dimensions:
                issues.append(
                    PlanIssue(
                        "DIMENSION_NOT_ALLOWED",
                        f"'{m.name}' cannot be broken down by '{dim}' "
                        f"(allowed: {', '.join(m.allowed_dimensions)}).",
                    )
                )

    filter_fields: set[str] = set()
    for flt in plan.filters:
        if flt.field in filter_fields:
            issues.append(PlanIssue("DUPLICATE_FILTER", f"Filter on '{flt.field}' is listed twice."))
        filter_fields.add(flt.field)
        fdef = FILTERS.get(flt.field)
        if fdef is None:
            issues.append(PlanIssue("UNKNOWN_FILTER", f"'{flt.field}' is not an approved filter."))
            continue
        bad = [v for v in flt.values if v not in fdef.allowed_values]
        if bad:
            issues.append(
                PlanIssue(
                    "FILTER_VALUE_NOT_ALLOWED",
                    f"Values {bad} are not valid for '{flt.field}' (allowed: {', '.join(fdef.allowed_values)}).",
                )
            )
        for m in known_metrics:
            if flt.field not in m.allowed_filters:
                issues.append(
                    PlanIssue("FILTER_NOT_ALLOWED", f"'{m.name}' cannot be filtered by '{flt.field}'.")
                )

    sortable = set(plan.dimensions) | set(plan.metric_names)
    for ob in plan.order_by:
        if ob.field not in sortable:
            issues.append(
                PlanIssue("INVALID_ORDER_BY", f"Cannot sort by '{ob.field}'; it is not a metric or dimension in the plan.")
            )

    return issues
