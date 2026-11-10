"""Tests for Db2 type conversion and numeric comparison."""

from decimal import Decimal

from parity.engine.compare import EngineConfig, compare_result_sets
from parity.engine.db2_types import convert_row, convert_value
from parity.engine.result import ResultSet


def test_decimal_string_converted():
    assert convert_value("1000.000000", "decimal") == Decimal("1000.000000")


def test_decimal_value_left_alone():
    assert convert_value(Decimal("1.5"), "decimal") == Decimal("1.5")


def test_non_decimal_untouched():
    assert convert_value("1000", "string") == "1000"
    assert convert_value("x", "string") == "x"


def test_none_untouched():
    assert convert_value(None, "decimal") is None


def test_invalid_decimal_left_alone():
    assert convert_value("not a number", "decimal") == "not a number"


def test_convert_row_uses_types():
    row = convert_row(("1000.000000", "alice", 5), ["decimal", "string", "int"])
    assert row == (Decimal("1000.000000"), "alice", 5)


def test_decimal_scale_difference_matches():
    source = ResultSet(columns=("credit_limit",), rows=((Decimal("1000.00"),),))
    target = ResultSet(columns=("CREDIT_LIMIT",), rows=((Decimal("1000.000000"),),))
    result = compare_result_sets(source, target)
    assert result.status.value == "MATCH"


def test_decimal_real_difference_still_mismatches():
    source = ResultSet(columns=("total",), rows=((Decimal("1000.00"),),))
    target = ResultSet(columns=("TOTAL",), rows=((Decimal("1000.01"),),))
    result = compare_result_sets(source, target)
    assert result.status.value == "MISMATCH"


def test_average_scale_difference_matches():
    source = ResultSet(
        columns=("avg",), rows=((Decimal("1786.2766666666666667"),),)
    )
    target = ResultSet(
        columns=("AVG",), rows=((Decimal("1786.2766666666666666666"),),)
    )
    result = compare_result_sets(source, target)
    assert result.status.value == "MATCH"


def test_decimal_tolerance_can_be_turned_off():
    source = ResultSet(columns=("avg",), rows=((Decimal("1.0000000000000001"),),))
    target = ResultSet(columns=("AVG",), rows=((Decimal("1.0000000000000002"),),))
    strict = EngineConfig(decimal_tolerance=Decimal(0))
    assert compare_result_sets(source, target, config=strict).status.value == "MISMATCH"


def test_boolean_matches_integer():
    source = ResultSet(columns=("active",), rows=((True,),))
    target = ResultSet(columns=("ACTIVE",), rows=((1,),))
    assert compare_result_sets(source, target).status.value == "MATCH"


def test_boolean_false_matches_zero():
    source = ResultSet(columns=("active",), rows=((False,),))
    target = ResultSet(columns=("ACTIVE",), rows=((0,),))
    assert compare_result_sets(source, target).status.value == "MATCH"


def test_boolean_differs_from_other_number():
    source = ResultSet(columns=("active",), rows=((True,),))
    target = ResultSet(columns=("ACTIVE",), rows=((2,),))
    assert compare_result_sets(source, target).status.value == "MISMATCH"


def test_settings_report_tolerances():
    source = ResultSet(columns=("id",), rows=((1,),))
    target = ResultSet(columns=("ID",), rows=((1,),))
    result = compare_result_sets(source, target)
    names = [name for name, _ in result.settings]
    assert "decimal_tolerance" in names
    assert "float_tolerance" in names
