"""
Database Initialization and Seeding Script for MasteryLoop (mastree).
Creates Db2 LUW tables, indexes, and views idempotently.
Seeds the 9 SQL concepts, prerequisite graph edges, and initial markdown notes.
"""

import os
import re
import sys
import logging
from typing import Dict, List, Tuple
from dotenv import load_dotenv

load_dotenv()

# Add project root to sys.path so we can import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db import (
    get_db,
    execute_non_query,
    execute_query,
    execute_insert_identity,
    table_exists,
    column_exists,
    view_exists,
    index_exists,
    get_db2_server_info,
    transaction
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mastree.init_db")

# 9 Seed SQL Concepts in topological / curriculum sequence
SEED_CONCEPTS: List[Tuple[str, str, int]] = [
    ("SELECT basics", "Foundational attribute projection, column aliases, expressions, and DISTINCT", 1),
    ("WHERE", "Row-level filtering with comparison, logical operators, LIKE, and 3VL NULL handling", 2),
    ("ORDER BY", "Deterministic tuple sorting, ASC/DESC directions, tie-breaking, and NULLS FIRST/LAST", 3),
    ("Aggregate functions", "Scalar statistical summarization with COUNT, SUM, AVG, MIN, MAX, and NULL exclusion", 4),
    ("GROUP BY", "Categorical row partitioning into summary buckets and the Single-Value Rule", 5),
    ("HAVING", "Post-aggregation filtering on group calculations and summary thresholds", 6),
    ("JOINs", "Relational correlations across tables via INNER, LEFT/RIGHT/FULL OUTER, and CROSS joins", 7),
    ("Subqueries", "Nested scalar, column, and table queries, correlated vs non-correlated, and EXISTS", 8),
    ("Window functions", "Analytical partitioned ranking and rolling calculations without row collapse", 9),
]

# Prerequisite dependencies: (concept_name, prereq_name)
SEED_PREREQ_EDGES: List[Tuple[str, str]] = [
    ("WHERE", "SELECT basics"),
    ("ORDER BY", "SELECT basics"),
    ("Aggregate functions", "WHERE"),
    ("GROUP BY", "Aggregate functions"),
    ("HAVING", "GROUP BY"),
    ("JOINs", "SELECT basics"),
    ("JOINs", "WHERE"),
    ("Subqueries", "JOINs"),
    ("Subqueries", "WHERE"),
    ("Window functions", "GROUP BY"),
    ("Window functions", "Subqueries"),
]


def execute_ddl_idempotent() -> None:
    """Execute DDL statements from src/schema.sql safely and idempotently."""
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found at: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Split into discrete statements separated by semicolons
    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

    with get_db() as conn:
        for stmt in statements:
            # Clean comments for matching
            cleaned = re.sub(r"--.*", "", stmt).strip()
            if not cleaned:
                continue

            # Determine object name and type
            is_table = cleaned.upper().startswith("CREATE TABLE")
            is_index = cleaned.upper().startswith("CREATE INDEX")
            is_view = cleaned.upper().startswith("CREATE VIEW")

            try:
                execute_non_query(cleaned, conn=conn)
                logger.info(f"Executed: {cleaned.split()[0]} {cleaned.split()[1]} {cleaned.split()[2] if len(cleaned.split()) > 2 else ''}")
            except Exception as e:
                err_str = str(e)
                # SQL0601N: Object already exists in Db2
                if "-601" in err_str or "SQL0601N" in err_str or "already exists" in err_str.lower():
                    logger.debug(f"Object already exists (SQL0601N), skipping statement.")
                else:
                    logger.warning(f"DDL notice on statement: {err_str.strip()}")


