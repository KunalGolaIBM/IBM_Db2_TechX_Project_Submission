"""Tests for the tie order difference kind."""

from parity.engine.compare import compare_result_sets
from parity.engine.result import DiffKind, ResultSet


def test_same_rows_other_order_is_a_tie_order():
    source = ResultSet(columns=("v",), rows=((1,), (2,), (1,)))
    target = ResultSet(columns=("V",), rows=((1,), (1,), (2,)))
    result = compare_result_sets(source, target, sql="SELECT v FROM t ORDER BY v")
    assert result.status.value == "MISMATCH"
    assert result.diffs[0].kind is DiffKind.TIE_ORDER
    assert "not unique" in result.diffs[0].detail


def test_tie_order_does_not_hide_a_value_difference():
    source = ResultSet(columns=("v",), rows=((1,), (2,), (3,)))
    target = ResultSet(columns=("V",), rows=((1,), (2,), (4,)))
    result = compare_result_sets(source, target, sql="SELECT v FROM t ORDER BY v")
    assert result.status.value == "MISMATCH"
    assert result.diffs[0].kind is DiffKind.VALUE


def test_tie_order_without_order_by_is_ignored():
    source = ResultSet(columns=("v",), rows=((1,), (2,), (1,)))
    target = ResultSet(columns=("V",), rows=((1,), (1,), (2,)))
    result = compare_result_sets(source, target, sql="SELECT v FROM t")
    assert result.status.value == "MATCH"


def test_row_count_difference_is_not_tie_order():
    source = ResultSet(columns=("v",), rows=((1,), (2,)))
    target = ResultSet(columns=("V",), rows=((1,),))
    result = compare_result_sets(source, target, sql="SELECT v FROM t ORDER BY v")
    kinds = {diff.kind for diff in result.diffs}
    assert DiffKind.ROW_COUNT in kinds
    assert DiffKind.TIE_ORDER not in kinds
