"""Db2 integration: chain checkpoints and VERIFY_CHAIN_FROM_CHECKPOINT (12_chain_checkpoints.sql).

An incremental verify recomputes the checkpoint row and every row after it, and records the new position. It does not
recompute rows before the checkpoint: one test pins that boundary, which only the full VERIFY_CHAIN covers.
"""

from __future__ import annotations

import uuid

import pytest
from test_db2_ledger import entry

from asof import db, ledger, schema, seed

pytestmark = pytest.mark.db2


@pytest.fixture
def chain(admin_conn, embeddings, settings):
    """A private ledger, and helpers: append rows, verify as the runtime user, tamper as the owner."""
    name = f"ASOF_K{uuid.uuid4().hex[:6].upper()}"
    try:
        schema.install(admin_conn, name)
        seed.seed_documents(admin_conn, name)
        seed.seed_chain_head(admin_conn, name)
        seed.seed_faq(admin_conn, embeddings, name)
        schema.apply_grants(admin_conn, settings.asof_app_user, settings.asof_editor_user, name)
    except Exception:
        schema.drop(admin_conn, name)
        raise
    app = db.connect(settings, "app")

    class Chain:
        schema_name = name

        def append(self, n: int) -> None:
            for _ in range(n):
                ledger.append(app, entry(), name)

        def verify(self, full: bool = False) -> ledger.CheckpointStatus:
            return ledger.verify_from_checkpoint(app, name, full=full, requested_by="auditor-1")

        def full_scan(self) -> ledger.ChainStatus:
            return ledger.verify_chain(app, name)

        def checkpoints(self) -> list[dict]:
            return ledger.checkpoints(app, name)

        def row_hash(self, ledger_id: int) -> str:
            row = ledger.get_entry(app, ledger_id, name)
            assert row is not None
            return str(row["row_hash"])

        def tamper(self, ledger_id: int) -> None:
            """The owner drops the update trigger and edits a row's text, leaving its stored hashes alone."""
            db.execute(admin_conn, f"DROP TRIGGER {db.ident(name)}.ANSWER_LEDGER_NO_UPDATE")
            db.use_schema(admin_conn, name)
            db.execute(admin_conn, "UPDATE ANSWER_LEDGER SET FINAL_ANSWER = 'Yes, refunds after travel.' "
                                   "WHERE LEDGER_ID = ?", (ledger_id,))
            admin_conn.commit()

    yield Chain()
    app.close()
    schema.drop(admin_conn, name)


def test_the_first_verify_is_full_and_the_next_starts_at_its_checkpoint(chain):
    chain.append(5)
    first = chain.verify()
    assert (first.status, first.checked, first.from_id) == ("OK", 5, 1) and first.checkpoint_id
    chain.append(3)
    second = chain.verify()
    assert (second.status, second.checked, second.from_id) == ("OK", 4, 5)  # the checkpoint row, then rows 6 to 8
    latest, earlier = chain.checkpoints()[:2]
    assert (latest["checkpoint_id"], latest["ledger_id"], latest["from_ledger_id"], latest["rows_checked"],
            latest["kind"], latest["requested_by"]) == (second.checkpoint_id, 8, 5, 4, "INCREMENTAL", "auditor-1")
    assert (earlier["ledger_id"], earlier["kind"]) == (5, "FULL")
    assert latest["row_hash"] == chain.row_hash(8) and latest["verified_by"] and latest["verified_at"] is not None


def test_with_nothing_new_it_rechecks_the_checkpoint_row_and_records_the_run(chain):
    chain.append(2)
    chain.verify()
    again = chain.verify()
    assert (again.status, again.checked, again.from_id) == ("OK", 1, 2) and again.checkpoint_id


def test_an_empty_ledger_verifies_and_records_nothing(chain):
    status = chain.verify()
    assert (status.status, status.checked, status.checkpoint_id) == ("OK", 0, None)
    assert chain.checkpoints() == []


def test_a_row_edited_after_the_checkpoint_is_caught_and_no_checkpoint_is_written(chain):
    chain.append(3)
    chain.verify()
    chain.append(3)
    chain.tamper(5)
    status = chain.verify()
    assert (status.status, status.first_bad, status.checkpoint_id) == ("BROKEN", 5, None)
    assert "content" in (status.detail or "") and len(chain.checkpoints()) == 1


def test_the_checkpoint_row_itself_is_rechecked(chain):
    chain.append(4)
    chain.verify()
    chain.tamper(4)
    status = chain.verify()
    assert (status.status, status.first_bad, status.from_id) == ("BROKEN", 4, 4)


def test_a_row_before_the_checkpoint_is_not_rechecked_only_the_full_scan_catches_it(chain):
    """The documented boundary: an owner who edits an old row without touching its hashes is invisible to the
    incremental verify. VERIFY_CHAIN, and a full verify from the first row, catch it."""
    chain.append(6)
    chain.verify()
    chain.tamper(2)
    assert chain.verify().status == "OK"  # rows 1 to 5 were not recomputed
    full = chain.full_scan()
    assert (full.status, full.first_bad) == ("BROKEN", 2)
    from_start = chain.verify(full=True)
    assert (from_start.status, from_start.first_bad, from_start.from_id) == ("BROKEN", 2, 1)


def test_checkpoints_are_append_only_and_written_only_by_the_procedure(chain, admin_conn, settings):
    chain.append(1)
    chain.verify()
    db.use_schema(admin_conn, chain.schema_name)
    for sql in ("UPDATE CHAIN_CHECKPOINT SET LEDGER_ID = 99", "DELETE FROM CHAIN_CHECKPOINT"):
        with pytest.raises(db.DatabaseError) as err:
            db.execute(admin_conn, sql)
        admin_conn.rollback()
        assert err.value.sqlstate == "75001"
    with db.connection(settings, "app") as app:
        db.use_schema(app, chain.schema_name)
        with pytest.raises(db.DatabaseError) as err:
            db.execute(app, "INSERT INTO CHAIN_CHECKPOINT (LEDGER_ID, ROW_HASH, FROM_LEDGER_ID, ROWS_CHECKED, KIND) "
                            "VALUES (1, ?, 1, 1, 'FULL')", ("0" * 64,))
        assert err.value.sqlstate == "42501"


def test_only_a_verifier_who_reads_the_text_may_run_it(chain, admin_conn, settings):
    """The owner holds EXECUTE but reads the text masked: hashing '[masked]' would report a false break, so Db2
    refuses (75030). The policy editor holds no EXECUTE at all (42501)."""
    chain.append(1)
    with pytest.raises(db.DatabaseError) as err:
        ledger.verify_from_checkpoint(admin_conn, chain.schema_name)
    assert err.value.sqlstate == "75030"
    with db.connection(settings, "editor") as editor:
        with pytest.raises(db.DatabaseError) as err:
            ledger.verify_from_checkpoint(editor, chain.schema_name)
    assert err.value.sqlstate == "42501"
