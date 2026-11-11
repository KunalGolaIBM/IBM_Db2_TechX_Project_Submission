"""Deterministic presentation: JSON numbers, labels, chart spec and template summaries.

Nothing here is written by the LLM. Every number in a summary or headline comes from the
Db2 result rows or from the Db2 control-total query.
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from metricguard.core.plan import QueryPlan
from metricguard.core.registry import DIMENSIONS, METRICS, Unit

_PLURAL = {"order_month": "months", "region": "regions", "channel": "sales channels",
           "product_category": "product categories"}
_SINGULAR = {"order_month": "month", "region": "region", "channel": "sales channel",
             "product_category": "product category"}


def to_json_number(value: Any, metric: str) -> float | int | None:
    if value is None:
        return None
    m = METRICS[metric]
    if m.unit == Unit.COUNT:
        return int(value)
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    return float(d.quantize(Decimal(1).scaleb(-m.scale), rounding=ROUND_HALF_UP))


def fmt(value: Any, metric: str) -> str:
    if value is None:
        return "n/a"
    m = METRICS[metric]
    if m.unit == Unit.USD:
        return f"${Decimal(str(value)):,.2f}"
    if m.unit == Unit.COUNT:
        return f"{int(value):,}"
    return f"{Decimal(str(value)) * 100:.2f}%"


def period_label(start: date, end: date) -> str:
    def month_end(d: date) -> bool:
        return d.day == calendar.monthrange(d.year, d.month)[1]

    if start.day == 1 and month_end(end) and start.year == end.year:
        months = end.month - start.month + 1
        if months == 1:
            return f"{calendar.month_name[start.month]} {start.year}"
        if months == 3 and start.month in (1, 4, 7, 10):
            return f"Q{(start.month + 2) // 3} {start.year}"
        if months == 6 and start.month in (1, 7):
            return f"H{1 if start.month == 1 else 2} {start.year}"
        if months == 12:
            return f"FY {start.year}"
        return f"{calendar.month_abbr[start.month]}–{calendar.month_abbr[end.month]} {start.year}"
    if start == end:
        return start.isoformat()
    return f"{start.isoformat()} to {end.isoformat()}"


def scope_label(plan: QueryPlan) -> str:
    parts = [period_label(plan.date_range.start_date, plan.date_range.end_date)]
    for f in plan.filters:
        parts.append(" + ".join(f.values))
    return ", ".join(parts)


def result_columns(plan: QueryPlan) -> list[dict[str, Any]]:
    cols: list[dict[str, Any]] = []
    for d in plan.dimensions:
        cols.append({"name": d, "label": DIMENSIONS[d].display_name, "role": "dimension", "data_type": "string",
                     "unit": None, "scale": None})
    for ref in plan.metrics:
        m = METRICS[ref.name]
        cols.append({"name": m.name, "label": m.display_name, "role": "metric",
                     "data_type": "integer" if m.unit == Unit.COUNT else "decimal", "unit": m.unit.value,
                     "scale": m.scale})
    return cols


def chart_spec(plan: QueryPlan, rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = METRICS[plan.metrics[0].name]
    same_unit = [METRICS[r.name] for r in plan.metrics if METRICS[r.name].unit == first.unit]
    dims = plan.dimensions
    if not dims:
        return {
            "type": "kpi", "title": f"{first.display_name} · {scope_label(plan)}", "x": None,
            "series": [{"key": m.name, "label": m.display_name, "metric": m.name, "unit": m.unit.value,
                        "points": [{"x": None, "y": rows[0].get(m.name) if rows else None}]} for m in same_unit],
        }
    x = dims[0]
    axis = {"field": x, "label": DIMENSIONS[x].display_name}
    title = f"{first.display_name} by {DIMENSIONS[x].display_name}"
    if len(dims) == 1:
        return {
            "type": "line" if x == "order_month" else "bar", "title": title, "x": axis,
            "series": [{"key": m.name, "label": m.display_name, "metric": m.name, "unit": m.unit.value,
                        "points": [{"x": str(r[x]), "y": r.get(m.name)} for r in rows]} for m in same_unit],
        }
    second = dims[1]
    values: list[str] = []
    for r in rows:
        if r[second] not in values:
            values.append(r[second])
    return {
        "type": "line" if x == "order_month" else "grouped_bar",
        "title": f"{title} and {DIMENSIONS[second].display_name}", "x": axis,
        "series": [{"key": f"{first.name}:{v}", "label": f"{first.display_name} · {v}", "metric": first.name,
                    "unit": first.unit.value,
                    "points": [{"x": str(r[x]), "y": r.get(first.name)} for r in rows if r[second] == v]}
                   for v in values],
    }


def _ranked_key(plan: QueryPlan) -> str | None:
    """The metric a top-N / bottom-N plan ranks by, or None if the plan is not a metric ranking."""
    if plan.dimensions and plan.limit and plan.order_by and plan.order_by[0].field in METRICS:
        return plan.order_by[0].field
    return None


def headline(plan: QueryPlan, rows: list[dict[str, Any]], totals: dict[str, Any] | None) -> dict[str, Any] | None:
    m = METRICS[plan.metrics[0].name]
    if (key := _ranked_key(plan)) is not None:
        # "Which region had the highest ...": the answer is the first-ranked row, not the all-groups control total.
        if not rows:
            return None
        km = METRICS[key]
        group = " / ".join(str(rows[0][d]) for d in plan.dimensions)
        word = "Top" if plan.order_by[0].direction == "desc" else "Bottom"
        noun = _SINGULAR[plan.dimensions[0]] if len(plan.dimensions) == 1 else "group"
        value = rows[0].get(key)
        return {"metric": km.name, "label": f"{word} {noun}: {group} · {km.display_name} ({scope_label(plan)})",
                "value": to_json_number(value, km.name), "unit": km.unit.value, "formatted": fmt(value, km.name)}
    if not plan.dimensions:
        value = rows[0].get(m.name) if rows else None
    elif totals is not None and m.name in totals:
        value = totals[m.name]
    else:
        return None
    return {"metric": m.name, "label": f"{m.display_name} ({scope_label(plan)})",
            "value": to_json_number(value, m.name), "unit": m.unit.value, "formatted": fmt(value, m.name)}


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def summary(plan: QueryPlan, rows: list[dict[str, Any]], totals: dict[str, Any] | None, *, truncated: bool) -> str:
    """Template summary. Values are the raw Db2 values (Decimal/int) formatted deterministically."""
    scope = scope_label(plan)
    metrics = [METRICS[r.name] for r in plan.metrics]
    first = metrics[0]
    if not rows:
        return f"No completed orders match {scope}; there is nothing to report."
    if not plan.dimensions:
        parts = [f"{m.display_name} was {fmt(rows[0].get(m.name), m.name)}" for m in metrics]
        return f"For {scope}: " + "; ".join(parts) + "."
    dim = plan.dimensions[0]
    if len(plan.dimensions) == 1:
        label = (_SINGULAR if len(rows) == 1 else _PLURAL)[dim]
    else:
        label = "group" if len(rows) == 1 else "groups"
    if plan.limit and plan.order_by:
        ob = plan.order_by[0]
        key = ob.field if ob.field in METRICS else first.name
        word = "top" if ob.direction == "desc" else "bottom"
        listed = [f"{' / '.join(str(r[d]) for d in plan.dimensions)} ({fmt(r.get(key), key)})" for r in rows]
        if len(rows) == 1:
            return f"The {word} {label} by {METRICS[key].display_name} for {scope} is {listed[0]}."
        return f"The {word} {len(rows)} {label} by {METRICS[key].display_name} for {scope} are {_join(listed)}."
    ranked = [r for r in rows if r.get(first.name) is not None]
    best = max(ranked, key=lambda r: r[first.name]) if ranked else None
    groups = f"{len(rows)} {label}" + (" (truncated)" if truncated else "")
    if totals is not None and first.name in totals and first.additive:
        lead = f"{first.display_name} for {scope} totals {fmt(totals[first.name], first.name)} across {groups}"
    elif totals is not None and first.name in totals:
        lead = f"{first.display_name} for {scope} is {fmt(totals[first.name], first.name)} overall across {groups}"
    else:
        lead = f"{first.display_name} for {scope} is shown for {groups}"
    if best is not None and len(plan.dimensions) == 1:
        lead += f"; the highest is {best[dim]} at {fmt(best[first.name], first.name)}"
    return lead + "."