def migrate_columns_idempotent() -> None:
    """Add missing columns to concepts and documents idempotently via SYSCAT.COLUMNS inspection."""
    with get_db() as conn:
        if not column_exists("concepts", "is_custom", conn=conn):
            try:
                execute_non_query("ALTER TABLE concepts ADD COLUMN is_custom SMALLINT DEFAULT 0", conn=conn)
                logger.info("Migrated: Added column is_custom to concepts.")
            except Exception as e:
                logger.warning(f"Notice on adding is_custom to concepts: {e}")

        if not column_exists("concepts", "created_by", conn=conn):
            try:
                execute_non_query("ALTER TABLE concepts ADD COLUMN created_by INTEGER", conn=conn)
                logger.info("Migrated: Added column created_by to concepts.")
            except Exception as e:
                logger.warning(f"Notice on adding created_by to concepts: {e}")

        if not column_exists("documents", "source_type", conn=conn):
            try:
                execute_non_query("ALTER TABLE documents ADD COLUMN source_type VARCHAR(20) DEFAULT 'seed'", conn=conn)
                logger.info("Migrated: Added column source_type to documents.")
            except Exception as e:
                logger.warning(f"Notice on adding source_type to documents: {e}")

        if not column_exists("documents", "source_url", conn=conn):
            try:
                execute_non_query("ALTER TABLE documents ADD COLUMN source_url VARCHAR(500)", conn=conn)
                logger.info("Migrated: Added column source_url to documents.")
            except Exception as e:
                logger.warning(f"Notice on adding source_url to documents: {e}")

        if not table_exists("lesson_images", conn=conn):
            try:
                execute_non_query("""
CREATE TABLE lesson_images (
    image_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lesson_id INTEGER,
    concept_id INTEGER NOT NULL,
    image_data BLOB(5M) NOT NULL,
    mime_type VARCHAR(50) DEFAULT 'image/png',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_lim_concept FOREIGN KEY (concept_id) REFERENCES concepts(concept_id) ON DELETE CASCADE
)
""", conn=conn)
                logger.info("Created table lesson_images.")
            except Exception as e:
                err_str = str(e)
                if "-601" not in err_str and "SQL0601N" not in err_str:
                    logger.warning(f"Notice creating lesson_images: {e}")



def seed_concepts_and_edges() -> Dict[str, int]:
    """Seed the 9 core concepts and their prerequisite relationships."""
    concept_map: Dict[str, int] = {}

    with transaction() as conn:
        # Seed Concepts
        for name, desc, seq in SEED_CONCEPTS:
            existing = execute_query(
                "SELECT concept_id FROM concepts WHERE name = ? FETCH FIRST 1 ROWS ONLY",
                (name,),
                conn=conn
            )
            if existing:
                cid = existing[0]["concept_id"]
                execute_non_query(
                    "UPDATE concepts SET description = ?, seq_order = ? WHERE concept_id = ?",
                    (desc, seq, cid),
                    conn=conn
                )
            else:
                cid = execute_insert_identity(
                    "INSERT INTO concepts (name, description, seq_order) VALUES (?, ?, ?)",
                    (name, desc, seq),
                    conn=conn
                )
            concept_map[name] = cid

        # Seed Prerequisite Graph Edges
        for concept_name, prereq_name in SEED_PREREQ_EDGES:
            cid = concept_map.get(concept_name)
            pid = concept_map.get(prereq_name)
            if cid and pid:
                edge_exists = execute_query(
                    "SELECT 1 FROM concept_prereqs WHERE concept_id = ? AND prereq_id = ? FETCH FIRST 1 ROWS ONLY",
                    (cid, pid),
                    conn=conn
                )
                if not edge_exists:
                    execute_non_query(
                        "INSERT INTO concept_prereqs (concept_id, prereq_id) VALUES (?, ?)",
                        (cid, pid),
                        conn=conn
                    )

    logger.info(f"Seeded {len(SEED_CONCEPTS)} concepts and {len(SEED_PREREQ_EDGES)} prerequisite edges.")
    return concept_map


