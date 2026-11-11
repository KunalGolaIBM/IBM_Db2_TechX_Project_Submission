"""Db2 integration: every ledger row records who stored it (SESSION_USER, roles, trusted context), set by Db2.

13_trusted_context.sql adds STORED_BY, STORED_ROLES and STORED_CONTEXT and a BEFORE INSERT trigger that fills them,
whatever the INSERT said. They are recorded, not hashed."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from test_db2_ledger import entry

from asof import db, ledger, schema, seed

pytestmark = pytest.mark.db2

NEW = {"ANSWER_LEDGER_SESSION_COLUMNS", "ANSWER_LEDGER_SESSION_AUDIT"}
SQL_DIR = Path(__file__).resolve().parents[1] / "src" / "asof" / "sql"


def test_the_runtime_users_row_says_the_runtime_user_stored_it(settings, app_conn, test_schema):
    a = ledger.append(app_conn, entry(), test_schema)
    who = ledger.get_entry(app_conn, a.ledger_id, test_schema)["stored_by"]
    assert who["user"] == settings.asof_app_user.upper() and who["in_row_hash"] is False
    assert "ASOF_TEXT_READER" in who["roles"]  # granted to the runtime user by setup


def test_a_value_named_in_the_insert_is_overwritten(admin_conn, settings, test_schema):
    """Only procedures insert, and none names these columns; even the owner's own INSERT cannot set them."""
    db.use_schema(admin_conn, test_schema)
    db.execute(admin_conn, "INSERT INTO ANSWER_LEDGER (LEDGER_ID, REQUEST_ID, CREATED_AT, CHANNEL, DOC_ID, AS_OF_DATE, "
                           "QUESTION_REDACTED, DRAFT_REDACTED, FINAL_ANSWER, DECISION, REASON_CODE, MODEL_INFO, "
                           "PROMPT_VERSION, LATENCY_MS, VERDICTS_JSON, PREV_HASH, ROW_HASH, STORED_BY, STORED_ROLES, "
                           "STORED_CONTEXT) VALUES (999999, ?, CURRENT TIMESTAMP, 'api', 'AURELIA-CSP', CURRENT DATE, "
                           "'q', 'd', 'f', 'ESCALATED', 'R', 'm', 'p', 1, '{}', REPEAT('0', 64), REPEAT('f', 64), "
                           "'MARIA', 'ASOF_AUDITOR', 'FORGED_CONTEXT')", (str(uuid.uuid4()),))
    row = db.query(admin_conn, "SELECT STORED_BY, STORED_ROLES, STORED_CONTEXT FROM ANSWER_LEDGER "
                               "WHERE LEDGER_ID = 999999")
    admin_conn.rollback()  # never committed: the test ledger's chain stays whole
    (user, roles, context), = row
    assert user.strip() == settings.db2_admin_user.upper()
    assert "ASOF_AUDITOR" not in (roles or "") and context != "FORGED_CONTEXT"


def test_the_columns_are_outside_the_row_hash():
    """Recorded, not hashed: the procedures that compute and check ROW_HASH never read them."""
    procs = (SQL_DIR / "03_procedures.sql").read_text(encoding="utf-8")
    assert "STORED_BY" not in procs and "STORED_ROLES" not in procs and "STORED_CONTEXT" not in procs


@pytest.fixture
def old_install(admin_conn, embeddings, settings):
    """A schema installed as it was before the session columns existed."""
    name = f"ASOF_U{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name, statements=[s for s in schema.load_statements(name) if s.name not in NEW])
        seed.seed_documents(admin_conn, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    except Exception:
        schema.drop(admin_conn, name)
        raise
    yield name
    schema.drop(admin_conn, name)


def test_an_existing_ledger_gets_the_columns_with_its_rows_and_chain_intact(admin_conn, settings, old_install):
    # Each step on its own connection: a connection that ran a procedure keeps a plan lock on it, and the ALTER that
    # invalidates the procedure would wait for that connection to go away.
    with db.connection(settings, "app") as app:
        before = ledger.append(app, entry(), old_install)
    counts = schema.install(admin_conn, old_install)  # what setup does on a re-run
    assert counts["created"] >= 2
    invalid = db.query(admin_conn, "SELECT CONTROLNAME FROM SYSCAT.CONTROLS WHERE CONTROLSCHEMA = ? AND VALID <> 'Y'",
                       (old_install,))
    assert invalid == []  # the ALTER invalidated the masks; install recreated them
    with db.connection(settings, "app") as app:
        after = ledger.append(app, entry(), old_install)
        assert ledger.get_entry(app, before.ledger_id, old_install)["stored_by"] is None  # not recorded then
        assert ledger.get_entry(app, after.ledger_id, old_install)["stored_by"]["user"] == settings.asof_app_user.upper()
        assert ledger.get_entry(app, before.ledger_id, old_install)["row_hash"] == before.row_hash
        assert ledger.verify_chain(app, old_install).status == "OK"
    schema.install(admin_conn, old_install)  # and a third run changes nothing
    with db.connection(settings, "app") as app:
        assert ledger.verify_chain(app, old_install).status == "OK"
