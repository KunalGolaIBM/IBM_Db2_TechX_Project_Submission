"""Deterministic presentation of ranked answers (Stage 4 fix)."""

from datetime import date
from decimal import Decimal

from metricguard.analysis import present
from metricguard.core.plan import DateRange, MetricRef, OrderBy, QueryPlan

Q2 = DateRange(start_date=date(2026, 4, 1), end_date=date(2026, 6, 30), source="explicit")
ROWS = [{"region": "NA", "net_revenue": Decimal("138679.66")}]
TOTALS = {"net_revenue": Decimal("325270.33")}  # control total across all regions


def _plan(**kw) -> QueryPlan:
    return QueryPlan(metrics=[MetricRef(name="net_revenue", version="1.0.0")], dimensions=["region"], filters=[],
                     date_range=Q2, **kw)


def test_top_one_headline_is_the_ranked_row_not_the_control_total():
    # "Which region had the highest net revenue in Q2 2026?" used to headline $325,270.33 (all regions).
    plan = _plan(order_by=[OrderBy(field="net_revenue", direction="desc")], limit=1)
    h = present.headline(plan, ROWS, TOTALS)
    assert h["formatted"] == "$138,679.66" and h["value"] == 138679.66
    assert h["label"] == "Top region: NA · Net Revenue (Q2 2026)"
    assert present.summary(plan, ROWS, TOTALS, truncated=False) == (
        "The top region by Net Revenue for Q2 2026 is NA ($138,679.66).")


def test_bottom_n_headline_names_the_first_row():
    rows = [{"region": "LATAM", "net_revenue": Decimal("40000.00")}, {"region": "APAC", "net_revenue": Decimal("60000.00")}]
    plan = _plan(order_by=[OrderBy(field="net_revenue", direction="asc")], limit=2)
    h = present.headline(plan, rows, TOTALS)
    assert h["label"].startswith("Bottom region: LATAM") and h["formatted"] == "$40,000.00"
    assert "bottom 2 regions" in present.summary(plan, rows, TOTALS, truncated=False)


def test_unranked_grouped_headline_keeps_the_control_total():
    h = present.headline(_plan(order_by=[], limit=None), ROWS, TOTALS)
    assert h["formatted"] == "$325,270.33" and h["label"] == "Net Revenue (Q2 2026)"


def test_ranked_headline_with_no_rows_is_absent():
    assert present.headline(_plan(order_by=[OrderBy(field="net_revenue", direction="desc")], limit=1), [], TOTALS) is None
