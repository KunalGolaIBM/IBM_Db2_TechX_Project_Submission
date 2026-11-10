"""Tests for bounded parallel execution in the pipeline."""

from pathlib import Path

import pytest

from parity.cli import build_parser
from parity.engine.executor import InMemoryExecutor
from parity.engine.result import ComparisonStatus, ResultSet
from parity.pipeline import run_pipeline


def executors(tmp_path: Path):
    result_set = ResultSet(columns=("id",), rows=((1,),))
    sqls = ["SELECT id FROM demo_users WHERE id = 1", "SELECT id FROM demo_users WHERE id = 2"]
    (tmp_path / "q.sql").write_text(";\n".join(sqls) + ";", encoding="utf-8")
    source = InMemoryExecutor({sqls[0]: result_set, sqls[1]: result_set})
    target = InMemoryExecutor(
        {'SELECT id FROM "DEMO_USERS" WHERE id = 1': result_set, 'SELECT id FROM "DEMO_USERS" WHERE id = 2': result_set}
    )
    return source, target, sqls


def test_parallel_matches_sequential_order(tmp_path: Path):
    source, target, _ = executors(tmp_path)
    sequential = run_pipeline(tmp_path, source, target, concurrency=1)
    source, target, _ = executors(tmp_path)
    parallel = run_pipeline(tmp_path, source, target, concurrency=2)
    assert [r.query_id for r in parallel] == [r.query_id for r in sequential]
    assert all(r.result.status is ComparisonStatus.MATCH for r in parallel)


def test_concurrency_validation(tmp_path: Path):
    source, target, _ = executors(tmp_path)
    with pytest.raises(ValueError, match="row_limit must be positive"):
        run_pipeline(tmp_path, source, target, concurrency=0)


def test_cli_concurrency_parser():
    args = build_parser().parse_args(["run", "--dir", "samples", "--concurrency", "3"])
    assert args.concurrency == 3
    args = build_parser().parse_args(["run", "--dir", "samples"])
    assert args.concurrency == 1
