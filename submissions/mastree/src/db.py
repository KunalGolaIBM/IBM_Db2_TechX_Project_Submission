"""
Database layer for MasteryLoop (mastree).
All IBM Db2 LUW database access and query logic lives in this module.
Adheres strictly to IBM Db2 LUW dialect rules:
- Recursive CTE with NO 'RECURSIVE' keyword
- FETCH FIRST n ROWS ONLY (no LIMIT)
- Parameterized queries with '?' markers
- Transactions with autocommit off, commit, and rollback
- Identity primary keys with IDENTITY_VAL_LOCAL()
"""

import os
import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
import ibm_db

# Load environment variables
load_dotenv()

logger = logging.getLogger("mastree.db")


def get_connection_string() -> str:
    """Build the IBM Db2 TCPIP connection string from environment variables."""
    host = os.getenv("DB2_HOST", "localhost")
    port = os.getenv("DB2_PORT", "50000")
    database = os.getenv("DB2_DATABASE", "MLOOP")
    user = os.getenv("DB2_USER", "mloop")
    password = os.getenv("DB2_PASSWORD", "")
    return (
        f"DATABASE={database};"
        f"HOSTNAME={host};"
        f"PORT={port};"
        f"PROTOCOL=TCPIP;"
        f"UID={user};"
        f"PWD={password};"
    )


def get_connection():
    """Establish and return an active IBM Db2 connection."""
    conn_str = get_connection_string()
    try:
        conn = ibm_db.connect(conn_str, "", "")
        return conn
    except Exception as e:
        err_msg = ibm_db.conn_errormsg() if hasattr(ibm_db, "conn_errormsg") else str(e)
        logger.error(f"Failed to connect to IBM Db2 ({conn_str}): {err_msg}")
        raise ConnectionError(f"IBM Db2 connection error: {err_msg}") from e


def close_connection(conn) -> None:
    """Safely close an open Db2 connection."""
    if conn:
        try:
            ibm_db.close(conn)
        except Exception as e:
            logger.warning(f"Error closing Db2 connection: {e}")


@contextmanager
def get_db():
    """Context manager providing an active connection, automatically closing it."""
    conn = get_connection()
    try:
        yield conn
    finally:
        close_connection(conn)


@contextmanager
def transaction(conn=None):
    """
    Context manager for atomic Db2 transactions.
    Disables autocommit, commits on success, and rolls back on exception.
    """
    external_conn = conn is not None
    active_conn = conn if external_conn else get_connection()
    try:
        ibm_db.autocommit(active_conn, ibm_db.SQL_AUTOCOMMIT_OFF)
        yield active_conn
        ibm_db.commit(active_conn)
    except Exception as e:
        try:
            ibm_db.rollback(active_conn)
        except Exception as rb_err:
            logger.error(f"Rollback failed: {rb_err}")
        raise e
    finally:
        try:
            ibm_db.autocommit(active_conn, ibm_db.SQL_AUTOCOMMIT_ON)
        except Exception:
            pass
        if not external_conn:
            close_connection(active_conn)


def _clean_row(row: dict) -> dict:
    """Helper to convert column keys to lowercase and format CLOB/byte values."""
    cleaned = {}
    for k, v in row.items():
        key = k.lower()
        if isinstance(v, bytes):
            v = v.decode("utf-8", errors="replace")
        elif v is not None and not isinstance(v, (int, float, bool, str, list, dict)):
            v = str(v)
        cleaned[key] = v
    return cleaned


def execute_query(sql: str, params: Optional[Tuple[Any, ...]] = None, conn=None) -> List[Dict[str, Any]]:
    """
    Execute a parameterized SELECT query and return rows as list of dictionaries.
    """
    def _run(active_conn):
        stmt = ibm_db.prepare(active_conn, sql)
        if not stmt:
            raise RuntimeError(f"Prepare failed: {ibm_db.stmt_errormsg(active_conn)}")
        if params is not None and len(params) > 0:
            ibm_db.execute(stmt, tuple(params))
        else:
            ibm_db.execute(stmt)
        
        rows = []
        row = ibm_db.fetch_assoc(stmt)
        while row:
            rows.append(_clean_row(row))
            row = ibm_db.fetch_assoc(stmt)
        ibm_db.free_result(stmt)
        return rows

    if conn is not None:
        return _run(conn)
    else:
        with get_db() as c:
            return _run(c)


