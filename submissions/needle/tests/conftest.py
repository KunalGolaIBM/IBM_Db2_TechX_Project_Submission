"""Shared skip guards so DB tests stay green on the 2,000-row sample corpus and on hosts without Ollama.

Full-corpus expectations (vector index chosen, router picks the approximate path) only hold above roughly 20k rows,
where Db2's cost model starts choosing the DiskANN index (docs/evidence/g1_vector_index.md).
"""
from __future__ import annotations

import functools
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FULL_CORPUS_MIN_ROWS = 20000


def _env() -> dict:
    vals = dict(os.environ)
    try:
        from dotenv import dotenv_values
        vals = {**dotenv_values(ROOT / ".env"), **vals}
    except Exception:
        pass
    return vals


@functools.lru_cache(maxsize=1)
def corpus_rows() -> int | None:
    """Row count of NEEDLE.ADV_DOC as the admin user (RCAC full-access row), or None if Db2 is unreachable."""
    env = _env()
    try:
        import ibm_db
        conn = ibm_db.connect(
            f"DATABASE={env.get('DB2_DATABASE', 'VECDB')};HOSTNAME={env.get('DB2_HOST', 'localhost')};"
            f"PORT={env.get('DB2_PORT', '50000')};PROTOCOL=TCPIP;", env.get("DB2_USER", "db2inst1"),
            env.get("DB2_PASSWORD", ""))
        try:
            stmt = ibm_db.exec_immediate(conn, "SELECT COUNT(*) FROM NEEDLE.ADV_DOC")
            return int(ibm_db.fetch_tuple(stmt)[0])
        finally:
            ibm_db.close(conn)
    except Exception:
        return None


def skip_unless_full_corpus() -> None:
    n = corpus_rows()
    if n is not None and n < FULL_CORPUS_MIN_ROWS:
        pytest.skip(f"needs the full corpus (>= {FULL_CORPUS_MIN_ROWS} rows); ADV_DOC has {n} "
                    "(sample mode: the optimizer does not choose the vector index at this size)")


@functools.lru_cache(maxsize=1)
def ollama_up() -> bool:
    url = _env().get("OLLAMA_URL", "http://localhost:11434").rstrip("/") + "/api/tags"
    try:
        import requests
        return requests.get(url, timeout=3).ok
    except Exception:
        return False


def skip_unless_ollama() -> None:
    if not ollama_up():
        pytest.skip("needs a reachable Ollama server (query embeddings)")
