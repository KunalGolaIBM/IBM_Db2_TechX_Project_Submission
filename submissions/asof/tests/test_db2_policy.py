"""Db2 integration: as-of retrieval, replay, constraints and least privilege (schema ASOF_TEST)."""

from __future__ import annotations

import json
import time
from datetime import date

import pytest

from asof import db, seed
from asof.embeddings import DIM
from asof.retriever import AsOfClauseRetriever, clauses_as_of

pytestmark = pytest.mark.db2

DOC = "AURELIA-CSP"
CLAIM = "You can apply for the bereavement discount retroactively within 90 days of ticket issue."


def versions(conn, vec, day, schema, k=3, system_time=None):
    return {c.clause_id: c.version_label for c in clauses_as_of(conn, vec, day, DOC, k, system_time, schema)}


def test_same_query_returns_brv002_v1_in_march_and_v2_in_june(app_conn, embeddings, test_schema):
    vec = embeddings.embed_query(CLAIM)
    march = clauses_as_of(app_conn, vec, date(2026, 3, 10), DOC, 3, schema=test_schema)
    june = clauses_as_of(app_conn, vec, date(2026, 6, 2), DOC, 3, schema=test_schema)
    assert (march[0].clause_id, march[0].version_label) == ("BRV-002", "v1")
    assert (june[0].clause_id, june[0].version_label) == ("BRV-002", "v2")
    assert march[0].rule["retroactive_allowed"] is False and june[0].rule["request_window_days"] == 90
    assert march[0].distance <= march[-1].distance  # nearest first


@pytest.mark.parametrize("day, label", [(date(2026, 4, 30), "v1"), (date(2026, 5, 1), "v2")])
def test_version_boundary_is_exact(app_conn, embeddings, test_schema, day, label):
    assert versions(app_conn, embeddings.embed_query(CLAIM), day, test_schema)["BRV-002"] == label


def test_no_clause_before_policy_start(app_conn, embeddings, test_schema):
    assert clauses_as_of(app_conn, embeddings.embed_query(CLAIM), date(2025, 12, 31), DOC, 3, schema=test_schema) == []


def test_langchain_retriever_interface(settings, embeddings, test_schema, app_conn):
    retriever = AsOfClauseRetriever(connect=lambda: db.connect(settings, "app"), embeddings=embeddings,
                                    doc_id=DOC, as_of=date(2026, 3, 10), k=2, schema_name=test_schema)
    docs = retriever.invoke(CLAIM)
    assert docs[0].metadata["clause_id"] == "BRV-002" and docs[0].metadata["version"] == "v1"
    assert docs[0].metadata["bus_end"] == "2026-05-01"


def test_replay_shows_what_the_database_held_before_a_change(admin_conn, app_conn, embeddings, test_schema):
    """FOR SYSTEM_TIME AS OF: after a change, replay still returns the old text for the old moment."""
    vec = embeddings.embed_query("Pets in the cabin fee")
    before = db.query(admin_conn, "SELECT CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1")[0][0]
    time.sleep(1.1)
    db.use_schema(admin_conn, test_schema)
    db.execute(admin_conn, "UPDATE POLICY_CLAUSE FOR PORTION OF BUSINESS_TIME FROM ? TO ? "
                           "SET CLAUSE_TEXT = ?, RULE_JSON = ?, VERSION_LABEL = ? WHERE CLAUSE_ID = ?",
               ("2026-12-01", "9999-12-31", "Small cats and dogs may travel in the cabin. The pet fee is $125 each way.",
                json.dumps({"pet_fee_usd": 125}), "v2", "PET-001"))
    admin_conn.commit()
    now = {c.clause_id: c for c in clauses_as_of(app_conn, vec, date(2026, 12, 15), DOC, 4, schema=test_schema)}
    then = {c.clause_id: c for c in clauses_as_of(app_conn, vec, date(2026, 12, 15), DOC, 4, before, test_schema)}
    assert now["PET-001"].rule["pet_fee_usd"] == 125 and now["PET-001"].version_label == "v2"
    assert then["PET-001"].rule["pet_fee_usd"] == 100 and then["PET-001"].version_label == "v1"
    # The change applies from 2026-12-01 only: a November trip still gets v1 today.
    assert versions(app_conn, vec, date(2026, 11, 20), test_schema, 4)["PET-001"] == "v1"


