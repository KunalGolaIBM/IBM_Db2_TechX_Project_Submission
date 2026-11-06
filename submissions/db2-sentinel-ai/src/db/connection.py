"""
Database connection factory and execution layer for Db2 Sentinel AI.
Supports dual-mode execution:
1. Native IBM Db2 (via ibm_db and SQLAlchemy ibm_db_sa) with VECTOR(dim, FLOAT32) and VECTOR_DISTANCE.
2. High-fidelity local emulation engine for zero-setup execution and local tests.
"""

import os
import json
import sqlite3
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from src.config import (
    DB2_MODE,
    DB2_DATABASE,
    DB2_HOSTNAME,
    DB2_PORT,
    DB2_UID,
    DB2_PWD,
    BASE_DIR,
    get_db2_conn_string,
)
from src.utils.embeddings import EmbeddingService

logger = logging.getLogger("Db2Sentinel.DB")


class Db2ConnectionManager:
    """Manages database connectivity, dual-mode execution, and vector search."""

    def __init__(self):
        self.active_mode = "emulated"
        self.live_conn = None
        self.sqlite_conn = None
        self._init_connection()

    def _init_connection(self):
        """Attempts connection to real IBM Db2; falls back to emulated engine if unavailable."""
        if DB2_MODE in ("live", "auto"):
            try:
                import ibm_db
                conn_str = get_db2_conn_string()
                logger.info(f"Attempting connection to IBM Db2 at {DB2_HOSTNAME}:{DB2_PORT}/{DB2_DATABASE}...")
                self.live_conn = ibm_db.connect(conn_str, "", "")
                if self.live_conn:
                    self.active_mode = "live"
                    logger.info("Successfully established connection to IBM Db2 (Live Mode).")
                    return
            except Exception as e:
                logger.warning(f"Could not connect to live IBM Db2 ({e}). Switching to High-Fidelity Local Engine.")

        # Initialize High-Fidelity Local Engine
        self.active_mode = "emulated"
        db_file = BASE_DIR / "sentinel_local.db"
        self.sqlite_conn = sqlite3.connect(str(db_file), check_same_thread=False)
        self.sqlite_conn.row_factory = sqlite3.Row

        # Register custom cosine distance UDF matching Db2's VECTOR_DISTANCE(..., 'COSINE')
        def cosine_distance_udf(vec1_json: str, vec2_json: str) -> float:
            try:
                v1 = json.loads(vec1_json) if isinstance(vec1_json, str) else vec1_json
                v2 = json.loads(vec2_json) if isinstance(vec2_json, str) else vec2_json
                sim = EmbeddingService.cosine_similarity(v1, v2)
                return float(1.0 - sim)  # distance = 1 - similarity
            except Exception:
                return 1.0

        self.sqlite_conn.create_function("VECTOR_DISTANCE", 2, cosine_distance_udf)
        logger.info(f"Initialized Db2 High-Fidelity Local Engine at {db_file}")

    def execute_query(self, sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Executes a SELECT query and returns a list of dictionaries."""
        if self.active_mode == "live" and self.live_conn:
            import ibm_db
            try:
                stmt = ibm_db.prepare(self.live_conn, sql)
                ibm_db.execute(stmt, params)
                results = []
                row = ibm_db.fetch_assoc(stmt)
                while row:
                    results.append(dict(row))
                    row = ibm_db.fetch_assoc(stmt)
                return results
            except Exception as e:
                logger.error(f"Live Db2 execute_query error: {e}")
                raise e
        else:
            # Emulated mode
            # Translate Db2-specific syntax if necessary
            clean_sql = sql
            # Replace Db2 FETCH FIRST n ROWS ONLY with LIMIT n
            if "FETCH FIRST" in clean_sql.upper() and "ROWS ONLY" in clean_sql.upper():
                import re
                clean_sql = re.sub(
                    r"FETCH FIRST (\d+) ROWS ONLY",
                    r"LIMIT \1",
                    clean_sql,
                    flags=re.IGNORECASE,
                )
            cursor = self.sqlite_conn.cursor()
            cursor.execute(clean_sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def execute_update(self, sql: str, params: tuple = ()) -> int:
        """Executes an INSERT, UPDATE, or DELETE statement with transactional commit."""
        if self.active_mode == "live" and self.live_conn:
            import ibm_db
            try:
                stmt = ibm_db.prepare(self.live_conn, sql)
                ibm_db.execute(stmt, params)
                return ibm_db.num_rows(stmt)
            except Exception as e:
                logger.error(f"Live Db2 execute_update error: {e}")
                raise e
        else:
            cursor = self.sqlite_conn.cursor()
            cursor.execute(sql, params)
            self.sqlite_conn.commit()
            return cursor.rowcount

    def execute_script(self, ddl_script: str):
        """Executes multiple DDL statements."""
        if self.active_mode == "live" and self.live_conn:
            import ibm_db
            for stmt_str in ddl_script.split(";"):
                stmt_str = stmt_str.strip()
                if stmt_str:
                    try:
                        ibm_db.exec_immediate(self.live_conn, stmt_str)
                    except Exception as e:
                        logger.warning(f"Live Db2 DDL notice for statement '{stmt_str[:40]}...': {e}")
        else:
            self.sqlite_conn.executescript(ddl_script)
            self.sqlite_conn.commit()

    def vector_search_typologies(
        self, query_vector: List[float], top_k: int = 3, min_similarity: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Executes semantic vector similarity search over AML typologies.
        In live Db2: uses native VECTOR_DISTANCE(EMBEDDING, ?, 'COSINE').
        In emulated: uses SQLite UDF with vector cosine distance.
        """
        if self.active_mode == "live" and self.live_conn:
            # Native IBM Db2 12.1+ Vector Search
            sql = f"""
            SELECT TYPOLOGY_ID, CODE, TITLE, CATEGORY, RED_FLAGS,
                   VECTOR_DISTANCE(EMBEDDING, ?, 'COSINE') AS DISTANCE
            FROM AML_TYPOLOGIES
            ORDER BY DISTANCE ASC
            FETCH FIRST {top_k} ROWS ONLY
            """
            vec_param = json.dumps(query_vector)
            rows = self.execute_query(sql, (vec_param,))
            results = []
            for r in rows:
                sim = 1.0 - float(r.get("DISTANCE", 1.0))
                if sim >= min_similarity:
                    r["SIMILARITY"] = round(sim, 4)
                    results.append(r)
            return results
        else:
            # Emulated search
            sql = """
            SELECT TYPOLOGY_ID, CODE, TITLE, CATEGORY, RED_FLAGS, EMBEDDING
            FROM AML_TYPOLOGIES
            """
            rows = self.execute_query(sql)
            scored = []
            for r in rows:
                raw_emb = r.get("EMBEDDING")
                if isinstance(raw_emb, str):
                    emb = json.loads(raw_emb)
                else:
                    emb = raw_emb
                sim = EmbeddingService.cosine_similarity(query_vector, emb)
                if sim >= min_similarity:
                    r_copy = dict(r)
                    del r_copy["EMBEDDING"]
                    r_copy["SIMILARITY"] = round(sim, 4)
                    scored.append(r_copy)
            scored.sort(key=lambda x: x["SIMILARITY"], reverse=True)
            return scored[:top_k]

    def close(self):
        """Closes active database connections."""
        if self.live_conn:
            import ibm_db
            try:
                ibm_db.close(self.live_conn)
            except Exception:
                pass
        if self.sqlite_conn:
            self.sqlite_conn.close()


# Global Singleton Manager
_db_manager = None


def get_db_manager() -> Db2ConnectionManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = Db2ConnectionManager()
    return _db_manager
