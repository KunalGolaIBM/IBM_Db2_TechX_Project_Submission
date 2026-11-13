"""The attack chips against Db2: each is stopped by the layer the page names, and Db2 itself refuses the writes too."""

from __future__ import annotations

import uuid

import pytest
from test_db2_ledger import entry

from asof import db, ledger, redteam, schema, seed, wlm
from asof.askledger import LedgerAsker

pytestmark = pytest.mark.db2


class NoModel:
    """The attacks call no model; any call is a bug."""

    info = "none"

    def structured(self, *a, **k):
        raise AssertionError("an attack must not call the model")


@pytest.fixture(scope="module")
def attacked(admin_conn, embeddings, settings):
    """A scratch schema with two decisions, so there is customer text to mask."""
    name = f"ASOF_K{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_policy(admin_conn, embeddings, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_published_answers(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)  # the grants cover every table, the FAQ store included
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name,
                            analyst_user=settings.asof_analyst_user)
        app = db.connect(settings, "app")
        try:
            for _ in range(2):
                ledger.append(app, entry(question_redacted="My card ends 4242, can I get a refund?"), name)
        finally:
            app.close()
    except Exception:
        schema.drop(admin_conn, name)
        raise
    yield LedgerAsker(NoModel(), settings, name)
    schema.drop(admin_conn, name)


@pytest.mark.parametrize("key", ["delete", "update", "tables"])
def test_the_sql_check_stops_it_and_db2_would_refuse_it_too(attacked, key):
    r = redteam.run(attacked, key)
    assert (r.status, r.stopped_by, r.rows) == ("REFUSED", "SQL check", [])
    privileges = r.layers[1]
    assert privileges["layer"] == "Db2 privileges" and privileges["outcome"] == "refused", privileges
    assert "42501" in privileges["detail"]


def test_the_customers_text_comes_back_masked(attacked):
    r = redteam.run(attacked, "messages")
    assert (r.status, r.stopped_by) == ("ANSWERED", "Db2 column masks")
    assert r.columns == ["LEDGER_ID", "QUESTION_REDACTED", "FINAL_ANSWER"] and len(r.rows) == 2
    assert all(row[1:] == ["[masked]", "[masked]"] for row in r.rows)


def test_the_heavy_query_is_stopped_by_db2s_workload_management(attacked):
    r = redteam.run(attacked, "heavy")
    assert (r.status, r.stopped_by) == ("STOPPED", "Db2 workload threshold")
    assert "SQL4712N" in r.attempts[0]["db2_error"] and r.reason == r.attempts[0]["db2_threshold"]
    assert any(limit.threshold in r.reason for limit in wlm.LIMITS)


def test_the_chain_is_untouched(settings, attacked):
    for key in ("delete", "update"):
        redteam.run(attacked, key)
    with db.connection(settings, "app") as app:
        assert ledger.verify_chain(app, attacked.schema).status == "OK"
        db.use_schema(app, attacked.schema)
        assert db.query(app, "SELECT COUNT(*) FROM ANSWER_LEDGER WHERE DECISION = 'PASS'") == [(0,)]
