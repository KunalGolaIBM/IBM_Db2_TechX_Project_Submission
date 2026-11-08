"""Independent reference implementation of the metric semantics.

Computes expected answers directly from the generated Python objects with plain loops,
sharing NO code with the SQL compiler. Agreement between this oracle and Db2 results is
the evidence that the compiled SQL implements the documented semantics.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from .generator import Dataset

ELIGIBLE_ORDER_STATUS = "COMPLETED"
COUNTED_REFUND_STATUS = "PROCESSED"


def _round(value: Decimal, places: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def compute(
    ds: Dataset,
    *,
    metrics: list[str],
    dimensions: list[str],
    start: date,
    end: date,
    filters: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """Return rows {dimension..., metric...} sorted by dimension values."""
    filters = filters or {}
    category_of = {p.product_id: p.category for p in ds.products}
    refunds_by_line: dict[int, Decimal] = defaultdict(Decimal)
    for r in ds.refunds:
        if r.status == COUNTED_REFUND_STATUS:
            refunds_by_line[r.order_item_id] += r.refund_amount
    items_by_order: dict[int, list] = defaultdict(list)
    for it in ds.items:
        items_by_order[it.order_id].append(it)

    revenue: dict[tuple, Decimal] = defaultdict(Decimal)
    refunded: dict[tuple, Decimal] = defaultdict(Decimal)
    orders: dict[tuple, set[int]] = defaultdict(set)
    for o in ds.orders:
        if o.status != ELIGIBLE_ORDER_STATUS:
            continue
        if not (start <= o.order_ts.date() <= end):
            continue
        if "region" in filters and o.region_code not in filters["region"]:
            continue
        if "channel" in filters and o.channel_code not in filters["channel"]:
            continue
        for it in items_by_order[o.order_id]:
            category = category_of[it.product_id]
            if "product_category" in filters and category not in filters["product_category"]:
                continue
            values = {
                "order_month": o.order_ts.strftime("%Y-%m"),
                "region": o.region_code,
                "channel": o.channel_code,
                "product_category": category,
            }
            key = tuple(values[d] for d in dimensions)
            revenue[key] += it.quantity * it.unit_price - it.discount_amount
            refunded[key] += refunds_by_line.get(it.order_item_id, Decimal("0"))
            orders[key].add(o.order_id)

    keys = sorted(revenue) if dimensions else [()]
    rows: list[dict[str, Any]] = []
    for key in keys:
        gross = revenue.get(key, Decimal("0"))
        ref = refunded.get(key, Decimal("0"))
        count = len(orders.get(key, set()))
        row: dict[str, Any] = dict(zip(dimensions, key))
        for m in metrics:
            if m == "gross_revenue":
                row[m] = _round(gross, 2)
            elif m == "net_revenue":
                row[m] = _round(gross - ref, 2)
            elif m == "refund_amount":
                row[m] = _round(ref, 2)
            elif m == "order_count":
                row[m] = count
            elif m == "average_order_value":
                row[m] = _round(gross / count, 2) if count else None
            elif m == "refund_rate":
                row[m] = _round(ref / gross, 6) if gross else None
            else:
                raise KeyError(m)
        rows.append(row)
    return rows
