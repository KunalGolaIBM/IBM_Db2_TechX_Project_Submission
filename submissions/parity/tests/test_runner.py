"""Tests for the comparison runner and CLI parser."""

from parity.cli import _EXIT_CODES, build_parser
from parity.engine.executor import InMemoryExecutor
from parity.engine.result import ComparisonStatus, ResultSet
from parity.runner import run_comparison


def rs(rows):
    return ResultSet(columns=("id",), rows=tuple((r,) for r in rows))


def test_match_end_to_end():
    source = InMemoryExecutor({"SELECT 1": rs([1, 2])})
    target = InMemoryExecutor({"SELECT 1": rs([2, 1])})
    result = run_comparison(source, target, "SELECT 1", "SELECT 1")
    assert result.status is ComparisonStatus.MATCH


def test_mismatch_end_to_end():
    source = InMemoryExecutor({"SELECT 1": rs([1])})
    target = InMemoryExecutor({"SELECT 1": rs([9])})
    result = run_comparison(source, target, "SELECT 1", "SELECT 1")
    assert result.status is ComparisonStatus.MISMATCH
    assert result.diffs


def test_nondeterministic_not_comparable():
    source = InMemoryExecutor({})
    target = InMemoryExecutor({})
    result = run_comparison(source, target, "SELECT now()", "SELECT now()")
    assert result.status is ComparisonStatus.NOT_COMPARABLE
    assert source.calls == []
    assert target.calls == []


def test_source_error_returns_error_status():
    source = InMemoryExecutor({})
    target = InMemoryExecutor({"SELECT 1": rs([1])})
    result = run_comparison(source, target, "SELECT missing", "SELECT 1")
    assert result.status is ComparisonStatus.ERROR
    assert "source executor failed" in result.note


def test_cli_parser_defaults():
    args = build_parser().parse_args(["compare", "--source-sql", "SELECT 1", "--target-sql", "SELECT 1"])
    assert args.command == "compare"
    assert args.timeout == 30.0


def test_exit_codes_cover_all_statuses():
    assert set(_EXIT_CODES) == set(ComparisonStatus)
    assert _EXIT_CODES[ComparisonStatus.MATCH] == 0
    assert _EXIT_CODES[ComparisonStatus.MISMATCH] == 1
