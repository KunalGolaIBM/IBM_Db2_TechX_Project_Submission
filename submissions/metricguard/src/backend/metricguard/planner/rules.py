"""DEMO_RULE_BASED planner: deterministic keyword rules for the curated example questions.

This is not an LLM and is never presented as one. Responses carry
`planner.execution_mode = "DEMO_RULE_BASED"` and a disclosure string. It exists so the demo
runs without an API key, and it goes through exactly the same validation, SQL compiler,
guard, execution and verification as the LangChain planner.
"""

from __future__ import annotations

import calendar
import re
import time
from datetime import date

from metricguard.core.registry import CATEGORIES, CHANNELS, REGIONS

from .base import AmbiguousMetric, Planner, PlannedFilter, PlannedSort, PlannerOutput, PlannerResult

# Longest phrases first; each match consumes its span so "refund rate" is not also "refunds".
_METRIC_PHRASES: list[tuple[str, str]] = sorted(
    [
        ("gross revenue", "gross_revenue"), ("gross sales", "gross_revenue"), ("bookings", "gross_revenue"),
        ("sales before refunds", "gross_revenue"), ("revenue before refunds", "gross_revenue"),
        ("net revenue", "net_revenue"), ("net sales", "net_revenue"), ("revenue after refunds", "net_revenue"),
        ("average order value", "average_order_value"), ("aov", "average_order_value"),
        ("average basket", "average_order_value"), ("average order size", "average_order_value"),
        ("refund rate", "refund_rate"), ("return rate", "refund_rate"), ("refund ratio", "refund_rate"),
        ("refund percentage", "refund_rate"),
        ("refund amount", "refund_amount"), ("refunded amount", "refund_amount"), ("refunds", "refund_amount"),
        ("returns value", "refund_amount"),
        ("order count", "order_count"), ("number of orders", "order_count"), ("how many orders", "order_count"),
        ("completed orders", "order_count"), ("orders", "order_count"), ("transactions", "order_count"),
    ],
    key=lambda p: -len(p[0]),
)
# Business terms that are not approved metrics: they are passed through so the validator blocks them
# with UNKNOWN_METRIC instead of the planner silently substituting something else.
_UNSUPPORTED_METRICS: list[tuple[str, str]] = [
    ("customer lifetime value", "customer_lifetime_value"), ("lifetime value", "customer_lifetime_value"),
    ("ltv", "customer_lifetime_value"), ("gross margin", "gross_margin"), ("profit margin", "profit_margin"),
    ("profit", "profit"), ("margin", "margin"), ("churn", "churn_rate"), ("conversion rate", "conversion_rate"),
    ("inventory", "inventory"), ("cost of goods", "cogs"), ("cogs", "cogs"), ("shipping revenue", "shipping_revenue"),
    ("tax", "tax_amount"), ("nps", "net_promoter_score"), ("active users", "active_users"),
    ("ebitda", "ebitda"), ("cac", "customer_acquisition_cost"),
]

_DIMENSION_WORDS = {
    "month": "order_month", "months": "order_month", "order month": "order_month",
    "region": "region", "regions": "region",
    "channel": "channel", "channels": "channel", "sales channel": "channel", "sales channels": "channel",
    "category": "product_category", "categories": "product_category", "product category": "product_category",
    "product categories": "product_category",
}
_BY_RE = re.compile(r"\b(?<!sorted\s)(?<!ranked\s)(?<!ordered\s)(?:by|per|for\s+each|each|across)\s+"
                    r"((?:sales\s+|product\s+|order\s+)?[a-z_]+)", re.IGNORECASE)
_MONTHLY_RE = re.compile(r"\b(monthly|month[-\s]by[-\s]month|trend|each\s+month|per\s+month)\b", re.IGNORECASE)
_PLURAL_DIM_RE = re.compile(r"\b(?:which|what|top|bottom|compare|all)\b[^?.]*?\b(product\s+categories|regions|"
                            r"sales\s+channels|channels)\b", re.IGNORECASE)

_REGION_WORDS = {"emea": "EMEA", "apac": "APAC", "latam": "LATAM", "north america": "NA", "europe": None}
_CHANNEL_WORDS = {"web": "WEB", "online": "WEB", "mobile": "MOBILE", "app": "MOBILE", "in-store": "STORE",
                  "store": "STORE", "marketplace": "MARKETPLACE"}
