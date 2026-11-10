"""Tests for nondeterminism detection and the in-memory executor."""

import pytest

from parity.engine.executor import InMemoryExecutor
from parity.engine.nondeterministic import find_nondeterministic_calls, is_nondeterministic
from parity.engine.result import ResultSet


def test_now_detected():
    assert find_nondeterministic_calls("SELECT now()") == ("now",)


def test_random_and_uuid_detected():
    found = find_nondeterministic_calls("SELECT random(), gen_random_uuid()")
    assert "random" in found
    assert "uuid" in found


def test_plain_query_not_flagged():
    assert not is_nondeterministic("SELECT id FROM users WHERE id = 1")


def test_in_memory_executor_returns_preset():
    result = ResultSet(columns=("a",), rows=((1,),))
    executor = InMemoryExecutor({"SELECT 1": result})
    assert executor.execute("SELECT 1") is result
    assert executor.calls == ["SELECT 1"]


def test_in_memory_executor_missing_sql():
    executor = InMemoryExecutor({})
    with pytest.raises(KeyError):
        executor.execute("SELECT 99")