def execute_non_query(sql: str, params: Optional[Tuple[Any, ...]] = None, conn=None) -> int:
    """
    Execute an INSERT, UPDATE, DELETE, or DDL statement.
    Returns the number of rows affected.
    """
    def _run(active_conn):
        stmt = ibm_db.prepare(active_conn, sql)
        if not stmt:
            raise RuntimeError(f"Prepare failed: {ibm_db.stmt_errormsg(active_conn)}")
        if params is not None and len(params) > 0:
            ibm_db.execute(stmt, tuple(params))
        else:
            ibm_db.execute(stmt)
        try:
            affected = ibm_db.num_rows(stmt)
        except Exception:
            affected = 1
        return affected

    if conn is not None:
        return _run(conn)
    else:
        with get_db() as c:
            return _run(c)


def execute_insert_identity(sql: str, params: Optional[Tuple[Any, ...]] = None, conn=None) -> int:
    """
    Execute an INSERT statement and return the generated IDENTITY value.
    Uses Db2's IDENTITY_VAL_LOCAL() in the same connection context.
    """
    def _run(active_conn):
        stmt = ibm_db.prepare(active_conn, sql)
        if not stmt:
            raise RuntimeError(f"Prepare failed: {ibm_db.stmt_errormsg(active_conn)}")
        if params is not None and len(params) > 0:
            ibm_db.execute(stmt, tuple(params))
        else:
            ibm_db.execute(stmt)

        # Retrieve last identity
        id_stmt = ibm_db.exec_immediate(active_conn, "SELECT IDENTITY_VAL_LOCAL() AS last_id FROM SYSIBM.SYSDUMMY1")
        row = ibm_db.fetch_assoc(id_stmt)
        ibm_db.free_result(id_stmt)
        if row and row.get("LAST_ID") is not None:
            return int(row["LAST_ID"])
        return 0

    if conn is not None:
        return _run(conn)
    else:
        with get_db() as c:
            return _run(c)


def table_exists(table_name: str, conn=None) -> bool:
    """Check if a table exists in Db2 catalog (SYSCAT.TABLES)."""
    sql = "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABNAME = UPPER(?) AND TABSCHEMA = CURRENT SCHEMA FETCH FIRST 1 ROWS ONLY"
    rows = execute_query(sql, (table_name.strip(),), conn=conn)
    return len(rows) > 0


def column_exists(table_name: str, column_name: str, conn=None) -> bool:
    """Check if a column exists in Db2 catalog (SYSCAT.COLUMNS)."""
    sql = "SELECT COLNAME FROM SYSCAT.COLUMNS WHERE TABNAME = UPPER(?) AND TABSCHEMA = CURRENT SCHEMA AND COLNAME = UPPER(?) FETCH FIRST 1 ROWS ONLY"
    rows = execute_query(sql, (table_name.strip(), column_name.strip()), conn=conn)
    return len(rows) > 0


def view_exists(view_name: str, conn=None) -> bool:
    """Check if a view exists in Db2 catalog (SYSCAT.VIEWS)."""
    sql = "SELECT VIEWNAME FROM SYSCAT.VIEWS WHERE VIEWNAME = UPPER(?) AND VIEWSCHEMA = CURRENT SCHEMA FETCH FIRST 1 ROWS ONLY"
    rows = execute_query(sql, (view_name.strip(),), conn=conn)
    return len(rows) > 0


def index_exists(index_name: str, conn=None) -> bool:
    """Check if an index exists in Db2 catalog (SYSCAT.INDEXES)."""
    sql = "SELECT INDNAME FROM SYSCAT.INDEXES WHERE INDNAME = UPPER(?) AND INDSCHEMA = CURRENT SCHEMA FETCH FIRST 1 ROWS ONLY"
    rows = execute_query(sql, (index_name.strip(),), conn=conn)
    return len(rows) > 0


