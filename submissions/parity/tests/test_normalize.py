"""Tests for the normalizer."""

from datetime import datetime, timezone
from decimal import Decimal

from parity.engine.normalize import is_trailing_space_only, normalize_value


def test_int_becomes_decimal():
    assert normalize_value(5) == Decimal(5)


def test_bool_stays_bool():
    assert normalize_value(True) is True


def test_none_stays_none():
    assert normalize_value(None) is None


def test_empty_string_stays_empty():
    assert normalize_value("") == ""


def test_naive_datetime_treated_as_utc():
    value = normalize_value(datetime(2024, 1, 1, 12, 0))  # noqa: DTZ001
    assert value == "2024-01-01T12:00:00+00:00"


def test_aware_datetime_converted_to_utc():
    from datetime import timedelta

    tz = timezone(timedelta(hours=2))
    value = normalize_value(datetime(2024, 1, 1, 14, 0, tzinfo=tz))
    assert value == "2024-01-01T12:00:00+00:00"


def test_bytes_become_hex():
    assert normalize_value(b"\x01\x02") == "0102"


def test_trailing_space_only():
    assert is_trailing_space_only("abc", "abc ")
    assert not is_trailing_space_only("abc", "abd")
    assert not is_trailing_space_only("abc", "abc")
    assert not is_trailing_space_only(1, "1 ")
