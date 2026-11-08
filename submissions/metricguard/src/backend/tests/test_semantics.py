"""Unit tests: registry, plan validation, compiler, SQL guard, generator and oracle (no database)."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from metricguard.core.compiler import compile_plan
from metricguard.core.examples import EXAMPLES
from metricguard.core.plan import DateRange, FilterClause, MetricRef, QueryPlan
from metricguard.core.registry import METRICS, registry_fingerprint
from metricguard.core.sql_guard import check_sql
from metricguard.core.validator import validate_plan
from metricguard.seed import oracle
from metricguard.seed.generator import (
    CANARY_ORDER_IDS,
    Dataset,
    Order,
    OrderItem,
    Product,
    Refund,
    generate,
)

REQUIRED_METRICS = {"gross_revenue", "net_revenue", "order_count", "average_order_value", "refund_amount", "refund_rate"}


def plan(*metrics, dims=(), filters=(), start=date(2026, 1, 1), end=date(2026, 6, 30), **kw) -> QueryPlan:
    return QueryPlan(
        metrics=[MetricRef(name=m, version=METRICS[m].version) for m in metrics],
        dimensions=list(dims),
        filters=[FilterClause(field=f, values=v) for f, v in filters],
        date_range=DateRange(start_date=start, end_date=end),
        **kw,
    )


# ---- registry -----------------------------------------------------------------------
def test_registry_contains_required_metrics_with_complete_semantics():
    assert REQUIRED_METRICS == set(METRICS)
    for m in METRICS.values():
        for field in ("description", "calculation", "date_attribution", "null_handling", "refund_treatment",
                      "discount_treatment"):
            assert len(getattr(m, field)) > 10, (m.name, field)
        assert m.eligible_order_statuses == ["COMPLETED"]
        assert m.allowed_dimensions and m.allowed_filters and m.version


def test_registry_metadata_contains_no_executable_sql():
    for m in METRICS.values():
        blob = m.canonical_json().upper()
        for token in ("SELECT ", "FROM METRICGUARD", "INSERT INTO", "DELETE FROM", "JOIN METRICGUARD"):
            assert token not in blob, (m.name, token)


def test_definition_hash_is_stable_and_sensitive():
    m = METRICS["net_revenue"]
    assert m.definition_hash() == METRICS["net_revenue"].definition_hash()
    changed = m.model_copy(update={"null_handling": "different"})
    assert changed.definition_hash() != m.definition_hash()
    assert len(registry_fingerprint()) == 64


# ---- validation ---------------------------------------------------------------------
def test_order_grain_metrics_cannot_be_split_by_category():
    codes = {i.code for i in validate_plan(plan("average_order_value", dims=["product_category"]))}
    assert "DIMENSION_NOT_ALLOWED" in codes
    codes = {i.code for i in validate_plan(plan("order_count", filters=[("product_category", ["HOME"])]))}
    assert "FILTER_NOT_ALLOWED" in codes


def test_unknown_metric_version_and_values_are_blocked():
    p = QueryPlan(metrics=[MetricRef(name="profit", version="1.0.0")],
                  date_range=DateRange(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)))
    assert {i.code for i in validate_plan(p)} == {"UNKNOWN_METRIC"}
    p = QueryPlan(metrics=[MetricRef(name="net_revenue", version="0.9.0")],
                  date_range=DateRange(start_date=date(2026, 1, 1), end_date=date(2026, 1, 31)))
    assert {i.code for i in validate_plan(p)} == {"METRIC_VERSION_MISMATCH"}
    codes = {i.code for i in validate_plan(plan("net_revenue", filters=[("region", ["EMEA'; DROP TABLE x--"])]))}
    assert codes == {"FILTER_VALUE_NOT_ALLOWED"}


def test_date_range_must_be_ordered():
    with pytest.raises(ValueError):
        DateRange(start_date=date(2026, 3, 1), end_date=date(2026, 2, 1))


# ---- compiler -----------------------------------------------------------------------
def test_compiled_sql_is_parameterized_and_passes_guard():
    p = plan("net_revenue", "refund_rate", dims=["order_month"], filters=[("region", ["EMEA", "NA"]),
                                                                          ("product_category", ["HOME"])])
    c = compile_plan(p)
    assert check_sql(c.sql) == []
    assert c.sql.count("?") == len(c.parameters)
    for value in ("EMEA", "HOME", "COMPLETED", "PROCESSED", "2026-01-01"):
        assert value not in c.sql
    names = [x.name for x in c.parameters]
    assert names[:3] == ["eligible_status_1", "date_start_inclusive", "date_end_exclusive"]
    assert c.parameters[2].value == "2026-07-01 00:00:00"  # inclusive end date -> exclusive bound


def test_refunds_are_pre_aggregated_before_line_join():
    sql = compile_plan(plan("refund_amount", dims=["region"])).sql
    cte = sql.split("line_refunds AS (")[1].split("\n)")[0]
    assert "GROUP BY r.ORDER_ITEM_ID" in sql and "SUM(r.REFUND_AMOUNT)" in cte
    assert "LEFT JOIN line_refunds lr ON lr.ORDER_ITEM_ID = i.ORDER_ITEM_ID" in sql
    assert "SHIPPING_AMOUNT" not in sql


def test_refund_cte_omitted_when_not_needed():
    sql = compile_plan(plan("gross_revenue", "order_count")).sql
    assert "REFUNDS" not in sql and "FETCH FIRST" not in sql


def test_top_n_limit_and_sort():
    ex = next(e for e in EXAMPLES if e.id == "ex-07-top-web-categories-q2")
    c = compile_plan(ex.reference_plan)
    assert "ORDER BY NET_REVENUE DESC, PRODUCT_CATEGORY ASC" in c.sql
    assert c.sql.endswith("FETCH FIRST 3 ROWS ONLY")


def test_every_executable_example_validates_and_compiles():
    for ex in EXAMPLES:
        if ex.reference_plan is None:
            assert ex.expected_status in {"AMBIGUOUS", "BLOCKED"}
            continue
        assert validate_plan(ex.reference_plan) == [], ex.id
        assert check_sql(compile_plan(ex.reference_plan).sql) == [], ex.id


# ---- SQL guard ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "sql,code",
    [
        ("DELETE FROM METRICGUARD.REFUNDS", "SQL_NOT_SELECT"),
        ("SELECT 1 FROM METRICGUARD.ORDERS; DROP TABLE METRICGUARD.ORDERS", "SQL_MULTI_STATEMENT"),
        ("SELECT * FROM SYSCAT.TABLES", "SQL_SYSTEM_CATALOG"),
        ("SELECT * FROM METRICGUARD.QUERY_AUDIT_LOG", "SQL_TABLE_NOT_ALLOWED"),
        ("SELECT * FROM METRICGUARD.ORDERS /* hidden */", "SQL_BLOCK_COMMENT"),
        ("WITH x AS (SELECT 1 FROM METRICGUARD.ORDERS) SELECT * FROM x WHERE 1 = (CALL foo())", "SQL_FORBIDDEN_KEYWORD"),
    ],
)
def test_guard_rejects_unsafe_sql(sql, code):
    assert code in {f.code for f in check_sql(sql)}


def test_guard_ignores_keywords_inside_string_literals():
    assert check_sql("SELECT COUNT(*) FROM METRICGUARD.ORDERS WHERE PROMO_CODE = 'DELETE'") == []


# ---- generator ------------------------------------------------------------------------
def test_generator_is_deterministic_and_sized():
    a, b = generate(), generate()
    assert a.orders == b.orders and a.items == b.items and a.refunds == b.refunds
    assert 1000 <= len(a.orders) <= 5000
    assert {o.status for o in a.orders} == {"COMPLETED", "CANCELLED", "PENDING"}
    assert {r.status for r in a.refunds} == {"PROCESSED", "PENDING", "REJECTED"}
    assert {o.order_ts.month for o in a.orders} == {1, 2, 3, 4, 5, 6}
    assert set(CANARY_ORDER_IDS) <= {o.order_id for o in a.orders}


def test_generator_invariants():
    ds = generate()
    line_rev = {i.order_item_id: i.line_revenue for i in ds.items}
    processed: dict[int, Decimal] = {}
    for r in ds.refunds:
        if r.status == "PROCESSED":
            processed[r.order_item_id] = processed.get(r.order_item_id, Decimal(0)) + r.refund_amount
    assert all(v <= line_rev[k] for k, v in processed.items())
    assert all(0 <= i.discount_amount <= i.quantity * i.unit_price for i in ds.items)
    orders_with_lines = {i.order_id for i in ds.items}
    assert all(o.order_id in orders_with_lines for o in ds.orders)
    # traps actually present
    assert any(i.line_revenue == 0 for i in ds.items)
    cancelled = {o.order_id for o in ds.orders if o.status == "CANCELLED"}
    assert any(r.order_id in cancelled and r.status == "PROCESSED" for r in ds.refunds)
    multi = {}
    for r in ds.refunds:
        multi[r.order_item_id] = multi.get(r.order_item_id, 0) + 1
    assert max(multi.values()) >= 2


# ---- oracle on a hand-built dataset ----------------------------------------------------
def _tiny() -> Dataset:
    D = Decimal
    ds = Dataset(seed=0)
    ds.products = [Product(1, "A", "A", "HOME", D("10.00"), 1), Product(2, "B", "B", "BEAUTY", D("5.00"), 1)]
    ds.orders = [
        Order(1, "1", 1, datetime(2026, 1, 31, 23, 59, 59), "COMPLETED", "EMEA", "WEB", D("7.99"), None, None),
        Order(2, "2", 1, datetime(2026, 2, 1, 0, 0, 0), "COMPLETED", "EMEA", "WEB", D("0"), None, None),
        Order(3, "3", 1, datetime(2026, 1, 15), "CANCELLED", "EMEA", "WEB", D("0"), None, datetime(2026, 1, 16)),
    ]
    ds.items = [
        OrderItem(11, 1, 1, 1, 3, D("10.00"), D("3.00")),  # 27.00
        OrderItem(12, 1, 2, 2, 1, D("5.00"), D("0.00")),   # 5.00
        OrderItem(21, 2, 1, 2, 2, D("5.00"), D("10.00")),  # 0.00 (100% discount)
        OrderItem(31, 3, 1, 1, 1, D("10.00"), D("0.00")),  # cancelled
    ]
    ds.refunds = [
        Refund(1, 1, 11, datetime(2026, 2, 5), D("4.00"), "PROCESSED", None),
        Refund(2, 1, 11, datetime(2026, 2, 6), D("2.00"), "PROCESSED", None),
        Refund(3, 1, 11, datetime(2026, 2, 7), D("9.00"), "REJECTED", None),
        Refund(4, 3, 31, datetime(2026, 1, 16), D("10.00"), "PROCESSED", None),
    ]
    return ds


def test_oracle_hand_computed_values():
    rows = oracle.compute(_tiny(), metrics=sorted(REQUIRED_METRICS), dimensions=["order_month"],
                          start=date(2026, 1, 1), end=date(2026, 2, 28))
    jan, feb = rows
    assert jan == {"order_month": "2026-01", "average_order_value": Decimal("32.00"), "gross_revenue": Decimal("32.00"),
                   "net_revenue": Decimal("26.00"), "order_count": 1, "refund_amount": Decimal("6.00"),
                   "refund_rate": Decimal("0.187500")}
    assert feb["gross_revenue"] == Decimal("0.00") and feb["order_count"] == 1
    assert feb["refund_rate"] is None  # zero denominator -> NULL, not 0


def test_oracle_end_date_is_inclusive_through_last_second():
    rows = oracle.compute(_tiny(), metrics=["order_count"], dimensions=[], start=date(2026, 1, 1),
                          end=date(2026, 1, 31))
    assert rows == [{"order_count": 1}]
