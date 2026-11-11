"""The Db2 tools that CI also runs as steps of their own: the feature check and the chain benchmark, at small scale."""

from __future__ import annotations

import uuid

import pytest

from asof import chainbench, db2check

pytestmark = pytest.mark.db2


def test_every_db2_feature_check_passes_and_leaves_nothing_behind(admin_conn, capsys):
    assert db2check.run() == 0
    out = capsys.readouterr().out
    assert f"{len(db2check.CHECKS)}/{len(db2check.CHECKS)} Db2 feature checks passed" in out and "was removed" in out


def test_the_chain_benchmark_builds_a_real_chain_that_verify_chain_accepts(admin_conn, settings):
    target = f"CB{uuid.uuid4().hex[:6].upper()}"
    result = chainbench.run(settings, 40, target=target, extra=5, machine="test runner")
    [point] = result["points"]
    assert (point["status"], point["rows"], point["rows_checked"]) == ("OK", 40, 40)
    # No checkpoint yet, so the first verify from a checkpoint is a full one; the next covers only the 5 new rows.
    first = point["incremental"]
    assert (first["status"], first["rows_checked"], first["from_ledger_id"]) == ("OK", 40, 1)
    after = result["after_checkpoint"]
    assert (after["status"], after["rows"], after["rows_checked"], after["from_ledger_id"]) == ("OK", 45, 6, 40)
    report = chainbench.report([result])
    assert "| 40 | OK |" in report and "VERIFY_CHAIN" in report and "Machine: test runner." in report
    assert "recomputing 6 rows" in report