def get_db2_server_info(conn=None) -> Dict[str, str]:
    """Retrieve Db2 server release, level, and engine name."""
    def _inspect(c):
        info = ibm_db.server_info(c)
        return {
            "dbms_name": str(getattr(info, "DBMS_NAME", "DB2/LUW")),
            "dbms_ver": str(getattr(info, "DBMS_VER", "Unknown")),
            "db_name": str(getattr(info, "DB_NAME", os.getenv("DB2_DATABASE", "MLOOP"))),
        }
    if conn is not None:
        return _inspect(conn)
    with get_db() as c:
        return _inspect(c)


# ====================================================================
# STUDENT OPERATIONS
# ====================================================================

def get_or_create_student(username: str) -> Dict[str, Any]:
    """Retrieve existing student by username or create a new one."""
    username = username.strip()
    if not username:
        raise ValueError("Username cannot be empty")
    
    rows = execute_query(
        "SELECT student_id, username, created_at FROM students WHERE username = ? FETCH FIRST 1 ROWS ONLY",
        (username,)
    )
    if rows:
        return rows[0]

    student_id = execute_insert_identity(
        "INSERT INTO students (username) VALUES (?)",
        (username,)
    )
    return {
        "student_id": student_id,
        "username": username,
        "created_at": None,
    }


