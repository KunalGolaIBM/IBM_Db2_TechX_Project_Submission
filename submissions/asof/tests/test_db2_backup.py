"""The backup and restore drill, end to end: an online Db2 backup, a restore into a new database, and the
ledger's checks on the copy. It creates and drops two databases, which takes minutes under emulation, so it
runs only when asked: ASOF_RUN_BACKUP_TESTS=1 pytest -m backup (CI runs it on IBM's stock image)."""

from __future__ import annotations

import pytest

from asof import backup

pytestmark = [pytest.mark.db2, pytest.mark.backup]


def test_online_backup_restores_into_a_fresh_database_with_chain_and_anchors_intact(settings, admin_conn, tmp_path,
                                                                                     monkeypatch):
    # The drill runs setup in a subprocess, and setup creates an anchor key file when none is set. Hand it a
    # throwaway key through the environment instead, so no test after this one finds a key on disk.
    monkeypatch.setenv("ASOF_ANCHOR_KEY", "drill-test-key-" + "x" * 32)
    report = backup.run(settings, rows=12, anchor_dir=tmp_path)
    failed = [name for name, ok in report["checks"].items() if not ok]
    assert not failed, failed
    assert report["appended_during_backup"] >= 1 and not report["writer_errors"]
    assert report["verify_chain"]["status"] == "OK"
    assert report["anchors"]["status"] == "OK" and report["anchors"]["covered_through"] == report["restored_head"]["ledger_id"]
    assert report["source_head_before_backup"]["ledger_id"] <= report["restored_head"]["ledger_id"]
    assert report["update_refused_sqlstate"] == "75001"