def chunk_text(text: str, target_words: int = 120) -> List[str]:
    """
    Split text into chunks of approximately target_words words,
    breaking cleanly at sentence boundaries where possible.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        words = sentence.split()
        if not words:
            continue
        if current_word_count + len(words) > target_words and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = [sentence]
            current_word_count = len(words)
        else:
            current_chunk.append(sentence)
            current_word_count += len(words)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def seed_notes_and_chunks(concept_map: Dict[str, int]) -> None:
    """Parse src/data/sql_notes.md and populate documents and chunks tables."""
    notes_path = os.path.join(os.path.dirname(__file__), "data", "sql_notes.md")
    if not os.path.exists(notes_path):
        logger.warning(f"Seed notes not found at {notes_path}")
        return

    with open(notes_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Split sections by '## <Concept Name>'
    sections = re.split(r'\n##\s+', content)
    
    with transaction() as conn:
        for section in sections:
            lines = section.strip().split("\n", 1)
            if len(lines) < 2:
                continue
            concept_name = lines[0].strip()
            passage = lines[1].strip()

            cid = concept_map.get(concept_name)
            if not cid:
                continue

            # Check if document already seeded
            doc_rows = execute_query(
                "SELECT doc_id FROM documents WHERE concept_id = ? AND source = 'seed' FETCH FIRST 1 ROWS ONLY",
                (cid,),
                conn=conn
            )
            if doc_rows:
                doc_id = doc_rows[0]["doc_id"]
                execute_non_query(
                    "UPDATE documents SET content = ?, source_type = 'seed' WHERE doc_id = ?",
                    (passage, doc_id),
                    conn=conn
                )
            else:
                doc_id = execute_insert_identity(
                    "INSERT INTO documents (concept_id, title, source, source_type, content) VALUES (?, ?, 'seed', 'seed', ?)",
                    (cid, f"{concept_name} Seed Notes", passage),
                    conn=conn
                )

            # Check existing chunks
            existing_chunks = execute_query(
                "SELECT chunk_id FROM chunks WHERE doc_id = ?",
                (doc_id,),
                conn=conn
            )
            chunks = chunk_text(passage, target_words=120)
            if len(existing_chunks) != len(chunks):
                execute_non_query("DELETE FROM chunks WHERE doc_id = ?", (doc_id,), conn=conn)
                for idx, chk in enumerate(chunks):
                    execute_non_query(
                        "INSERT INTO chunks (doc_id, concept_id, chunk_index, content) VALUES (?, ?, ?, ?)",
                        (doc_id, cid, idx, chk),
                        conn=conn
                    )
                logger.info(f"Seeded/Updated {len(chunks)} chunks for concept '{concept_name}' (doc_id={doc_id})")

    logger.info("Successfully seeded notes and chunks into Db2.")


def reset_database(wipe_all: bool = False) -> None:
    """
    Completely clean all data from Db2 tables.
    If wipe_all is True: deletes concepts and prerequisite edges as well, leaving a 100% blank canvas.
    If wipe_all is False: deletes user progress, questions, lessons, chunks, and reseeds curriculum.
    """
    logger.info("Cleaning IBM Db2 LUW database tables...")
    tables_to_clear = [
        "attempts",
        "mastery_history",
        "mastery",
        "loop_events",
        "questions",
        "lessons",
        "lesson_images",
        "chunks",
        "documents"
    ]
    if wipe_all:
        tables_to_clear.extend(["concept_prereqs", "concepts", "students", "llm_cache"])

    with transaction() as conn:
        for t in tables_to_clear:
            if table_exists(t, conn=conn):
                try:
                    execute_non_query(f"DELETE FROM {t}", conn=conn)
                    logger.info(f"Cleared table: {t}")
                except Exception as e:
                    logger.warning(f"Notice clearing {t}: {e}")

    logger.info("Database reset complete.")
    if not wipe_all:
        logger.info("Re-seeding initial curriculum concepts...")
        concept_map = seed_concepts_and_edges()
        seed_notes_and_chunks(concept_map)


def init_database(seed: bool = False) -> None:
    """Run full idempotent schema initialization."""
    logger.info("Connecting to IBM Db2 and verifying server status...")
    info = get_db2_server_info()
    logger.info(f"Target DBMS: {info.get('dbms_name')} | Version: {info.get('dbms_ver')} | Database: {info.get('db_name')}")

    logger.info("Applying schema DDL idempotently...")
    execute_ddl_idempotent()

    logger.info("Checking and applying idempotent schema migrations...")
    migrate_columns_idempotent()

    if seed:
        logger.info("Seeding concepts, prerequisite graph, and curriculum notes...")
        concept_map = seed_concepts_and_edges()
        seed_notes_and_chunks(concept_map)
    else:
        logger.info("Database schema initialized cleanly without pre-seeded course content.")

    logger.info("Database initialization complete.")


if __name__ == "__main__":
    if "--clean" in sys.argv or "--reset" in sys.argv:
        reset_database(wipe_all=True)
    elif "--reset-data" in sys.argv:
        reset_database(wipe_all=False)
    elif "--seed" in sys.argv:
        init_database(seed=True)
    else:
        init_database(seed=False)


