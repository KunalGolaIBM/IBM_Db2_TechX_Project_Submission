"""End to end comparison runner.

Runs one query on two executors and compares the results
with the deterministic engine. Handles nondeterministic
SQL and executor errors without hiding them.
"""

from __future__ import annotations

from parity.engine.compare import EngineConfig, compare_result_sets
from parity.engine.executor import DatabaseExecutor
from parity.engine.nondeterministic import find_nondeterministic_calls
from parity.engine.result import ComparisonResult, ComparisonStatus
from parity.engine.safety import DEFAULT_TIMEOUT_SECONDS, validate_timeout


def _error_result(message: str) -> ComparisonResult:
    return ComparisonResult(
        status=ComparisonStatus.ERROR,
        note=message[:500],
    )


def run_comparison(
    source: DatabaseExecutor,
    target: DatabaseExecutor,
    source_sql: str,
    target_sql: str,
    config: EngineConfig | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> ComparisonResult:
    """Run both queries and compare. Return the verdict.

    Nondeterministic source SQL returns NOT_COMPARABLE
    before any query runs. Executor failures return
    ERROR with the error text. A verdict of MATCH only
    comes from the comparator.
    """
    validate_timeout(timeout_seconds)
    calls = find_nondeterministic_calls(source_sql)
    if calls:
        return ComparisonResult(
            status=ComparisonStatus.NOT_COMPARABLE,
            note=f"nondeterministic calls found: {', '.join(calls)}",
        )
    try:
        source_result = source.execute(source_sql, timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - any executor failure becomes ERROR status
        return _error_result(f"source executor failed: {exc}")
    try:
        target_result = target.execute(target_sql, timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - any executor failure becomes ERROR status
        return _error_result(f"target executor failed: {exc}")
    return compare_result_sets(source_result, target_result, config=config, sql=source_sql)
