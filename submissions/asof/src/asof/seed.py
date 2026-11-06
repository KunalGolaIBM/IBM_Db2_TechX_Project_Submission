"""Load the fictional Aurelia Air data into Db2. Every loader is a no-op when its table
already has data, so setup can be re-run without duplicating or rewriting history."""

from __future__ import annotations

import json
from importlib import resources

import ibm_db_dbi
from langchain_core.embeddings import Embeddings

from . import db
from .corpus import load_corpus
from .embeddings import DIM, clause_embedding_text

FAQ_TABLE = "FAQ_KB"

# Every statement below is a literal. Names are unqualified: db.use_schema() binds the schema.
SQL_COUNT_CLAUSES = "SELECT COUNT(*) FROM POLICY_CLAUSE"
SQL_COUNT_HEAD = "SELECT COUNT(*) FROM CHAIN_HEAD"
SQL_COUNT_PUBLISHED = "SELECT COUNT(*) FROM PUBLISHED_ANSWER"
SQL_COUNT_FAQ = "SELECT COUNT(*) FROM FAQ_KB"
SQL_INSERT_DOC = "INSERT INTO POLICY_DOC (DOC_ID, TITLE, OWNER_TEAM, SOURCE_NOTE) VALUES (?, ?, ?, ?)"
SQL_INSERT_CLAUSE = ("INSERT INTO POLICY_CLAUSE (CLAUSE_ID, DOC_ID, AREA, TITLE, VERSION_LABEL, CLAUSE_TEXT, RULE_JSON, "
                     "EMBEDDING, CHANGE_NOTE, BUS_START, BUS_END) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, VECTOR(?, 384, FLOAT32), ?, ?, ?)")
# Same row, but Db2 computes the embedding itself with the registered in-database model.
SQL_INSERT_CLAUSE_INDB = ("INSERT INTO POLICY_CLAUSE (CLAUSE_ID, DOC_ID, AREA, TITLE, VERSION_LABEL, CLAUSE_TEXT, "
                          "RULE_JSON, EMBEDDING, CHANGE_NOTE, BUS_START, BUS_END) "
                          "VALUES (?, ?, ?, ?, ?, ?, ?, TO_EMBEDDING(CAST(? AS VARCHAR(4300)) USING EMBEDDER), ?, ?, ?)")
SQL_INSERT_HEAD = "INSERT INTO CHAIN_HEAD (HEAD_ID, LAST_LEDGER_ID, LAST_HASH) VALUES (1, 0, ?)"
SQL_INSERT_PUBLISHED = ("INSERT INTO PUBLISHED_ANSWER (ANSWER_ID, DOC_ID, QUESTION, ANSWER_TEXT, CITED_CLAUSE_ID, "
                        "CITED_VERSION, CITED_BUS_START, APPLIES_FROM, APPLIES_TO) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)")
assert DIM == 384, "SQL_INSERT_CLAUSE is written for 384-dimension embeddings"


def _data(name: str) -> dict:
    return json.loads((resources.files("asof") / "data" / name).read_text(encoding="utf-8"))


def _count(conn: ibm_db_dbi.Connection, schema: str, sql: str) -> int:
    db.use_schema(conn, schema)
    return int(db.query(conn, sql)[0][0])


def seed_policy(conn: ibm_db_dbi.Connection, embeddings: Embeddings, schema: str = db.SCHEMA,
                in_db: bool = False) -> int:
    """Insert every clause version with its embedding. Returns rows inserted (0 if already seeded).

    With in_db=True, Db2 embeds each clause itself (TO_EMBEDDING ... USING EMBEDDER); otherwise
    the vectors are computed here with the same model and bound as parameters.
    """
    if _count(conn, schema, SQL_COUNT_CLAUSES) > 0:
        return 0
    corpus = load_corpus()
    for d in corpus.documents:
        db.execute(conn, SQL_INSERT_DOC, (d.doc_id, d.title, d.owner_team, d.source_note))
    rows = [(c, v) for c in corpus.clauses for v in c.versions]
    texts = [clause_embedding_text(c.title, v.clause_text) for c, v in rows]
    vectors = [db.vector_literal(x) for x in embeddings.embed_documents(texts)] if not in_db else texts
    for (c, v), vec in zip(rows, vectors, strict=True):
        db.execute(conn, SQL_INSERT_CLAUSE_INDB if in_db else SQL_INSERT_CLAUSE,
                   (c.clause_id, c.doc_id, c.area, c.title, v.version_label, v.clause_text,
                    json.dumps(v.rule, sort_keys=True), vec, "Initial policy load", v.bus_start, v.bus_end))
    conn.commit()
    return len(rows)


def seed_chain_head(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> int:
    if _count(conn, schema, SQL_COUNT_HEAD) > 0:
        return 0
    db.execute(conn, SQL_INSERT_HEAD, ("0" * 64,))
    conn.commit()
    return 1


def seed_published_answers(conn: ibm_db_dbi.Connection, schema: str = db.SCHEMA) -> int:
    if _count(conn, schema, SQL_COUNT_PUBLISHED) > 0:
        return 0
    answers = _data("published_answers.json")["answers"]
    corpus = load_corpus()
    for a in answers:
        cited = next((v for c in corpus.clauses if c.clause_id == a["cited_clause_id"] for v in c.versions
                      if v.bus_start.isoformat() == a["cited_bus_start"]), None)
        if cited is None:
            raise ValueError(f"{a['answer_id']} cites a clause version that does not exist")
        db.execute(conn, SQL_INSERT_PUBLISHED,
                   (a["answer_id"], a["doc_id"], a["question"], a["answer_text"], a["cited_clause_id"],
                    cited.version_label, a["cited_bus_start"], a["applies_from"], a["applies_to"]))
    conn.commit()
    return len(answers)


def faq_store(conn: ibm_db_dbi.Connection, embeddings: Embeddings, schema: str = db.SCHEMA):
    """The naive assistant's knowledge base, stored with the official langchain-db2 DB2VS.

    DB2VS creates its table on first use, which only the owner can do, so setup builds it
    with the admin connection and the app user gets SELECT on it.
    """
    from langchain_community.vectorstores.utils import DistanceStrategy
    from langchain_db2.db2vs import DB2VS

    # DB2VS builds its own SQL from this table name, so it must be a validated identifier pair.
    return DB2VS(embedding_function=embeddings, table_name=db.validate_schema(schema) + "." + db.ident(FAQ_TABLE), client=conn,
                 distance_strategy=DistanceStrategy.COSINE)


def seed_faq(conn: ibm_db_dbi.Connection, embeddings: Embeddings, schema: str = db.SCHEMA) -> int:
    store = faq_store(conn, embeddings, schema)
    if _count(conn, schema, SQL_COUNT_FAQ) > 0:
        return 0
    entries = _data("faq_kb.json")["entries"]
    store.add_texts(
        texts=[f"Q: {e['question']}\nA: {e['answer']}" for e in entries],
        metadatas=[{"faq_id": e["faq_id"], "topic": e["topic"]} for e in entries],
        ids=[e["faq_id"] for e in entries],
    )
    return len(entries)
