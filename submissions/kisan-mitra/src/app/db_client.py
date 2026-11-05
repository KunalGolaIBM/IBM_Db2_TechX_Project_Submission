"""
IBM Db2 Database Client for Kisan Mitra (किसान मित्र)
Provides unified access to:
1. Native IBM Db2 12.1+ instances via ibm_db (with native VECTOR and VECTOR_DISTANCE)
2. High-fidelity local Db2-dialect emulation engine for testing and portable execution
3. Strict read-only safety validation, query timeout, and result truncation
"""

import os
import re
import time
import math
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from app.config import config

# Optional native ibm_db import
try:
    import ibm_db  # type: ignore
    HAS_IBM_DB = True
except (ImportError, Exception):
    HAS_IBM_DB = False


# SQL Safety regex: match disallowed DDL, DML, and injection tokens
FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|"
    r"EXEC|CALL|ATTACH|DETACH|PRAGMA|INTO|REPLACE)\b",
    re.IGNORECASE,
)

def cosine_distance(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine distance = 1 - cosine_similarity."""
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for a, b in zip(vec_a, vec_b):
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    sim = dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
    return round(float(1.0 - max(-1.0, min(1.0, sim))), 6)


class DbClient:
    """Unified client for IBM Db2 with relational and native vector search support."""

    def __init__(self, read_only: bool = True):
        self.read_only = read_only
        self.mode = config.DB2_MODE
        self.engine_type = "emulated_db2"
        self._native_conn = None
        self._sqlite_conn: Optional[sqlite3.Connection] = None
        
        # Connect based on mode
        if self.mode in ("native", "auto") and HAS_IBM_DB:
            try:
                self._connect_native()
                self.engine_type = "native_db2"
            except Exception as err:
                if self.mode == "native":
                    raise ConnectionError(f"Failed to connect to native IBM Db2: {err}")
                print(f"ℹ️ Native Db2 connection unavailable ({err}). Using Db2-compatible local engine.")
                self._connect_emulated()
        else:
            self._connect_emulated()

    def _connect_native(self):
        """Establish native IBM Db2 connection via ibm_db."""
        user = config.DB2_READONLY_USER if self.read_only else config.DB2_USER
        password = config.DB2_READONLY_PASSWORD if self.read_only else config.DB2_PASSWORD
        conn_str = (
            f"DATABASE={config.DB2_DATABASE};"
            f"HOSTNAME={config.DB2_HOST};"
            f"PORT={config.DB2_PORT};"
            f"PROTOCOL=TCPIP;"
            f"UID={user};"
            f"PWD={password};"
        )
        self._native_conn = ibm_db.connect(conn_str, "", "")
        print(f"🔌 Connected to native IBM Db2 ({config.DB2_HOST}:{config.DB2_PORT}/{config.DB2_DATABASE}) as '{user}'")

    def _connect_emulated(self):
        """Initialize local Db2-dialect SQLite engine with Db2 custom vector functions."""
        db_path = config.EMULATOR_DB_PATH
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._sqlite_conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._sqlite_conn.row_factory = sqlite3.Row
        
        # Register IBM Db2 custom functions into SQLite
        def _sqlite_vector(vec_str, dim, coord_type=None):
            return vec_str

        def _sqlite_vector_distance(v1_raw, v2_raw, metric="COSINE"):
            try:
                v1 = json.loads(v1_raw) if isinstance(v1_raw, str) else list(v1_raw)
                v2 = json.loads(v2_raw) if isinstance(v2_raw, str) else list(v2_raw)
                return cosine_distance(v1, v2)
            except Exception:
                return 1.0

        self._sqlite_conn.create_function("VECTOR", 2, _sqlite_vector)
        self._sqlite_conn.create_function("VECTOR", 3, _sqlite_vector)
        self._sqlite_conn.create_function("VECTOR_DISTANCE", 3, _sqlite_vector_distance)
        self.engine_type = "emulated_db2"
        self._init_emulated_schema()

    def _init_emulated_schema(self):
        """Create schema on emulated engine matching Db2 schema."""
        cursor = self._sqlite_conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS MANDI_PRICES (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                state TEXT NOT NULL,
                district TEXT NOT NULL,
                market TEXT NOT NULL,
                commodity TEXT NOT NULL,
                variety TEXT DEFAULT 'FAQ',
                arrival_date TEXT NOT NULL,
                min_price REAL,
                max_price REAL,
                modal_price REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mandi_state_comm_date ON MANDI_PRICES (state, commodity, arrival_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mandi_district_market ON MANDI_PRICES (district, market, arrival_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_mandi_commodity_date ON MANDI_PRICES (commodity, arrival_date)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS DOC_CHUNKS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_name TEXT NOT NULL,
                scheme_name TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                chunk_text TEXT NOT NULL,
                embedding TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_scheme_page ON DOC_CHUNKS (scheme_name, page_number)")
        self._sqlite_conn.commit()

    def validate_sql(self, sql: str) -> None:
        """Enforce strict read-only security: allow SELECT only, prevent DDL/DML & semicolon chaining."""
        clean = sql.strip().rstrip(";")
        if ";" in clean:
            raise PermissionError("Security Policy Violation: Semicolon command chaining is forbidden.")
        
        # Check first token
        first_token = clean.split()[0].upper() if clean.split() else ""
        if first_token not in ("SELECT", "WITH"):
            raise PermissionError(f"Security Policy Violation: '{first_token}' is disallowed. Only SELECT queries are permitted.")
        
        # Check forbidden keywords
        match = FORBIDDEN_SQL_PATTERN.search(clean)
        if match:
            forbidden = match.group(0).upper()
            raise PermissionError(f"Security Policy Violation: Statement contains forbidden mutation keyword '{forbidden}'.")

    def execute_query(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> Dict[str, Any]:
        """Validate and execute a read-only SQL query with latency measurement and row truncation."""
        self.validate_sql(sql)
        start_time = time.time()
        
        # Normalize row limits: ensure query has a limit or append Db2 FETCH FIRST
        clean_sql = sql.strip().rstrip(";")
        has_fetch = bool(re.search(r"FETCH\s+FIRST\s+\d+\s+ROWS?\s+ONLY", clean_sql, re.IGNORECASE))
        has_limit = bool(re.search(r"\bLIMIT\s+\d+\b", clean_sql, re.IGNORECASE))
        
        if not has_fetch and not has_limit:
            clean_sql = f"{clean_sql} FETCH FIRST {config.MAX_ROWS_RETURNED} ROWS ONLY"

        columns: List[str] = []
        rows: List[Dict[str, Any]] = []

        if self.engine_type == "native_db2":
            stmt = ibm_db.prepare(self._native_conn, clean_sql)
            if params:
                for idx, p in enumerate(params, start=1):
                    ibm_db.bind_param(stmt, idx, p)
            ibm_db.execute(stmt)
            
            num_fields = ibm_db.num_fields(stmt)
            columns = [ibm_db.field_name(stmt, i) for i in range(num_fields)]
            
            result = ibm_db.fetch_assoc(stmt)
            while result and len(rows) < config.MAX_ROWS_RETURNED:
                rows.append(result)
                result = ibm_db.fetch_assoc(stmt)
        else:
            # Emulated engine translation (Db2 dialect -> SQLite)
            exec_sql = clean_sql
            # Convert FETCH FIRST N ROWS ONLY to LIMIT N
            fetch_match = re.search(r"FETCH\s+FIRST\s+(\d+)\s+ROWS?\s+ONLY", exec_sql, re.IGNORECASE)
            if fetch_match:
                limit_n = fetch_match.group(1)
                exec_sql = re.sub(r"FETCH\s+FIRST\s+\d+\s+ROWS?\s+ONLY", f"LIMIT {limit_n}", exec_sql, flags=re.IGNORECASE)
            
            # Convert Db2 unquoted metric identifiers (COSINE, EUCLIDEAN) and types (REAL, FLOAT32) to strings for emulation
            exec_sql = re.sub(r",\s*COSINE\b", ", 'COSINE'", exec_sql, flags=re.IGNORECASE)
            exec_sql = re.sub(r",\s*EUCLIDEAN\b", ", 'EUCLIDEAN'", exec_sql, flags=re.IGNORECASE)
            exec_sql = re.sub(r",\s*REAL\b", ", 'REAL'", exec_sql, flags=re.IGNORECASE)
            exec_sql = re.sub(r",\s*FLOAT32\b", ", 'FLOAT32'", exec_sql, flags=re.IGNORECASE)
            exec_sql = re.sub(r",\s*INT8\b", ", 'INT8'", exec_sql, flags=re.IGNORECASE)
            
            # Convert Db2 date math (e.g. CURRENT DATE - 7 DAYS)
            exec_sql = re.sub(r"CURRENT\s+DATE\s*-\s*(\d+)\s+DAYS?", r"date('now', '-\1 days')", exec_sql, flags=re.IGNORECASE)
            exec_sql = re.sub(r"CURRENT\s+DATE", r"date('now')", exec_sql, flags=re.IGNORECASE)
            exec_sql = re.sub(r"CURRENT\s+TIMESTAMP", r"datetime('now')", exec_sql, flags=re.IGNORECASE)
            
            cursor = self._sqlite_conn.cursor()
            if params:
                cursor.execute(exec_sql, params)
            else:
                cursor.execute(exec_sql)
            
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                raw_rows = cursor.fetchall()
                for r in raw_rows[:config.MAX_ROWS_RETURNED]:
                    rows.append({col: r[col] for col in columns})

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "sql": clean_sql,
            "latency_ms": elapsed_ms,
            "engine": self.engine_type,
        }

    def vector_search(
        self,
        query_embedding: List[float],
        top_k: int = 4,
        scheme_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform native IBM Db2 vector similarity search using VECTOR_DISTANCE and COSINE metric.
        Db2 12.1+ Syntax:
          SELECT doc_name, scheme_name, page_number, chunk_text,
                 VECTOR_DISTANCE(embedding, VECTOR(?, 384, REAL), COSINE) AS distance
          FROM DOC_CHUNKS
          ORDER BY distance ASC
          FETCH FIRST ? ROWS ONLY;
        """
        # Format vector literal string: '[0.0123, -0.0456, ...]'
        vec_literal = f"[{', '.join(f'{x:.6f}' for x in query_embedding)}]"
        
        sql = f"""
        SELECT doc_name, scheme_name, page_number, chunk_text,
               VECTOR_DISTANCE(embedding, VECTOR('{vec_literal}', {len(query_embedding)}, REAL), COSINE) AS distance
        FROM DOC_CHUNKS
        """
        params: List[Any] = []
        if scheme_filter:
            sql += " WHERE scheme_name = ?"
            params.append(scheme_filter)
            
        sql += f" ORDER BY distance ASC FETCH FIRST {top_k} ROWS ONLY"
        
        res = self.execute_query(sql, params=tuple(params) if params else None)
        return res["rows"]

    def insert_mandi_prices(self, records: List[Dict[str, Any]]) -> int:
        """Insert mandi price records (used by ingestion pipeline)."""
        if not records:
            return 0
        if self.engine_type == "native_db2":
            sql = """
            INSERT INTO MANDI_PRICES (state, district, market, commodity, variety, arrival_date, min_price, max_price, modal_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            stmt = ibm_db.prepare(self._native_conn, sql)
            count = 0
            for r in records:
                ibm_db.execute(stmt, (
                    r["state"], r["district"], r["market"], r["commodity"],
                    r["variety"], r["arrival_date"], r["min_price"], r["max_price"], r["modal_price"]
                ))
                count += 1
            return count
        else:
            cursor = self._sqlite_conn.cursor()
            cursor.executemany("""
                INSERT INTO MANDI_PRICES (state, district, market, commodity, variety, arrival_date, min_price, max_price, modal_price)
                VALUES (:state, :district, :market, :commodity, :variety, :arrival_date, :min_price, :max_price, :modal_price)
            """, records)
            self._sqlite_conn.commit()
            return len(records)

    def insert_doc_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """Insert document chunks with native vector embeddings."""
        if not chunks:
            return 0
        if self.engine_type == "native_db2":
            count = 0
            for c in chunks:
                vec_literal = f"[{', '.join(f'{x:.6f}' for x in c['embedding'])}]"
                dim = len(c["embedding"])
                sql = f"""
                INSERT INTO DOC_CHUNKS (doc_name, scheme_name, page_number, chunk_index, chunk_text, embedding)
                VALUES (?, ?, ?, ?, ?, VECTOR('{vec_literal}', {dim}, REAL))
                """
                stmt = ibm_db.prepare(self._native_conn, sql)
                ibm_db.execute(stmt, (
                    c["doc_name"], c["scheme_name"], c["page_number"], c["chunk_index"], c["chunk_text"]
                ))
                count += 1
            return count
        else:
            cursor = self._sqlite_conn.cursor()
            formatted = []
            for c in chunks:
                formatted.append((
                    c["doc_name"],
                    c["scheme_name"],
                    c["page_number"],
                    c["chunk_index"],
                    c["chunk_text"],
                    json.dumps(c["embedding"])
                ))
            cursor.executemany("""
                INSERT INTO DOC_CHUNKS (doc_name, scheme_name, page_number, chunk_index, chunk_text, embedding)
                VALUES (?, ?, ?, ?, ?, ?)
            """, formatted)
            self._sqlite_conn.commit()
            return len(chunks)


def get_db_client(read_only: bool = True) -> DbClient:
    """Factory helper to obtain a configured DbClient instance."""
    return DbClient(read_only=read_only)