_CATEGORY_WORDS = {c.lower(): c for c in CATEGORIES}
_EXPLICIT_VALUE_RE = re.compile(r"\b(region|channel|category)\s*(?:=|:|is|of)?\s*'?([A-Z][A-Z_]{1,})'?")

_MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
_ISO_RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*(?:to|through|until|and|-|–)\s*(\d{4}-\d{2}-\d{2})")
_QUARTER_RE = re.compile(r"\bq([1-4])\s*(?:of\s+)?(\d{4})\b", re.IGNORECASE)
_HALF_RE = re.compile(r"\b(?:h([12])|(first|second)\s+half\s+(?:of\s+)?)\s*(\d{4})\b", re.IGNORECASE)
_MONTH_RE = re.compile(r"\b(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?\s+(\d{4})\b", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(?:in|for|during|of)\s+(20\d{2})\b", re.IGNORECASE)
_TOP_RE = re.compile(r"\b(top|bottom|best|worst|lowest|highest)\s+(\d{1,3})\b", re.IGNORECASE)
_SUPERLATIVE_RE = re.compile(r"\b(highest|most|largest|biggest|best|lowest|least|smallest|worst)\b", re.IGNORECASE)
# "Which region had the highest ...": a singular grouping plus a superlative asks for the single first-ranked group.
_WHICH_ONE_RE = re.compile(r"\b(?:which|what)\s+(region|sales\s+channel|channel|product\s+category|month)\b",
                           re.IGNORECASE)
_WHICH_ONE_DIM = {"region": "region", "sales channel": "channel", "channel": "channel",
                  "product category": "product_category", "month": "order_month"}


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _dates(q: str) -> tuple[date | None, date | None]:
    if m := _ISO_RANGE_RE.search(q):
        return date.fromisoformat(m.group(1)), date.fromisoformat(m.group(2))
    if m := _QUARTER_RE.search(q):
        n, year = int(m.group(1)), int(m.group(2))
        return date(year, 3 * n - 2, 1), _month_end(year, 3 * n)
    if m := _HALF_RE.search(q):
        first = m.group(1) == "1" or (m.group(2) or "").lower() == "first"
        year = int(m.group(3))
        return (date(year, 1, 1), date(year, 6, 30)) if first else (date(year, 7, 1), date(year, 12, 31))
    if m := _MONTH_RE.search(q):
        month, year = _MONTHS[m.group(1).lower()], int(m.group(2))
        return date(year, month, 1), _month_end(year, month)
    if m := _YEAR_RE.search(q):
        year = int(m.group(1))
        return date(year, 1, 1), date(year, 12, 31)
    return None, None


def _find_metrics(q: str) -> list[str]:
    text = q.lower()
    hits: list[tuple[int, str]] = []
    for phrase, name in [*_METRIC_PHRASES, *_UNSUPPORTED_METRICS]:
        for m in re.finditer(rf"\b{re.escape(phrase)}\b", text):
            hits.append((m.start(), name))
            text = text[: m.start()] + " " * len(phrase) + text[m.end():]
    ordered: list[str] = []
    for _, name in sorted(hits):
        if name not in ordered:
            ordered.append(name)
    return ordered


def _find_dimensions(q: str) -> list[str]:
    dims: list[tuple[int, str]] = []
    for m in _BY_RE.finditer(q):
        word = m.group(1).lower().strip()
        if word in _DIMENSION_WORDS:
            dims.append((m.start(), _DIMENSION_WORDS[word]))
        elif word.split()[-1] in _DIMENSION_WORDS:
            dims.append((m.start(), _DIMENSION_WORDS[word.split()[-1]]))
        elif word not in {"the", "a", "an", "all", "our", "net", "gross", "refund", "order", "average"} \
                and not any(word.startswith(p) for p, _ in _METRIC_PHRASES):
            dims.append((m.start(), word.replace(" ", "_")))  # unknown -> validator blocks UNKNOWN_DIMENSION
    for m in re.finditer(r"\b(?:by|per)\s+[a-z_ ]+?\s+and\s+((?:sales\s+|product\s+|order\s+)?[a-z]+)", q,
                         re.IGNORECASE):
        word = m.group(1).lower()
        if word in _DIMENSION_WORDS:
            dims.append((m.start(1), _DIMENSION_WORDS[word]))
    if m := _MONTHLY_RE.search(q):
        dims.append((m.start(), "order_month"))
    for m in _PLURAL_DIM_RE.finditer(q):
        dims.append((m.start(1), _DIMENSION_WORDS[m.group(1).lower().replace("  ", " ")]))
    out: list[str] = []
    for _, d in sorted(dims):
        if d not in out:
            out.append(d)
    return out


def _find_filters(q: str, dimensions: list[str]) -> list[PlannedFilter]:
    lower = q.lower()
    found: dict[str, list[str]] = {}

    def add(fieldname: str, value: str) -> None:
        if value not in found.setdefault(fieldname, []):
            found[fieldname].append(value)

    for word, code in _REGION_WORDS.items():
        if code and re.search(rf"\b{re.escape(word)}\b", lower):
            add("region", code)
    if re.search(r"\bNA\b", q):
        add("region", "NA")
    for word, code in _CHANNEL_WORDS.items():
        if re.search(rf"\b(?:on|via|through|in|from|the)\s+(?:the\s+)?{re.escape(word)}\b(?:\s+channel)?", lower) or \
                re.search(rf"\b{re.escape(word)}\s+channel\b", lower):
            add("channel", code)
    for word, code in _CATEGORY_WORDS.items():
        if re.search(rf"\b{word}\b(?!\s+categor)", lower) and "product_category" not in dimensions:
            add("product_category", code)
    for m in _EXPLICIT_VALUE_RE.finditer(q):
        fieldname = {"category": "product_category"}.get(m.group(1).lower(), m.group(1).lower())
        add(fieldname, m.group(2))
    allowed = {"region": REGIONS, "channel": CHANNELS, "product_category": CATEGORIES}
    return [PlannedFilter(field=f, values=v) for f, v in found.items() if f in allowed]


class RuleBasedPlanner(Planner):
    name = "rules-demo"
    model = None
    execution_mode = "DEMO_RULE_BASED"
    provider = "metricguard-rules"

    def plan(self, question: str) -> PlannerResult:
        started = time.perf_counter()
        output = self._plan(question)
        return PlannerResult(output=output, name=self.name, model=None, execution_mode="DEMO_RULE_BASED", provider="metricguard-rules",
                             elapsed_ms=round((time.perf_counter() - started) * 1000, 2))

    def _plan(self, q: str) -> PlannerOutput:
        metrics = _find_metrics(q)
        dimensions = _find_dimensions(q)
        filters = _find_filters(q, dimensions)
        start, end = _dates(q)
        ambiguous = None
        bare = re.search(r"(?<!gross\s)(?<!net\s)\b(revenue|sales)\b(?!\s+(?:after|before|channels?))", q, re.IGNORECASE)
        if bare and not any(m in metrics for m in ("gross_revenue", "net_revenue")):
            ambiguous = AmbiguousMetric(term=bare.group(1), candidate_metrics=["net_revenue", "gross_revenue"])
        order_by: list[PlannedSort] = []
        limit = None
        if metrics:
            if m := _TOP_RE.search(q):
                limit = int(m.group(2))
                desc = m.group(1).lower() in {"top", "best", "highest"}
                order_by = [PlannedSort(field=metrics[0], direction="desc" if desc else "asc")]
            elif m := _SUPERLATIVE_RE.search(q):
                one = _WHICH_ONE_RE.search(q)
                if one and not dimensions:
                    dimensions = [_WHICH_ONE_DIM[re.sub(r"\s+", " ", one.group(1).lower())]]
                    limit = 1
                if dimensions:
                    desc = m.group(1).lower() in {"highest", "most", "largest", "biggest", "best"}
                    order_by = [PlannedSort(field=metrics[0], direction="desc" if desc else "asc")]
        intent = "ambiguous" if ambiguous else ("analysis" if metrics else "out_of_scope")
        return PlannerOutput(
            intent=intent, metrics=metrics, dimensions=dimensions, filters=filters, start_date=start, end_date=end,
            order_by=order_by, limit=limit, ambiguous_metric=ambiguous, relative_time_phrase=None,
        )
