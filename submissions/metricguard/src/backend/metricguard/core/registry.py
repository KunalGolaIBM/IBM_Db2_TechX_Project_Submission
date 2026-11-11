"""Approved metric registry (declarative semantics, version-controlled).

This module is the single source of truth for metric meaning. It is serialized into
METRICGUARD.METRIC_DEFINITIONS by `metricguard db init`, together with a SHA-256 hash
of each canonical definition. It contains NO executable SQL: SQL fragments live in
`compiler.py`, keyed by the closed set of base measures below.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Data coverage of the seeded dataset (used as the documented default range) ---
DATA_COVERAGE_START = date(2026, 1, 1)
DATA_COVERAGE_END = date(2026, 6, 30)  # inclusive


class Unit(str, Enum):
    USD = "USD"
    COUNT = "COUNT"
    RATIO = "RATIO"


class BaseMeasure(str, Enum):
    """Closed set of physical aggregations the compiler knows how to emit."""

    LINE_REVENUE_SUM = "line_revenue_sum"
    PROCESSED_REFUND_SUM = "processed_refund_sum"
    DISTINCT_ORDER_COUNT = "distinct_order_count"


class DimensionDef(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    display_name: str
    description: str
    data_type: Literal["string"] = "string"
    grain: Literal["order", "line"]
    allowed_values: list[str] | None = None


class FilterDef(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    display_name: str
    operators: list[Literal["in"]] = ["in"]
    allowed_values: list[str]
    grain: Literal["order", "line"]


class MetricDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    display_name: str
    description: str = Field(description="Business meaning")
    calculation: str = Field(description="Human-readable calculation (not executable)")
    unit: Unit
    scale: int = Field(description="Decimal places returned by the API")
    kind: Literal["BASE", "DERIVED"]
    additive: bool = Field(description="Values can be summed across dimension groups")
    measures: list[BaseMeasure]
    formula: str = Field(description="Combination of base measures, e.g. 'a - b'")
    eligible_order_statuses: list[str]
    date_attribution: str
    null_handling: str
    refund_treatment: str
    discount_treatment: str
    allowed_dimensions: list[str]
    allowed_filters: list[str]
    synonyms: list[str] = Field(default_factory=list)
    owner: str = "finance-analytics"
    lifecycle_status: Literal["APPROVED", "DRAFT", "DEPRECATED"] = "APPROVED"

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def definition_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    @property
    def ref(self) -> str:
        return f"{self.name}@{self.version}"


# --------------------------------------------------------------------------------------
# Dimensions & filters
# --------------------------------------------------------------------------------------
REGIONS = ["NA", "EMEA", "APAC", "LATAM"]
CHANNELS = ["WEB", "MOBILE", "STORE", "MARKETPLACE"]
CATEGORIES = ["ELECTRONICS", "HOME", "APPAREL", "BEAUTY", "SPORTS"]
ORDER_STATUSES = ["COMPLETED", "CANCELLED", "PENDING"]
REFUND_STATUSES = ["PROCESSED", "PENDING", "REJECTED"]

DIMENSIONS: dict[str, DimensionDef] = {
    d.name: d
    for d in [
        DimensionDef(
            name="order_month",
            display_name="Order month",
            description="Calendar month (UTC) of ORDERS.ORDER_TS, formatted YYYY-MM.",
            grain="order",
        ),
        DimensionDef(
            name="region",
            display_name="Region",
            description="Sales region of the order (ORDERS.REGION_CODE).",
            grain="order",
            allowed_values=REGIONS,
        ),
        DimensionDef(
            name="channel",
            display_name="Sales channel",
            description="Channel the order was placed through (ORDERS.CHANNEL_CODE).",
            grain="order",
            allowed_values=CHANNELS,
        ),
        DimensionDef(
            name="product_category",
            display_name="Product category",
            description="Category of the product on the order line (PRODUCTS.CATEGORY).",
            grain="line",
            allowed_values=CATEGORIES,
        ),
    ]
}

FILTERS: dict[str, FilterDef] = {
    f.name: f
    for f in [
        FilterDef(name="region", display_name="Region", allowed_values=REGIONS, grain="order"),
        FilterDef(name="channel", display_name="Sales channel", allowed_values=CHANNELS, grain="order"),
        FilterDef(
            name="product_category", display_name="Product category", allowed_values=CATEGORIES, grain="line"
        ),
    ]
}

# --------------------------------------------------------------------------------------
# Shared semantic rules (quoted verbatim in docs/METRIC_SEMANTICS.md)
# --------------------------------------------------------------------------------------
_ELIGIBLE = ["COMPLETED"]
_ORDER_DATE = (
    "Attributed to the UTC order timestamp ORDERS.ORDER_TS. Date ranges are inclusive calendar "
    "dates [start_date, end_date], executed as ORDER_TS >= start 00:00:00 AND ORDER_TS < (end_date + 1 day)."
)
_REFUND_BY_ORDER_DATE = (
    "Refunds are attributed to the order date of the refunded order (cohort basis), not to REFUND_TS. "
    "Only REFUNDS.STATUS = 'PROCESSED' counts; PENDING and REJECTED refunds are excluded. Refunds on "
    "non-eligible (CANCELLED/PENDING) orders are excluded because those orders never produced revenue."
)
_DISCOUNT = (
    "Line discounts (ORDER_ITEMS.DISCOUNT_AMOUNT, a line total) are subtracted: line revenue = "
    "QUANTITY * UNIT_PRICE - DISCOUNT_AMOUNT. Shipping (ORDERS.SHIPPING_AMOUNT) and taxes are excluded."
)
_LINE_DIMS = ["order_month", "region", "channel", "product_category"]
_ORDER_DIMS = ["order_month", "region", "channel"]
_LINE_FILTERS = ["region", "channel", "product_category"]
_ORDER_FILTERS = ["region", "channel"]

METRICS: dict[str, MetricDefinition] = {
    m.name: m
    for m in [
        MetricDefinition(
            name="gross_revenue",
            version="1.0.0",
            display_name="Gross Revenue",
            description="Merchandise revenue charged to customers on completed orders, after line "
            "discounts and before refunds.",
            calculation="SUM over order lines of eligible orders of (QUANTITY * UNIT_PRICE - DISCOUNT_AMOUNT).",
            unit=Unit.USD,
            scale=2,
            kind="BASE",
            additive=True,
            measures=[BaseMeasure.LINE_REVENUE_SUM],
            formula="line_revenue_sum",
            eligible_order_statuses=_ELIGIBLE,
            date_attribution=_ORDER_DATE,
            null_handling="All inputs are NOT NULL. An empty result set yields 0.00 (COALESCE), never NULL.",
            refund_treatment="Not reduced by refunds (see net_revenue).",
            discount_treatment=_DISCOUNT,
            allowed_dimensions=_LINE_DIMS,
            allowed_filters=_LINE_FILTERS,
            synonyms=["gross sales", "bookings", "sales before refunds"],
        ),
        MetricDefinition(
            name="net_revenue",
            version="1.0.0",
            display_name="Net Revenue",
            description="Gross revenue minus processed refunds on the same completed orders.",
            calculation="gross_revenue - refund_amount, both computed at order-line grain for the same "
            "eligible orders.",
            unit=Unit.USD,
            scale=2,
            kind="DERIVED",
            additive=True,
            measures=[BaseMeasure.LINE_REVENUE_SUM, BaseMeasure.PROCESSED_REFUND_SUM],
            formula="line_revenue_sum - processed_refund_sum",
            eligible_order_statuses=_ELIGIBLE,
            date_attribution=_ORDER_DATE + " Refunds follow the order date (cohort basis).",
            null_handling="Lines without refunds contribute 0 refund (COALESCE). Empty result yields 0.00.",
            refund_treatment=_REFUND_BY_ORDER_DATE,
            discount_treatment=_DISCOUNT,
            allowed_dimensions=_LINE_DIMS,
            allowed_filters=_LINE_FILTERS,
            synonyms=["revenue after refunds", "net sales"],
        ),
        MetricDefinition(
            name="order_count",
            version="1.0.0",
            display_name="Order Count",
            description="Number of distinct completed orders.",
            calculation="COUNT(DISTINCT ORDER_ID) of eligible orders.",
            unit=Unit.COUNT,
            scale=0,
            kind="BASE",
            additive=True,
            measures=[BaseMeasure.DISTINCT_ORDER_COUNT],
            formula="distinct_order_count",
            eligible_order_statuses=_ELIGIBLE,
            date_attribution=_ORDER_DATE,
            null_handling="Empty result yields 0. Orders fully refunded are still counted (they were completed).",
            refund_treatment="Refunds do not remove an order from the count.",
            discount_treatment="Orders with 100% discounted lines (zero revenue) are still counted.",
            allowed_dimensions=_ORDER_DIMS,
            allowed_filters=_ORDER_FILTERS,
            synonyms=["orders", "number of orders", "transactions"],
        ),
        MetricDefinition(
            name="average_order_value",
            version="1.0.0",
            display_name="Average Order Value",
            description="Average gross revenue per completed order.",
            calculation="gross_revenue / order_count, rounded half-up to 2 decimals.",
            unit=Unit.USD,
            scale=2,
            kind="DERIVED",
            additive=False,
            measures=[BaseMeasure.LINE_REVENUE_SUM, BaseMeasure.DISTINCT_ORDER_COUNT],
            formula="line_revenue_sum / distinct_order_count",
            eligible_order_statuses=_ELIGIBLE,
            date_attribution=_ORDER_DATE,
            null_handling="NULL (not 0) when order_count = 0 (NULLIF on the denominator).",
            refund_treatment="Uses gross revenue; refunds are not subtracted.",
            discount_treatment=_DISCOUNT,
            allowed_dimensions=_ORDER_DIMS,
            allowed_filters=_ORDER_FILTERS,
            synonyms=["aov", "average basket", "average order size"],
        ),
        MetricDefinition(
            name="refund_amount",
            version="1.0.0",
            display_name="Refund Amount",
            description="Money returned to customers via processed refunds on completed orders.",
            calculation="SUM(REFUND_AMOUNT) of PROCESSED refunds whose order is eligible, pre-aggregated per "
            "order line before joining to lines (prevents join fan-out).",
            unit=Unit.USD,
            scale=2,
            kind="BASE",
            additive=True,
            measures=[BaseMeasure.PROCESSED_REFUND_SUM],
            formula="processed_refund_sum",
            eligible_order_statuses=_ELIGIBLE,
            date_attribution=_ORDER_DATE + " Refunds follow the order date (cohort basis), not REFUND_TS.",
            null_handling="Lines without refunds contribute 0. Empty result yields 0.00.",
            refund_treatment=_REFUND_BY_ORDER_DATE,
            discount_treatment="Refund amounts are recorded net of discounts; capped at the line revenue.",
            allowed_dimensions=_LINE_DIMS,
            allowed_filters=_LINE_FILTERS,
            synonyms=["refunds", "returns value", "refunded amount"],
        ),
        MetricDefinition(
            name="refund_rate",
            version="1.0.0",
            display_name="Refund Rate",
            description="Share of gross revenue that was refunded (value-based, not order-based).",
            calculation="refund_amount / gross_revenue, rounded half-up to 6 decimals (ratio, 0.0123 = 1.23%).",
            unit=Unit.RATIO,
            scale=6,
            kind="DERIVED",
            additive=False,
            measures=[BaseMeasure.PROCESSED_REFUND_SUM, BaseMeasure.LINE_REVENUE_SUM],
            formula="processed_refund_sum / line_revenue_sum",
            eligible_order_statuses=_ELIGIBLE,
            date_attribution=_ORDER_DATE + " Numerator and denominator use the same order cohort.",
            null_handling="NULL when gross_revenue = 0 (NULLIF on the denominator).",
            refund_treatment=_REFUND_BY_ORDER_DATE,
            discount_treatment=_DISCOUNT,
            allowed_dimensions=_LINE_DIMS,
            allowed_filters=_LINE_FILTERS,
            synonyms=["return rate", "refund ratio", "refund percentage"],
        ),
    ]
}


def get_metric(name: str) -> MetricDefinition:
    try:
        return METRICS[name]
    except KeyError:
        raise KeyError(f"Unknown metric '{name}'. Approved metrics: {sorted(METRICS)}") from None


def registry_fingerprint() -> str:
    """Hash over all metric hashes; changes whenever any approved definition changes."""
    joined = "|".join(f"{m.ref}:{m.definition_hash()}" for m in sorted(METRICS.values(), key=lambda m: m.name))
    return hashlib.sha256(joined.encode()).hexdigest()
