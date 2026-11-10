"""Tests for the comparator."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from parity.engine.compare import EngineConfig, compare_result_sets
from parity.engine.result import ComparisonStatus, DiffKind, ResultSet


def make(columns, rows):
    return ResultSet(columns=tuple(columns), rows=tuple(tuple(r) for r in rows))


def test_identical_results_match():
    source = make(["id", "name"], [(1, "a"), (2, "b")])
    target = make(["ID", "Name"], [(2, "b"), (1, "a")])
    result = compare_result_sets(source, target)
    assert result.status is ComparisonStatus.MATCH
    assert result.diffs == ()


def test_order_by_makes_order_matter():
    source = make(["id"], [(1,), (2,)])
    target = make(["id"], [(2,), (1,)])
    result = compare_result_sets(source, target, sql="SELECT id FROM t ORDER BY id")
    assert result.status is ComparisonStatus.MISMATCH


def test_row_count_mismatch():
    source = make(["id"], [(1,), (2,)])
    target = make(["id"], [(1,)])
    result = compare_result_sets(source, target)
    assert result.status is ComparisonStatus.MISMATCH
    assert result.diffs[0].kind is DiffKind.ROW_COUNT


def test_null_never_equals_empty_string():
    source = make(["v"], [(None,)])
    target = make(["v"], [("",)])
    result = compare_result_sets(source, target)
    assert result.status is ComparisonStatus.MISMATCH
    assert result.diffs[0].kind is DiffKind.NULL_VS_VALUE


def test_null_equals_null():
    source = make(["v"], [(None,)])
    target = make(["v"], [(None,)])
    assert compare_result_sets(source, target).status is ComparisonStatus.MATCH


def test_trailing_space_is_its_own_category():
    source = make(["v"], [("abc",)])
    target = make(["v"], [("abc ",)])
    result = compare_result_sets(source, target)
    assert result.status is ComparisonStatus.MISMATCH
    assert result.diffs[0].kind is DiffKind.TRAILING_SPACE


def test_decimal_difference_below_tolerance_matches():
    """A difference no decimal scale can store is not a real difference."""
    source = make(["v"], [(Decimal("0.1"),)])
    target = make(["v"], [(Decimal("0.1000000001"),)])
    result = compare_result_sets(source, target)
    assert result.status is ComparisonStatus.MATCH


def test_decimal_real_difference_still_mismatches():
    """One unit of a DECIMAL(18,6) column must always be caught."""
    source = make(["v"], [(Decimal("999999.990000"),)])
    target = make(["v"], [(Decimal("999999.990001"),)])
    result = compare_result_sets(source, target)
    assert result.status is ComparisonStatus.MISMATCH


def test_float_uses_tolerance():
    source = make(["v"], [(1.0,)])
    target = make(["v"], [(1.0 + 1e-10,)])
    assert compare_result_sets(source, target).status is ComparisonStatus.MATCH
    strict = EngineConfig(float_tolerance=0.0)
    assert compare_result_sets(source, target, config=strict).status is ComparisonStatus.MISMATCH


def test_column_order_must_match():
    source = make(["a", "b"], [(1, 2)])
    target = make(["b", "a"], [(2, 1)])
    result = compare_result_sets(source, target)
    assert result.status is ComparisonStatus.MISMATCH
    assert result.diffs[0].kind is DiffKind.COLUMN_NAME


def test_duplicate_rows_count():
    source = make(["v"], [(1,), (1,)])
    target = make(["v"], [(1,)])
    assert compare_result_sets(source, target).status is ComparisonStatus.MISMATCH


def test_timestamp_utc_normalization():
    source = make(["ts"], [(datetime(2024, 1, 1, 12, 0, tzinfo=UTC),)])
    target = make(["ts"], [("2024-01-01T12:00:00+00:00",)])
    assert compare_result_sets(source, target).status is ComparisonStatus.MATCH


def test_bad_config_rejected():
    with pytest.raises(ValueError):
        EngineConfig(float_tolerance=-1.0)


def test_result_set_width_checked():
    with pytest.raises(ValueError):
        ResultSet(columns=("a", "b"), rows=((1,),))