def test_rule_json_must_be_valid(admin_conn, test_schema):
    with pytest.raises(db.DatabaseError) as err:
        db.use_schema(admin_conn, test_schema)
        db.execute(admin_conn, "INSERT INTO POLICY_CLAUSE (CLAUSE_ID, DOC_ID, AREA, TITLE, VERSION_LABEL, "
                               "CLAUSE_TEXT, RULE_JSON, EMBEDDING, BUS_START, BUS_END) VALUES "
                               "(?, ?, ?, ?, ?, ?, ?, VECTOR(?, 384, FLOAT32), ?, ?)",
                   ("TST-001", DOC, "pets", "t", "v1", "x", "{not json", db.vector_literal([0.0] * DIM),
                    "2026-01-01", "2026-02-01"))
    admin_conn.rollback()
    assert err.value.sqlstate == "23513"


def test_overlapping_versions_are_rejected_by_db2(admin_conn, test_schema):
    """PRIMARY KEY (CLAUSE_ID, BUSINESS_TIME WITHOUT OVERLAPS): two versions cannot both apply."""
    with pytest.raises(db.DatabaseError) as err:
        db.use_schema(admin_conn, test_schema)
        db.execute(admin_conn, "INSERT INTO POLICY_CLAUSE (CLAUSE_ID, DOC_ID, AREA, TITLE, VERSION_LABEL, "
                               "CLAUSE_TEXT, RULE_JSON, EMBEDDING, BUS_START, BUS_END) VALUES "
                               "(?, ?, ?, ?, ?, ?, ?, VECTOR(?, 384, FLOAT32), ?, ?)",
                   ("BRV-002", DOC, "bereavement", "t", "v9", "x", "{}", db.vector_literal([0.0] * DIM),
                    "2026-04-01", "2026-06-01"))
    admin_conn.rollback()
    assert err.value.sqlstate == "23505"


def test_unknown_doc_or_injection_string_returns_nothing(app_conn, embeddings, test_schema):
    vec = embeddings.embed_query(CLAIM)
    assert clauses_as_of(app_conn, vec, date(2026, 3, 10), "AURELIA-CSP' OR '1'='1", 3, schema=test_schema) == []


def test_seeding_is_idempotent(admin_conn, embeddings, test_schema):
    assert seed.seed_policy(admin_conn, embeddings, test_schema) == 0
    assert seed.seed_faq(admin_conn, embeddings, test_schema) == 0
    assert seed.seed_published_answers(admin_conn, test_schema) == 0


@pytest.mark.parametrize("sql, state", [
    ("UPDATE {s}.POLICY_CLAUSE SET CLAUSE_TEXT = 'x'", "42501"),
    ("DELETE FROM {s}.PUBLISHED_ANSWER", "42501"),
    ("INSERT INTO {s}.ANSWER_LEDGER (REQUEST_ID) VALUES ('x')", "42501"),
    ("UPDATE {s}.CHAIN_HEAD SET LAST_LEDGER_ID = 99", "42501"),
    ("CREATE TABLE {s}.EVIL (X INT)", "42502"),
    ("DROP TABLE {s}.POLICY_CLAUSE", "42501"),
])
def test_app_user_is_read_only(app_conn, test_schema, sql, state):
    with pytest.raises(db.DatabaseError) as err:
        db.execute(app_conn, sql.format(s=test_schema))
    assert err.value.sqlstate == state


def test_app_user_can_read_faq_store_through_db2vs(settings, embeddings, test_schema):
    conn = db.connect(settings, "app")
    try:
        store = seed.faq_store(conn, embeddings, test_schema)
        hit = store.similarity_search("Can I get a bereavement fare after I travelled?", k=1)[0]
        assert hit.metadata["faq_id"] == "FAQ-01"
    finally:
        conn.close()
