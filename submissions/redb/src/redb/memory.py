"""Remember: solved tuning cases stored with a Db2 VECTOR embedding for similarity recall."""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any, Callable

DDL = """CREATE TABLE REDB.TUNING_MEMORY (
  CASE_ID INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  CREATED_AT TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP,
  SIGNATURE VARCHAR(4000), STMT_TEXT CLOB(1M), FIX_KIND VARCHAR(20),
  FIX_DETAIL VARCHAR(4000), GAIN_PCT DOUBLE,
  EMBEDDING VECTOR({dim}, FLOAT32)) IN REDB_TS32"""


def normalize_sql(sql: str) -> str:
    s = re.sub(r"'(?:[^']|'')*'", "?", sql)
    s = re.sub(r"\b\d+(\.\d+)?\b", "?", s)
    return re.sub(r"\s+", " ", s).strip().upper()


def signature(sql: str, tables: list[str], operators: list[str]) -> str:
    return f"SQL: {normalize_sql(sql)} | TABLES: {','.join(sorted(tables))} | OPS: {','.join(sorted(operators))}"


def hash_embed(text: str, dim: int = 768) -> list[float]:
    """Deterministic feature-hashing embedding (offline fallback). Unit length."""
    vec = [0.0] * dim
    toks = re.findall(r"[A-Z_][A-Z0-9_\.]*|\?", text.upper())
    feats = toks + [f"{a} {b}" for a, b in zip(toks, toks[1:])]
    for f in feats:
        h = int.from_bytes(hashlib.md5(f.encode()).digest()[:8], "big")
        vec[h % dim] += 1.0 if (h >> 63) & 1 else -1.0
    return l2_normalize(vec)


def l2_normalize(vec: list[float]) -> list[float]:
    n = math.sqrt(sum(v * v for v in vec))
    return [v / n for v in vec] if n else vec


def _vec_literal(vec: list[float]) -> str:
    return json.dumps([round(float(v), 6) for v in vec], separators=(",", ":"))


class Memory:
    def __init__(self, db, embed: Callable[[str], list[float]], dim: int = 768):
        self.db, self.embed, self.dim = db, embed, dim
        self.enabled, self.warning = True, None

    def ensure(self) -> None:
        try:
            exists = self.db.scalar("SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA='REDB' AND TABNAME='TUNING_MEMORY'")
            if not exists:
                self.db.execute(DDL.format(dim=self.dim))
        except Exception as e:  # VECTOR needs Db2 12.1.2+
            self.enabled, self.warning = False, f"Vector memory disabled (VECTOR unsupported?): {str(e)[:200]}"

    def remember(self, sig: str, sql: str, fix_kind: str, fix_detail: str, gain_pct: float) -> int | None:
        if not self.enabled:
            return None
        return int(self.db.scalar(
            f"""SELECT CASE_ID FROM FINAL TABLE (INSERT INTO REDB.TUNING_MEMORY
                (SIGNATURE, STMT_TEXT, FIX_KIND, FIX_DETAIL, GAIN_PCT, EMBEDDING)
                VALUES (?, ?, ?, ?, ?, VECTOR(CAST(? AS VARCHAR(32000)), {self.dim}, FLOAT32)))""",
            (sig[:4000], sql, fix_kind, fix_detail[:4000], gain_pct, _vec_literal(self.embed(sig)))))

    def search(self, sig: str, k: int = 3) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        rows = self.db.query(
            f"""SELECT CASE_ID, FIX_KIND, FIX_DETAIL, GAIN_PCT, CAST(SUBSTR(STMT_TEXT,1,2000) AS VARCHAR(2000)) AS STMT,
                VECTOR_DISTANCE(EMBEDDING, VECTOR(CAST(? AS VARCHAR(32000)), {self.dim}, FLOAT32), COSINE) AS DIST
                FROM REDB.TUNING_MEMORY ORDER BY DIST ASC FETCH FIRST {int(k)} ROWS ONLY""",
            (_vec_literal(self.embed(sig)),))
        return [{"case_id": r["CASE_ID"], "fix_kind": r["FIX_KIND"], "fix_detail": r["FIX_DETAIL"],
                 "gain_pct": r["GAIN_PCT"], "sql": r["STMT"], "similarity": round(1 - float(r["DIST"]), 3)}
                for r in rows]