def get_student_by_id(student_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve student record by student_id."""
    rows = execute_query(
        "SELECT student_id, username, created_at FROM students WHERE student_id = ? FETCH FIRST 1 ROWS ONLY",
        (student_id,)
    )
    return rows[0] if rows else None


# ====================================================================
# CONCEPTS & PREREQUISITES
# ====================================================================

def get_all_concepts() -> List[Dict[str, Any]]:
    """Return all concepts ordered by sequential order, including custom metadata and chunk counts."""
    concepts = execute_query(
        "SELECT concept_id, name, description, seq_order, COALESCE(is_custom, 0) AS is_custom, created_by FROM concepts ORDER BY seq_order ASC"
    )
    if not concepts:
        return concepts
    counts_rows = execute_query("SELECT concept_id, COUNT(*) AS cnt FROM chunks GROUP BY concept_id")
    counts_map = {int(r["concept_id"]): int(r["cnt"]) for r in counts_rows}
    for c in concepts:
        c["chunk_count"] = counts_map.get(int(c["concept_id"]), 0)
    return concepts


def get_concept_by_id(concept_id: int) -> Optional[Dict[str, Any]]:
    """Return concept record by ID."""
    rows = execute_query(
        "SELECT concept_id, name, description, seq_order, COALESCE(is_custom, 0) AS is_custom, created_by FROM concepts WHERE concept_id = ? FETCH FIRST 1 ROWS ONLY",
        (concept_id,)
    )
    return rows[0] if rows else None


def get_concept_prereqs(concept_id: int) -> List[int]:
    """Return list of prerequisite concept IDs directly required by concept_id."""
    rows = execute_query(
        "SELECT prereq_id FROM concept_prereqs WHERE concept_id = ?",
        (concept_id,)
    )
    return [r["prereq_id"] for r in rows]


def find_root_cause_prereq(student_id: int, current_concept_id: int) -> Tuple[Optional[Dict[str, Any]], str, List[Dict[str, Any]]]:
    """
    Run recursive CTE over concept_prereqs to collect all ancestors/prerequisites
    of current_concept_id along with the student's current mastery score.
    
    Db2 LUW Rule:
    'WITH name (cols) AS (anchor UNION ALL recursive) SELECT ...' (NO 'RECURSIVE' keyword).
    
    Returns:
      (root_cause_concept_dict_or_none, sql_executed, all_prereq_rows)
    """
    sql = """
WITH prereq_tree (concept_id, prereq_id, depth) AS (
    SELECT cp.concept_id, cp.prereq_id, 1
    FROM concept_prereqs cp
    WHERE cp.concept_id = ?
    UNION ALL
    SELECT pt.concept_id, cp2.prereq_id, pt.depth + 1
    FROM prereq_tree pt, concept_prereqs cp2
    WHERE pt.prereq_id = cp2.concept_id
)
SELECT 
    c.concept_id, 
    c.name, 
    c.seq_order,
    MIN(pt.depth) AS min_depth,
    COALESCE(m.mastery_score, 0.0) AS mastery_score,
    COALESCE(m.attempt_count, 0) AS attempt_count,
    COALESCE(m.distinct_difficulties, 0) AS distinct_difficulties
FROM prereq_tree pt
JOIN concepts c ON pt.prereq_id = c.concept_id
LEFT JOIN mastery m ON m.student_id = ? AND m.concept_id = c.concept_id
GROUP BY c.concept_id, c.name, c.seq_order, m.mastery_score, m.attempt_count, m.distinct_difficulties
ORDER BY mastery_score ASC, min_depth DESC
"""
    rows = execute_query(sql, (current_concept_id, student_id))
    
    # Weakest prerequisite below 0.8 (or never attempted)
    root_cause = None
    for r in rows:
        if r["mastery_score"] < 0.8 or r["attempt_count"] == 0:
            root_cause = r
            break
            
    return root_cause, sql.strip(), rows


# ====================================================================
# DOCUMENTS & CHUNKS (INGESTION & RETRIEVAL)
# ====================================================================

def insert_document(
    concept_id: int,
    title: str,
    source: str,
    content: str,
    source_type: str = "seed",
    source_url: Optional[str] = None,
    conn=None
) -> int:
    """Store raw ingested document with source type (seed|wikipedia|upload|paste) and optional source URL."""
    sql = "INSERT INTO documents (concept_id, title, source, source_type, source_url, content) VALUES (?, ?, ?, ?, ?, ?)"
    safe_url = source_url[:500] if source_url else None
    return execute_insert_identity(
        sql,
        (concept_id, title.strip()[:200], source.strip()[:50], source_type.strip()[:20], safe_url, content),
        conn=conn,
    )


def create_custom_concept(
    name: str,
    description: str,
    student_id: Optional[int] = None,
    prereq_ids: Optional[List[int]] = None,
    seq_order: Optional[int] = None,
    created_by: Optional[int] = None,
    is_custom: int = 1,
    conn=None,
) -> int:
    """
    Create a new custom concept (is_custom=1, created_by=student_id) or return existing ID.
    Optionally links prerequisite concept IDs in concept_prereqs.
    Reuses caller's transaction connection when conn is provided.
    """
    creator = created_by if created_by is not None else student_id
    clean_name = name.strip()[:100]
    clean_desc = (description or "").strip()[:500]

    def _run(active_conn) -> int:
        existing = execute_query(
            "SELECT concept_id FROM concepts WHERE name = ? FETCH FIRST 1 ROWS ONLY",
            (clean_name,),
            conn=active_conn,
        )
        if existing:
            cid = int(existing[0]["concept_id"])
        else:
            if seq_order is not None:
                next_seq = int(seq_order)
            else:
                max_seq_rows = execute_query(
                    "SELECT COALESCE(MAX(seq_order), 0) + 1 AS next_seq FROM concepts",
                    conn=active_conn,
                )
                next_seq = int(max_seq_rows[0]["next_seq"]) if max_seq_rows else 1

            cid = execute_insert_identity(
                "INSERT INTO concepts (name, description, seq_order, is_custom, created_by) VALUES (?, ?, ?, ?, ?)",
                (clean_name, clean_desc, next_seq, int(is_custom), creator),
                conn=active_conn,
            )

        if prereq_ids:
            for pid in prereq_ids:
                if int(pid) != cid:
                    edge = execute_query(
                        "SELECT 1 FROM concept_prereqs WHERE concept_id = ? AND prereq_id = ? FETCH FIRST 1 ROWS ONLY",
                        (cid, int(pid)),
                        conn=active_conn,
                    )
                    if not edge:
                        execute_non_query(
                            "INSERT INTO concept_prereqs (concept_id, prereq_id) VALUES (?, ?)",
                            (cid, int(pid)),
                            conn=active_conn,
                        )
        return cid

    if conn is not None:
        return _run(conn)
    with transaction() as new_conn:
        return _run(new_conn)


def insert_chunk(doc_id: int, concept_id: int, chunk_index: int, content: str, embedding_json: Optional[str] = None, conn=None) -> int:
    """Store chunk text and optional vector embedding (JSON array in CLOB)."""
    sql = "INSERT INTO chunks (doc_id, concept_id, chunk_index, content, embedding) VALUES (?, ?, ?, ?, ?)"
    return execute_insert_identity(sql, (doc_id, concept_id, chunk_index, content, embedding_json), conn=conn)


def get_chunks_for_concept(concept_id: int) -> List[Dict[str, Any]]:
    """Retrieve all chunks belonging to a concept."""
    sql = """
SELECT chunk_id, doc_id, concept_id, chunk_index, content, embedding
FROM chunks
WHERE concept_id = ?
ORDER BY chunk_id ASC
"""
    return execute_query(sql, (concept_id,))


def get_all_chunks() -> List[Dict[str, Any]]:
    """Retrieve all chunks stored across all concepts."""
    sql = "SELECT chunk_id, doc_id, concept_id, chunk_index, content, embedding FROM chunks ORDER BY chunk_id ASC"
    return execute_query(sql)


# ====================================================================
# LESSONS
# ====================================================================

def save_lesson(student_id: int, concept_id: int, loop_count: int, style: str, steps_json: str) -> int:
    """Store generated lesson steps."""
    sql = """
INSERT INTO lessons (student_id, concept_id, loop_count, style, steps_json)
VALUES (?, ?, ?, ?, ?)
"""
    return execute_insert_identity(sql, (student_id, concept_id, loop_count, style, steps_json))


def get_latest_lesson(student_id: int, concept_id: int) -> Optional[Dict[str, Any]]:
    """Get the most recent lesson generated for this student and concept."""
    sql = """
SELECT lesson_id, student_id, concept_id, loop_count, style, steps_json, created_at
FROM lessons
WHERE student_id = ? AND concept_id = ?
ORDER BY lesson_id DESC
FETCH FIRST 1 ROWS ONLY
"""
    rows = execute_query(sql, (student_id, concept_id))
    return rows[0] if rows else None


# ====================================================================
# QUESTIONS POOL
# ====================================================================

def save_question(
    concept_id: int,
    source_chunk_id: Optional[int],
    question_text: str,
    option_a: str,
    option_b: str,
    option_c: str,
    option_d: str,
    correct_letter: str,
    explanation: str,
    difficulty: str,
    loop_index: int = 1,
    conn=None
) -> int:
    """Insert a single verified quiz question."""
    sql = """
INSERT INTO questions (
    concept_id, source_chunk_id, question_text,
    option_a, option_b, option_c, option_d,
    correct_letter, explanation, difficulty, loop_index
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
    return execute_insert_identity(
        sql,
        (
            concept_id, source_chunk_id, question_text,
            option_a, option_b, option_c, option_d,
            correct_letter.upper().strip(), explanation, difficulty.lower().strip(),
            loop_index
        ),
        conn=conn
    )


def get_unanswered_questions(student_id: int, concept_id: int, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve questions for a concept that this student has not yet attempted.
    Ensures question variety and no repeats across remediation loops.
    """
    sql = f"""
SELECT 
    q.question_id, q.concept_id, q.source_chunk_id, q.question_text,
    q.option_a, q.option_b, q.option_c, q.option_d,
    q.correct_letter, q.explanation, q.difficulty, q.loop_index
FROM questions q
WHERE q.concept_id = ?
  AND q.question_id NOT IN (
      SELECT a.question_id FROM attempts a WHERE a.student_id = ?
  )
ORDER BY q.loop_index DESC, q.difficulty ASC, q.question_id ASC
FETCH FIRST {int(limit)} ROWS ONLY
"""
    return execute_query(sql, (concept_id, student_id))


def get_all_questions_for_concept(concept_id: int) -> List[Dict[str, Any]]:
    """Retrieve all generated questions for a concept."""
    sql = """
SELECT 
    question_id, concept_id, source_chunk_id, question_text,
    option_a, option_b, option_c, option_d,
    correct_letter, explanation, difficulty, loop_index
FROM questions
WHERE concept_id = ?
ORDER BY question_id ASC
"""
    return execute_query(sql, (concept_id,))


# ====================================================================
# ATTEMPTS, DETERMINISTIC MASTERY & TRANSACTIONS
# ====================================================================

DIFFICULTY_WEIGHTS = {
    "easy": 1.0,
    "medium": 1.5,
    "hard": 2.0
}


def calculate_mastery_from_attempts(attempts: List[Dict[str, Any]]) -> Tuple[float, int, int]:
    """
    Mastery formula:
    Mastery for student+concept = weighted mean of correctness over attempts,
    weight = difficulty weight (easy 1, medium 1.5, hard 2) x 0.85^(age in attempts, newest = 0).
    
    Returns (mastery_score, attempt_count, distinct_difficulties_count)
    """
    if not attempts:
        return 0.0, 0, 0

    # Attempts sorted newest first (age 0 = newest)
    sorted_attempts = sorted(attempts, key=lambda a: a["attempt_id"], reverse=True)
    total_weighted_correctness = 0.0
    total_weights = 0.0
    diff_set = set()

    for age, att in enumerate(sorted_attempts):
        diff = att["difficulty"].lower()
        diff_weight = DIFFICULTY_WEIGHTS.get(diff, 1.0)
        diff_set.add(diff)
        
        recency_factor = 0.85 ** age
        w = diff_weight * recency_factor
        
        is_corr = 1.0 if att["is_correct"] in (1, True, "1") else 0.0
        total_weighted_correctness += is_corr * w
        total_weights += w

    mastery_score = total_weighted_correctness / total_weights if total_weights > 0 else 0.0
    return round(mastery_score, 4), len(sorted_attempts), len(diff_set)


def record_attempt_and_update_mastery(
    student_id: int,
    concept_id: int,
    question_id: int,
    selected_letter: str,
    is_correct: bool,
    difficulty: str
) -> Dict[str, Any]:
    """
    Record an attempt and atomically update mastery and mastery_history in a Db2 transaction.
    """
    with transaction() as conn:
        # 1. Insert into attempts
        insert_att_sql = """
INSERT INTO attempts (student_id, concept_id, question_id, selected_letter, is_correct, difficulty)
VALUES (?, ?, ?, ?, ?, ?)
"""
        att_id = execute_insert_identity(
            insert_att_sql,
            (
                student_id, concept_id, question_id,
                selected_letter.upper().strip(),
                1 if is_correct else 0,
                difficulty.lower().strip()
            ),
            conn=conn
        )

        # 2. Fetch all attempts for this student + concept to compute new mastery
        attempts = execute_query(
            "SELECT attempt_id, is_correct, difficulty FROM attempts WHERE student_id = ? AND concept_id = ? ORDER BY attempt_id ASC",
            (student_id, concept_id),
            conn=conn
        )
        
        new_mastery, attempt_count, distinct_diffs = calculate_mastery_from_attempts(attempts)

        # 3. Upsert mastery table
        existing = execute_query(
            "SELECT mastery_id FROM mastery WHERE student_id = ? AND concept_id = ? FETCH FIRST 1 ROWS ONLY",
            (student_id, concept_id),
            conn=conn
        )
        if existing:
            update_sql = """
UPDATE mastery
SET mastery_score = ?, attempt_count = ?, distinct_difficulties = ?, updated_at = CURRENT TIMESTAMP
WHERE student_id = ? AND concept_id = ?
"""
            execute_non_query(update_sql, (new_mastery, attempt_count, distinct_diffs, student_id, concept_id), conn=conn)
        else:
            insert_m_sql = """
INSERT INTO mastery (student_id, concept_id, mastery_score, attempt_count, distinct_difficulties)
VALUES (?, ?, ?, ?, ?)
"""
            execute_non_query(insert_m_sql, (student_id, concept_id, new_mastery, attempt_count, distinct_diffs), conn=conn)

        # 4. Append to mastery_history
        insert_hist_sql = """
INSERT INTO mastery_history (student_id, concept_id, mastery_score, attempt_id)
VALUES (?, ?, ?, ?)
"""
        execute_non_query(insert_hist_sql, (student_id, concept_id, new_mastery, att_id), conn=conn)

        return {
            "attempt_id": att_id,
            "mastery_score": new_mastery,
            "attempt_count": attempt_count,
            "distinct_difficulties": distinct_diffs
        }


def get_current_mastery(student_id: int, concept_id: int) -> Dict[str, Any]:
    """Retrieve current mastery record for student + concept."""
    sql = """
SELECT mastery_id, student_id, concept_id, mastery_score, attempt_count, distinct_difficulties, updated_at
FROM mastery
WHERE student_id = ? AND concept_id = ?
FETCH FIRST 1 ROWS ONLY
"""
    rows = execute_query(sql, (student_id, concept_id))
    if rows:
        return rows[0]
    return {
        "mastery_score": 0.0,
        "attempt_count": 0,
        "distinct_difficulties": 0,
        "updated_at": None
    }


# ====================================================================
# GATE DECISION & LOOP EVENTS LOGGING
# ====================================================================

def evaluate_gate(mastery_score: float, attempt_count: int, distinct_difficulties: int) -> Tuple[bool, str]:
    """
    Evaluate Gate Rule:
    advance only if mastery >= 0.8 AND >= 5 attempts AND attempts span >= 2 difficulty levels.
    """
    reasons = []
    if mastery_score < 0.8:
        reasons.append(f"Mastery score {mastery_score:.2f} is below 0.80 threshold")
    if attempt_count < 5:
        reasons.append(f"Total attempts ({attempt_count}) is below required minimum of 5")
    if distinct_difficulties < 2:
        reasons.append(f"Difficulty span ({distinct_difficulties}) is below required minimum of 2 levels")

    if not reasons:
        return True, "Passed gate: mastery >= 0.80, >= 5 attempts, and >= 2 difficulty levels tested."
    return False, "Failed gate: " + "; ".join(reasons)


def log_loop_event(
    student_id: int,
    concept_id: int,
    event_type: str,
    gate_passed: bool,
    mastery_score: float,
    attempt_count: int,
    distinct_difficulties: int,
    root_cause_concept_id: Optional[int],
    reason: str,
    sql_query: Optional[str] = None
) -> int:
    """Log gate or remediation loop event to loop_events table."""
    sql = """
INSERT INTO loop_events (
    student_id, concept_id, event_type, gate_passed,
    mastery_score, attempt_count, distinct_difficulties,
    root_cause_concept_id, reason, sql_query
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
    return execute_insert_identity(
        sql,
        (
            student_id, concept_id, event_type,
            1 if gate_passed else 0,
            mastery_score, attempt_count, distinct_difficulties,
            root_cause_concept_id, reason, sql_query
        )
    )


def get_loop_events_for_concept(student_id: int, concept_id: int) -> List[Dict[str, Any]]:
    """Retrieve all loop events logged for a student on a concept."""
    sql = """
SELECT 
    event_id, student_id, concept_id, event_type, gate_passed,
    mastery_score, attempt_count, distinct_difficulties,
    root_cause_concept_id, reason, sql_query, created_at
FROM loop_events
WHERE student_id = ? AND concept_id = ?
ORDER BY event_id ASC
"""
    return execute_query(sql, (student_id, concept_id))


def get_remediation_count(student_id: int, concept_id: int) -> int:
    """Get the number of times remediation has been triggered for this concept."""
    sql = """
SELECT COUNT(*) AS cnt
FROM loop_events
WHERE student_id = ? AND concept_id = ? AND event_type IN ('GATE_FAIL', 'REMEDIATION_TRIGGERED')
"""
    rows = execute_query(sql, (student_id, concept_id))
    return int(rows[0]["cnt"]) if rows else 0


# ====================================================================
# LLM CACHE
# ====================================================================

def get_cached_llm(cache_key: str, conn=None) -> Optional[str]:
    """Retrieve cached response from llm_cache by SHA-256 key."""
    sql = "SELECT response_text FROM llm_cache WHERE cache_key = ? FETCH FIRST 1 ROWS ONLY"
    rows = execute_query(sql, (cache_key,), conn=conn)
    return rows[0]["response_text"] if rows else None


def set_cached_llm(cache_key: str, model_name: str, prompt_text: str, response_text: str, conn=None) -> None:
    """Cache LLM response in Db2."""
    existing = get_cached_llm(cache_key, conn=conn)
    if existing is not None:
        return
    sql = "INSERT INTO llm_cache (cache_key, model_name, prompt_text, response_text) VALUES (?, ?, ?, ?)"
    try:
        execute_non_query(sql, (cache_key, model_name, prompt_text, response_text), conn=conn)
    except Exception as e:
        logger.warning(f"Failed to write to llm_cache: {e}")


# ====================================================================
# ANALYTICS & PROGRESS VIEW
# ====================================================================

def get_student_progress_view(student_id: int) -> List[Dict[str, Any]]:
    """Read student concept matrix from SQL VIEW v_student_progress."""
    sql = """
SELECT 
    student_id, username, concept_id, concept_name, seq_order,
    current_mastery, total_attempts, distinct_difficulties, is_mastered, last_assessed_at
FROM v_student_progress
WHERE student_id = ?
ORDER BY seq_order ASC
"""
    return execute_query(sql, (student_id,))


def get_mastery_history_series(student_id: int, concept_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Read chronological mastery history for plotting progress line chart."""
    if concept_id is not None:
        sql = """
SELECT h.history_id, h.student_id, h.concept_id, c.name AS concept_name, h.mastery_score, h.recorded_at
FROM mastery_history h
JOIN concepts c ON h.concept_id = c.concept_id
WHERE h.student_id = ? AND h.concept_id = ?
ORDER BY h.history_id ASC
"""
        return execute_query(sql, (student_id, concept_id))
    else:
        sql = """
SELECT h.history_id, h.student_id, h.concept_id, c.name AS concept_name, h.mastery_score, h.recorded_at
FROM mastery_history h
JOIN concepts c ON h.concept_id = c.concept_id
WHERE h.student_id = ?
ORDER BY h.history_id ASC
"""
        return execute_query(sql, (student_id,))


def get_question_by_id(question_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single question by question_id."""
    sql = """
SELECT 
    question_id, concept_id, source_chunk_id, question_text,
    option_a, option_b, option_c, option_d,
    correct_letter, explanation, difficulty, loop_index
FROM questions
WHERE question_id = ?
FETCH FIRST 1 ROWS ONLY
"""
    rows = execute_query(sql, (question_id,))
    return rows[0] if rows else None


def get_loop_event_by_id(event_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a loop event by event_id."""
    sql = """
SELECT 
    event_id, student_id, concept_id, event_type, gate_passed,
    mastery_score, attempt_count, distinct_difficulties,
    root_cause_concept_id, reason, sql_query, created_at
FROM loop_events
WHERE event_id = ?
FETCH FIRST 1 ROWS ONLY
"""
    rows = execute_query(sql, (event_id,))
    return rows[0] if rows else None


def get_all_concept_prereqs_map() -> Dict[int, List[int]]:
    """Return dictionary mapping concept_id -> list of prereq_ids."""
    sql = "SELECT concept_id, prereq_id FROM concept_prereqs ORDER BY concept_id, prereq_id"
    rows = execute_query(sql)
    prereqs_map: Dict[int, List[int]] = {}
    for r in rows:
        cid = int(r["concept_id"])
        pid = int(r["prereq_id"])
        prereqs_map.setdefault(cid, []).append(pid)
    return prereqs_map


def save_lesson_image(lesson_id: Optional[int], concept_id: int, image_bytes: bytes, mime_type: str = "image/png") -> int:
    """Save an illustration generated for a lesson into Db2 lesson_images table."""
    sql = "INSERT INTO lesson_images (lesson_id, concept_id, image_data, mime_type) VALUES (?, ?, ?, ?)"
    return execute_insert_identity(sql, (lesson_id, concept_id, image_bytes, mime_type))


def get_lesson_image(lesson_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve illustration by lesson_id."""
    sql = """
SELECT image_id, lesson_id, concept_id, image_data, mime_type
FROM lesson_images
WHERE lesson_id = ?
ORDER BY image_id DESC
FETCH FIRST 1 ROWS ONLY
"""
    rows = execute_query(sql, (lesson_id,))
    return rows[0] if rows else None

