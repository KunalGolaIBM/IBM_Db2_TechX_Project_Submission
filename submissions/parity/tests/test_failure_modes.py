"""Failure mode tests for hardening."""

import pytest

from parity.engine.executor import InMemoryExecutor
from parity.engine.result import ComparisonStatus, ResultSet
from parity.engine.safety import (
    DEFAULT_ROW_LIMIT,
    DEFAULT_TIMEOUT_SECONDS,
    validate_row_limit,
    validate_timeout,
)
from parity.runner import run_comparison


def result_set():
    return ResultSet(columns=("id",), rows=((1,),))


class ExplodingExecutor:
    """Executor that simulates a database dying mid-run."""

    def execute(self, sql: str, timeout_seconds: float = 30.0) -> ResultSet:
        raise RuntimeError("connection lost")


def test_timeout_must_be_positive():
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        run_comparison(
            InMemoryExecutor({}),
            InMemoryExecutor({}),
            "SELECT 1",
            "SELECT 1",
            timeout_seconds=0,
        )
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        validate_timeout(-1)


def test_row_limit_must_be_positive():
    with pytest.raises(ValueError, match="row_limit must be positive"):
        validate_row_limit(0)


def test_defaults_are_sane():
    assert DEFAULT_TIMEOUT_SECONDS == 30.0
    assert DEFAULT_ROW_LIMIT == 100_000


def test_source_db_death_returns_error():
    result = run_comparison(
        ExplodingExecutor(),
        InMemoryExecutor({}),
        "SELECT 1",
        "SELECT 1",
    )
    assert result.status is ComparisonStatus.ERROR
    assert "source executor failed" in result.note
    assert "connection lost" in result.note


def test_target_db_death_returns_error():
    result = run_comparison(
        InMemoryExecutor({"SELECT 1": result_set()}),
        ExplodingExecutor(),
        "SELECT 1",
        "SELECT 1",
    )
    assert result.status is ComparisonStatus.ERROR
    assert "target executor failed" in result.note


def test_missing_preset_returns_error_not_hang():
    result = run_comparison(
        InMemoryExecutor({}),
        InMemoryExecutor({"SELECT 1": result_set()}),
        "SELECT 1",
        "SELECT 1",
    )
    assert result.status is ComparisonStatus.ERROR


def test_gateway_total_failure_raises():
    import urllib.error

    from parity.gateway.cache import InMemoryCache
    from parity.gateway.client import Gateway
    from parity.gateway.types import ProviderConfig

    def dead(provider, system, user):
        raise urllib.error.URLError("gateway down")

    provider = ProviderConfig(name="p", base_url="http://localhost", model="m")
    gateway = Gateway(providers=[provider], cache=InMemoryCache(), transport=dead)
    with pytest.raises(RuntimeError, match="all providers failed"):
        gateway.complete("translator", "sys", "user")
