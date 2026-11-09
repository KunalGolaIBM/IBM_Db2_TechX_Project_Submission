"""Corpus ingestion: JSON -> Db2 (relational rules + native vectors).

Run with:  python -m src.cli seed
Idempotent: a scheme is deleted (cascading to its rules and chunks) and
re-inserted, so re-running never duplicates rows.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from . import db
from .config import DATA_DIR, settings
from .embeddings import embed_documents, vector_literal


def load_corpus() -> Dict[str, Any]:
    path = DATA_DIR / "schemes.json"
    if not path.is_file():
        raise FileNotFoundError(f"Corpus not found: {path}")
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _chunk_id(scheme_id: str, clause_ref: str, index: int) -> str:
    raw = f"{scheme_id}::{clause_ref}::{index}"
    return "".join(ch if ch.isalnum() or ch in ":_-." else "_" for ch in raw)[:96]


def _pick_grounding_chunk(scheme: Dict[str, Any], rule: Dict[str, Any],
                          chunks: List[Dict[str, Any]]) -> str | None:
    """Map a rule to the clause chunk that justifies it.

    Prefer the same page, then the same section, then the first chunk.
    Deterministic and inspectable - no embeddings involved in this link.
    """
    page = rule.get("source_page")
    for chunk in chunks:
        if page is not None and chunk.get("page_no") == page:
            return chunk["_chunk_id"]
    return chunks[0]["_chunk_id"] if chunks else None


def seed(verbose: bool = True) -> Dict[str, int]:
    corpus = load_corpus()
    schemes = corpus.get("schemes", [])
    if not schemes:
        raise ValueError("Corpus contains no schemes")

    # Prepare chunk identifiers and embed every clause in one batch.
    all_texts: List[str] = []
    for scheme in schemes:
        for index, chunk in enumerate(scheme["chunks"]):
            chunk["_chunk_id"] = _chunk_id(scheme["scheme_id"], chunk["clause_ref"], index)
            all_texts.append(chunk["text"])

    if verbose:
        print(f"[seed] embedding {len(all_texts)} clauses with {settings.embedding_model} ...")
    vectors = embed_documents(all_texts)
    if len(vectors) != len(all_texts):
        raise RuntimeError("Embedding count does not match clause count")

    cursor = 0
    counts = {"schemes": 0, "rules": 0, "chunks": 0}

    db.init_db(verbose=verbose)
    with db.connect() as conn:
        for scheme in schemes:
            scheme_id = scheme["scheme_id"]
            db.execute(conn, "DELETE FROM schemes WHERE scheme_id = ?", (scheme_id,))
            db.execute(
                conn,
                "INSERT INTO schemes (scheme_id, name, ministry, gov_level, state_code, "
                "category, status, source_url, benefit_summary) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    scheme_id,
                    scheme["name"],
                    scheme.get("ministry"),
                    scheme.get("level", "central"),
                    scheme.get("state_code", "ALL"),
                    scheme.get("category", "welfare"),
                    scheme.get("status", "ACTIVE"),
                    scheme.get("source_url"),
                    scheme.get("benefit_summary"),
                ),
            )
            counts["schemes"] += 1

            chunks = scheme["chunks"]
            for chunk in chunks:
                vector = vectors[cursor]
                cursor += 1
                db.execute(
                    conn,
                    "INSERT INTO scheme_chunks (chunk_id, scheme_id, clause_ref, section, "
                    "page_no, chunk_text, embedding) "
                    "VALUES (?, ?, ?, ?, ?, ?, VECTOR(CAST(? AS VARCHAR(32672)), "
                    f"{settings.embedding_dim}, FLOAT32))",
                    (
                        chunk["_chunk_id"],
                        scheme_id,
                        chunk["clause_ref"],
                        chunk.get("section"),
                        chunk.get("page_no"),
                        chunk["text"],
                        vector_literal(vector),
                    ),
                )
                counts["chunks"] += 1

            for rule in scheme["rules"]:
                db.execute(
                    conn,
                    "INSERT INTO scheme_rules (scheme_id, criterion_code, rule_op, value_num, "
                    "value_text, mandatory, clause_ref, source_page, chunk_id) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        scheme_id,
                        rule["criterion_code"],
                        rule["op"],
                        rule.get("num"),
                        rule.get("text"),
                        1 if rule.get("mandatory", True) else 0,
                        rule["clause_ref"],
                        rule.get("source_page"),
                        _pick_grounding_chunk(scheme, rule, chunks),
                    ),
                )
                counts["rules"] += 1

        db.audit(conn, None, "ingest", "corpus.seeded", json.dumps(counts))

    if verbose:
        print(f"[seed] done: {counts}")
    return counts
