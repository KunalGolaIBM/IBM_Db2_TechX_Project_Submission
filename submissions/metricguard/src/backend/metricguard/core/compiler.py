"""Deterministic QueryPlan -> parameterized Db2 SQL compiler.

Design rules (see docs/ARCHITECTURE_DECISIONS.md, ADR-004):
* Every SQL fragment below is a reviewed constant. Identifiers come only from the
  registry whitelist; user/LLM-provided *values* travel exclusively as `?` parameters.
* Revenue is computed at order-line grain. Refunds are pre-aggregated per line in their
  own CTE before the join, so a line with N refund rows is still counted once
  (prevents the classic refund x items join fan-out).
* Order-level columns (e.g. SHIPPING_AMOUNT) are never aggregated after a line join.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal

from .plan import QueryPlan
from .registry import METRICS, BaseMeasure

SCHEMA = "METRICGUARD"

# Dimension name -> (SQL expression over line_facts alias f, output column alias)
_DIMENSION_SQL: dict[str, tuple[str, str]] = {
    "order_month": ("VARCHAR_FORMAT(f.ORDER_TS, 'YYYY-MM')", "ORDER_MONTH"),
    "region": ("f.REGION_CODE", "REGION"),
    "channel": ("f.CHANNEL_CODE", "CHANNEL"),
    "product_category": ("f.CATEGORY", "PRODUCT_CATEGORY"),
}

# Filter name -> (CTE it belongs to, column expression)
_FILTER_SQL: dict[str, tuple[Literal["orders", "lines"], str]] = {
    "region": ("orders", "o.REGION_CODE"),
    "channel": ("orders", "o.CHANNEL_CODE"),
    "product_category": ("lines", "p.CATEGORY"),
}

_REV = "COALESCE(SUM(f.LINE_REVENUE), 0)"
_REF = "COALESCE(SUM(f.LINE_REFUND), 0)"
_CNT = "COUNT(DISTINCT f.ORDER_ID)"

# Metric name -> SQL aggregate expression over line_facts alias f.
_METRIC_SQL: dict[str, str] = {
    "gross_revenue": f"CAST({_REV} AS DECIMAL(18,2))",
    "net_revenue": f"CAST({_REV} - {_REF} AS DECIMAL(18,2))",
    "order_count": f"{_CNT}",
    "average_order_value": (
        f"CAST(ROUND(CAST(SUM(f.LINE_REVENUE) AS DECIMAL(25,4)) / NULLIF({_CNT}, 0), 2) AS DECIMAL(18,2))"
    ),
    "refund_amount": f"CAST({_REF} AS DECIMAL(18,2))",
    "refund_rate": (
        f"CAST(ROUND(CAST({_REF} AS DECIMAL(25,4)) / NULLIF(SUM(f.LINE_REVENUE), 0), 6) AS DECIMAL(12,6))"
    ),
}

ELIGIBLE_REFUND_STATUS = "PROCESSED"


@dataclass(frozen=True)
class SqlParameter:
    position: int
    name: str
    db2_type: str
    value: Any

    def as_dict(self) -> dict[str, Any]:
        return {"position": self.position, "name": self.name, "db2_type": self.db2_type, "value": self.value}


@dataclass(frozen=True)
class OutputColumn:
    name: str  # lower-case API name (dimension or metric name)
    sql_alias: str
    role: Literal["dimension", "metric"]


@dataclass
class CompiledQuery:
    sql: str
    parameters: list[SqlParameter]
    columns: list[OutputColumn]
    fetch_limit: int
    tables: list[str] = field(default_factory=list)

    @property
    def param_values(self) -> tuple[Any, ...]:
        return tuple(p.value for p in self.parameters)


class CompileError(ValueError):
    pass


def _needs(plan: QueryPlan, measure: BaseMeasure) -> bool:
    return any(measure in METRICS[m.name].measures for m in plan.metrics)


def compile_plan(plan: QueryPlan, *, max_rows: int = 500) -> CompiledQuery:
    """Compile a *validated* plan. Raises CompileError for anything outside the whitelist."""
    for ref in plan.metrics:
        if ref.name not in _METRIC_SQL:
            raise CompileError(f"No compiler rule for metric '{ref.name}'")
    for dim in plan.dimensions:
        if dim not in _DIMENSION_SQL:
            raise CompileError(f"No compiler rule for dimension '{dim}'")

    params: list[SqlParameter] = []

    def bind(name: str, db2_type: str, value: Any) -> str:
        params.append(SqlParameter(len(params) + 1, name, db2_type, value))
        return f"CAST(? AS {db2_type})"

    # ---- eligible_orders CTE --------------------------------------------------------
    eligible_statuses = sorted({s for m in plan.metrics for s in METRICS[m.name].eligible_order_statuses})
    status_marks = ", ".join(bind(f"eligible_status_{i + 1}", "VARCHAR(16)", s) for i, s in enumerate(eligible_statuses))
    start_ts = f"{plan.date_range.start_date.isoformat()} 00:00:00"
    end_exclusive = plan.date_range.end_date + timedelta(days=1)
    end_ts = f"{end_exclusive.isoformat()} 00:00:00"
    order_where = [
        f"o.STATUS IN ({status_marks})",
        f"o.ORDER_TS >= {bind('date_start_inclusive', 'TIMESTAMP', start_ts)}",
        f"o.ORDER_TS < {bind('date_end_exclusive', 'TIMESTAMP', end_ts)}",
    ]
    line_where: list[str] = []
    line_filter_binds: list[tuple[str, list[str]]] = []
    for flt in plan.filters:
        scope, column = _FILTER_SQL[flt.field]
        if scope == "orders":
            marks = ", ".join(
                bind(f"filter_{flt.field}_{i + 1}", "VARCHAR(16)", v) for i, v in enumerate(flt.values)
            )
            order_where.append(f"{column} IN ({marks})")
        else:
            line_filter_binds.append((flt.field, flt.values))

    ctes = [
        "eligible_orders AS (\n"
        "    SELECT o.ORDER_ID, o.ORDER_TS, o.REGION_CODE, o.CHANNEL_CODE\n"
        f"    FROM {SCHEMA}.ORDERS o\n"
        "    WHERE " + "\n      AND ".join(order_where) + "\n)"
    ]

    need_refunds = _needs(plan, BaseMeasure.PROCESSED_REFUND_SUM)
    if need_refunds:
        refund_mark = bind("refund_status", "VARCHAR(12)", ELIGIBLE_REFUND_STATUS)
        ctes.append(
            "line_refunds AS (\n"
            "    -- Pre-aggregate refunds per order line BEFORE joining (no fan-out).\n"
            "    SELECT r.ORDER_ITEM_ID, SUM(r.REFUND_AMOUNT) AS REFUND_AMOUNT\n"
            f"    FROM {SCHEMA}.REFUNDS r\n"
            "    JOIN eligible_orders e ON e.ORDER_ID = r.ORDER_ID\n"
            f"    WHERE r.STATUS = {refund_mark}\n"
            "    GROUP BY r.ORDER_ITEM_ID\n"
            ")"
        )

    for fname, values in line_filter_binds:
        _, column = _FILTER_SQL[fname]
        marks = ", ".join(bind(f"filter_{fname}_{i + 1}", "VARCHAR(16)", v) for i, v in enumerate(values))
        line_where.append(f"{column} IN ({marks})")

    refund_col = "COALESCE(lr.REFUND_AMOUNT, 0)" if need_refunds else "CAST(0 AS DECIMAL(10,2))"
    refund_join = "    LEFT JOIN line_refunds lr ON lr.ORDER_ITEM_ID = i.ORDER_ITEM_ID\n" if need_refunds else ""
    ctes.append(
        "line_facts AS (\n"
        "    SELECT e.ORDER_ID, e.ORDER_TS, e.REGION_CODE, e.CHANNEL_CODE, p.CATEGORY,\n"
        "           (i.QUANTITY * i.UNIT_PRICE) - i.DISCOUNT_AMOUNT AS LINE_REVENUE,\n"
        f"           {refund_col} AS LINE_REFUND\n"
        "    FROM eligible_orders e\n"
        f"    JOIN {SCHEMA}.ORDER_ITEMS i ON i.ORDER_ID = e.ORDER_ID\n"
        f"    JOIN {SCHEMA}.PRODUCTS p ON p.PRODUCT_ID = i.PRODUCT_ID\n"
        + refund_join
        + ("    WHERE " + "\n      AND ".join(line_where) + "\n" if line_where else "")
        + ")"
    )

    # ---- final SELECT ---------------------------------------------------------------
    columns: list[OutputColumn] = []
    select_items: list[str] = []
    group_by: list[str] = []
    for dim in plan.dimensions:
        expr, alias = _DIMENSION_SQL[dim]
        select_items.append(f"{expr} AS {alias}")
        group_by.append(expr)
        columns.append(OutputColumn(dim, alias, "dimension"))
    for ref in plan.metrics:
        alias = ref.name.upper()
        select_items.append(f"{_METRIC_SQL[ref.name]} AS {alias}")
        columns.append(OutputColumn(ref.name, alias, "metric"))

    alias_of = {c.name: c.sql_alias for c in columns}
    order_items = [f"{alias_of[ob.field]} {ob.direction.upper()}" for ob in plan.order_by]
    for dim in plan.dimensions:  # deterministic tie-breaker
        if not any(ob.field == dim for ob in plan.order_by):
            order_items.append(f"{alias_of[dim]} ASC")

    fetch_limit = min(plan.limit, max_rows) if plan.limit else max_rows + 1

    sql = "WITH " + ",\n".join(ctes) + "\nSELECT " + ",\n       ".join(select_items) + "\nFROM line_facts f"
    if group_by:
        sql += "\nGROUP BY " + ", ".join(group_by)
    if order_items:
        sql += "\nORDER BY " + ", ".join(order_items)
    if plan.dimensions:
        sql += f"\nFETCH FIRST {int(fetch_limit)} ROWS ONLY"

    tables = [f"{SCHEMA}.ORDERS", f"{SCHEMA}.ORDER_ITEMS", f"{SCHEMA}.PRODUCTS"]
    if need_refunds:
        tables.append(f"{SCHEMA}.REFUNDS")
    return CompiledQuery(sql=sql, parameters=params, columns=columns, fetch_limit=fetch_limit, tables=tables)
