"""The ledger benchmark end to end at a small volume: both designs installed, loaded, explained and timed, the
same answers from both, and the scratch schemas dropped."""

from __future__ import annotations

import pytest

from asof import db, ledgerbench

pytestmark = pytest.mark.db2


def test_both_designs_load_answer_alike_and_are_dropped(settings, admin_conn, tmp_path):
    if ledgerbench.find_db2_container(settings.db2_container) is None:
        pytest.skip("the benchmark collects statistics and plans inside the Db2 container")
    r = ledgerbench.run(settings, rows=ledgerbench.BATCH, plans_dir=tmp_path)
    assert set(r["queries"]) == {name for name, *_ in ledgerbench.QUERIES}
    assert all(q["same_rows"] for q in r["queries"].values()), [n for n, q in r["queries"].items() if not q["same_rows"]]
    analytics = r["queries"]["analytics_decisions"]
    # The view reads the MQT, not the ledger. The rest of each plan is the domain row permissions' lookups
    # (DOMAIN_ACCESS, the SECADM check) and the per-domain MQT branch, which returns nothing to the owner.
    part, flat = analytics["LBPART"]["objects"], analytics["LBFLAT"]["objects"]
    assert "MQT_DECISION_STATS (table)" in part and not [o for o in part if o.startswith("ANSWER_LEDGER")], part
    assert "ANSWER_LEDGER (table)" in flat and not [o for o in flat if o.startswith("MQT_")], flat
    assert r["append_ms"]["LBPART"] > 0  # (db2exfmt plan text is best effort: IBM's CI container wrote none)
    left = db.query(admin_conn, "SELECT SCHEMANAME FROM SYSCAT.SCHEMATA WHERE SCHEMANAME IN ('LBFLAT', 'LBPART')")
    assert left == []
