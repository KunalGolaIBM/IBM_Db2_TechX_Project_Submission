"""
GitMind 2.0 — IBM Db2 Schema Migrations

Manages idempotent, versioned schema migrations for IBM Db2:
- Migration tracking table (GITMIND_SCHEMA_MIGRATIONS)
- Relational tables (Repositories, Artifacts, Relations, Index Runs, Runs, Findings, Evidence, Audit)
- Secondary B-tree and vector-compatible indexing
- Idempotent upgrade and verification mechanisms
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, NamedTuple, Optional

import config
from data.db2.connection import Db2ConnectionManager, get_connection_manager

logger = logging.getLogger("gitmind.db2.migrations")


class Migration(NamedTuple):
    migration_id: str
    description: str
    up_sqls: List[str]


# ---------------------------------------------------------------------------
# Migration Definitions
# ---------------------------------------------------------------------------

MIGRATION_001_CORE = Migration(
    migration_id="001_core_schema",
    description="Create core GitMind repository intelligence tables",
    up_sqls=[
        # Repositories Catalog
        """
        CREATE TABLE GITMIND_REPOSITORIES (
            REPO_ID VARCHAR(64) NOT NULL PRIMARY KEY,
            REPO_KEY VARCHAR(255) NOT NULL,
            REMOTE_URL VARCHAR(512),
            DEFAULT_BRANCH VARCHAR(128) DEFAULT 'main',
            INDEXED_HEAD_SHA VARCHAR(64),
            EMBEDDING_MODEL VARCHAR(128),
            EMBEDDING_DIMENSION INTEGER,
            SCHEMA_VERSION VARCHAR(32) DEFAULT '2.0',
            LAST_INDEXED_AT TIMESTAMP,
            CREATED_AT TIMESTAMP NOT NULL,
            UPDATED_AT TIMESTAMP NOT NULL,
            CONSTRAINT UQ_REPO_KEY UNIQUE (REPO_KEY)
        )
        """,
        # Artifacts Table
        """
        CREATE TABLE GITMIND_ARTIFACTS (
            ARTIFACT_ID VARCHAR(64) NOT NULL PRIMARY KEY,
            REPO_ID VARCHAR(64) NOT NULL,
            ARTIFACT_TYPE VARCHAR(64) NOT NULL,
            SOURCE_KEY VARCHAR(255) NOT NULL,
            TITLE VARCHAR(512),
            CONTENT CLOB,
            FILE_PATH VARCHAR(512),
            COMMIT_SHA VARCHAR(64),
            AUTHOR VARCHAR(255),
            SOURCE_URL VARCHAR(512),
            CONTENT_HASH VARCHAR(64) NOT NULL,
            START_LINE INTEGER,
            END_LINE INTEGER,
            CREATED_AT TIMESTAMP NOT NULL,
            UPDATED_AT TIMESTAMP NOT NULL,
            CONSTRAINT FK_ART_REPO FOREIGN KEY (REPO_ID)
                REFERENCES GITMIND_REPOSITORIES(REPO_ID) ON DELETE CASCADE,
            CONSTRAINT UQ_ART_SOURCE UNIQUE (REPO_ID, ARTIFACT_TYPE, SOURCE_KEY)
        )
        """,
        # Artifact Indexes
        "CREATE INDEX IDX_ART_REPO_TYPE ON GITMIND_ARTIFACTS(REPO_ID, ARTIFACT_TYPE)",
        "CREATE INDEX IDX_ART_COMMIT ON GITMIND_ARTIFACTS(COMMIT_SHA)",
        "CREATE INDEX IDX_ART_FILE ON GITMIND_ARTIFACTS(FILE_PATH)",
        "CREATE INDEX IDX_ART_HASH ON GITMIND_ARTIFACTS(CONTENT_HASH)",

        # Knowledge Graph Relations
        """
        CREATE TABLE GITMIND_RELATIONS (
            RELATION_ID VARCHAR(64) NOT NULL PRIMARY KEY,
            REPO_ID VARCHAR(64) NOT NULL,
            SOURCE_ARTIFACT_ID VARCHAR(64) NOT NULL,
            TARGET_ARTIFACT_ID VARCHAR(64) NOT NULL,
            RELATION_TYPE VARCHAR(64) NOT NULL,
            CREATED_AT TIMESTAMP NOT NULL,
            CONSTRAINT FK_REL_REPO FOREIGN KEY (REPO_ID)
                REFERENCES GITMIND_REPOSITORIES(REPO_ID) ON DELETE CASCADE,
            CONSTRAINT FK_REL_SRC FOREIGN KEY (SOURCE_ARTIFACT_ID)
                REFERENCES GITMIND_ARTIFACTS(ARTIFACT_ID) ON DELETE CASCADE,
            CONSTRAINT FK_REL_TGT FOREIGN KEY (TARGET_ARTIFACT_ID)
                REFERENCES GITMIND_ARTIFACTS(ARTIFACT_ID) ON DELETE CASCADE,
            CONSTRAINT UQ_RELATION UNIQUE (REPO_ID, SOURCE_ARTIFACT_ID, TARGET_ARTIFACT_ID, RELATION_TYPE)
        )
        """,
        # Relation Indexes
        "CREATE INDEX IDX_REL_SRC ON GITMIND_RELATIONS(SOURCE_ARTIFACT_ID)",
        "CREATE INDEX IDX_REL_TGT ON GITMIND_RELATIONS(TARGET_ARTIFACT_ID)",
        "CREATE INDEX IDX_REL_TYPE ON GITMIND_RELATIONS(REPO_ID, RELATION_TYPE)",

        # Indexing Runs
        """
        CREATE TABLE GITMIND_INDEX_RUNS (
            RUN_ID VARCHAR(64) NOT NULL PRIMARY KEY,
            REPO_ID VARCHAR(64) NOT NULL,
            INDEX_MODE VARCHAR(32) NOT NULL,
            STARTING_HEAD_SHA VARCHAR(64),
            ENDING_HEAD_SHA VARCHAR(64),
            INDEXED_ARTIFACTS INTEGER DEFAULT 0,
            GENERATED_CHUNKS INTEGER DEFAULT 0,
            FAILED_ARTIFACTS INTEGER DEFAULT 0,
            START_TIME TIMESTAMP NOT NULL,
            COMPLETION_TIME TIMESTAMP,
            STATUS VARCHAR(32) NOT NULL,
            ERROR_SUMMARY CLOB,
            CONSTRAINT FK_IDX_REPO FOREIGN KEY (REPO_ID)
                REFERENCES GITMIND_REPOSITORIES(REPO_ID) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IDX_RUN_REPO ON GITMIND_INDEX_RUNS(REPO_ID, STATUS)",
    ],
)

MIGRATION_002_AGENT_MEMORY = Migration(
    migration_id="002_agent_memory_and_findings",
    description="Create tables for multi-agent traces, findings, and grounded evidence",
    up_sqls=[
        # Agent Runs
        """
        CREATE TABLE GITMIND_AGENT_RUNS (
            RUN_ID VARCHAR(64) NOT NULL PRIMARY KEY,
            REPO_ID VARCHAR(64) NOT NULL,
            QUERY_HASH VARCHAR(64),
            QUERY_SUMMARY VARCHAR(1024),
            WORKFLOW_NAME VARCHAR(64),
            AGENTS_INVOKED VARCHAR(512),
            LLM_PROVIDER VARCHAR(64),
            LLM_MODEL VARCHAR(64),
            PROMPT_VERSION VARCHAR(32),
            STATUS VARCHAR(32),
            START_TIME TIMESTAMP NOT NULL,
            COMPLETION_TIME TIMESTAMP,
            CONSTRAINT FK_AGRUN_REPO FOREIGN KEY (REPO_ID)
                REFERENCES GITMIND_REPOSITORIES(REPO_ID) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IDX_AGRUN_QUERY ON GITMIND_AGENT_RUNS(REPO_ID, QUERY_HASH)",

        # Findings (Persistent Engineering Memory)
        """
        CREATE TABLE GITMIND_FINDINGS (
            FINDING_ID VARCHAR(64) NOT NULL PRIMARY KEY,
            REPO_ID VARCHAR(64) NOT NULL,
            AGENT_RUN_ID VARCHAR(64),
            AGENT_NAME VARCHAR(64) NOT NULL,
            FINDING_TYPE VARCHAR(64) NOT NULL,
            TITLE VARCHAR(512) NOT NULL,
            SUMMARY CLOB NOT NULL,
            SEVERITY VARCHAR(32),
            STATUS VARCHAR(32) DEFAULT 'ACTIVE',
            CREATED_AT TIMESTAMP NOT NULL,
            CONSTRAINT FK_FIND_REPO FOREIGN KEY (REPO_ID)
                REFERENCES GITMIND_REPOSITORIES(REPO_ID) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IDX_FIND_TYPE ON GITMIND_FINDINGS(REPO_ID, FINDING_TYPE)",
        "CREATE INDEX IDX_FIND_AGENT ON GITMIND_FINDINGS(REPO_ID, AGENT_NAME)",

        # Finding Evidence (Grounded traceability)
        """
        CREATE TABLE GITMIND_FINDING_EVIDENCE (
            EVIDENCE_ID VARCHAR(64) NOT NULL PRIMARY KEY,
            FINDING_ID VARCHAR(64) NOT NULL,
            ARTIFACT_ID VARCHAR(64),
            COMMIT_SHA VARCHAR(64),
            FILE_PATH VARCHAR(512),
            START_LINE INTEGER,
            END_LINE INTEGER,
            EVIDENCE_TYPE VARCHAR(64),
            CONTENT_HASH VARCHAR(64),
            SOURCE_URL VARCHAR(512),
            CREATED_AT TIMESTAMP NOT NULL,
            CONSTRAINT FK_EVID_FIND FOREIGN KEY (FINDING_ID)
                REFERENCES GITMIND_FINDINGS(FINDING_ID) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IDX_EVID_FIND ON GITMIND_FINDING_EVIDENCE(FINDING_ID)",
        "CREATE INDEX IDX_EVID_COMMIT ON GITMIND_FINDING_EVIDENCE(COMMIT_SHA)",
        "CREATE INDEX IDX_EVID_FILE ON GITMIND_FINDING_EVIDENCE(FILE_PATH)",
    ],
)

MIGRATION_003_AUDIT = Migration(
    migration_id="003_audit_trail",
    description="Create append-only audit event log table",
    up_sqls=[
        """
        CREATE TABLE GITMIND_AUDIT_EVENTS (
            EVENT_ID VARCHAR(64) NOT NULL PRIMARY KEY,
            REPO_ID VARCHAR(64) NOT NULL,
            EVENT_TYPE VARCHAR(64) NOT NULL,
            ACTOR VARCHAR(128) NOT NULL,
            DETAILS CLOB,
            CREATED_AT TIMESTAMP NOT NULL,
            CONSTRAINT FK_AUDIT_REPO FOREIGN KEY (REPO_ID)
                REFERENCES GITMIND_REPOSITORIES(REPO_ID) ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IDX_AUDIT_REPO_TIME ON GITMIND_AUDIT_EVENTS(REPO_ID, CREATED_AT)",
    ],
)

MIGRATION_004_VECTOR = Migration(
    migration_id="004_vector_store",
    description="Create official DB2VS vector table for semantic embeddings",
    up_sqls=[
        f"""
        CREATE TABLE {config.DB2_VECTOR_TABLE} (
            ID CHAR(16) NOT NULL PRIMARY KEY,
            TEXT CLOB,
            METADATA BLOB,
            EMBEDDING VECTOR({config.get_embedding_dimension()}, FLOAT32)
        )
        """,
    ],
)

ALL_MIGRATIONS: List[Migration] = [
    MIGRATION_001_CORE,
    MIGRATION_002_AGENT_MEMORY,
    MIGRATION_003_AUDIT,
    MIGRATION_004_VECTOR,
]


# ---------------------------------------------------------------------------
# Migration Manager
# ---------------------------------------------------------------------------

class SchemaMigrationManager:
    """Manages tracking, applying, and verifying Db2 migrations."""

    def __init__(self, manager: Optional[Db2ConnectionManager] = None):
        self.manager = manager or get_connection_manager()

    def ensure_migration_table(self, conn) -> None:
        """Create GITMIND_SCHEMA_MIGRATIONS if not existing."""
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT TABNAME FROM SYSCAT.TABLES
                WHERE TABSCHEMA = ? AND TABNAME = 'GITMIND_SCHEMA_MIGRATIONS'
            """, (self.manager.schema,))
            if not cur.fetchone():
                cur.execute("""
                    CREATE TABLE GITMIND_SCHEMA_MIGRATIONS (
                        MIGRATION_ID VARCHAR(64) NOT NULL PRIMARY KEY,
                        DESCRIPTION VARCHAR(255) NOT NULL,
                        APPLIED_AT TIMESTAMP NOT NULL
                    )
                """)
                conn.commit()
                logger.info("Created schema migrations tracking table.")
        finally:
            cur.close()

    def get_applied_migrations(self, conn) -> set[str]:
        """Fetch IDs of applied migrations."""
        cur = conn.cursor()
        try:
            cur.execute("SELECT MIGRATION_ID FROM GITMIND_SCHEMA_MIGRATIONS")
            rows = cur.fetchall()
            return {r[0].strip() for r in rows}
        except Exception:
            return set()
        finally:
            cur.close()

    def apply_migrations(self) -> List[str]:
        """Apply all pending migrations in transaction blocks."""
        applied_now = []

        with self.manager.connection() as conn:
            self.ensure_migration_table(conn)
            applied = self.get_applied_migrations(conn)

            for mig in ALL_MIGRATIONS:
                if mig.migration_id in applied:
                    continue

                logger.info(f"Applying migration: {mig.migration_id} — {mig.description}")
                cur = conn.cursor()
                try:
                    for sql in mig.up_sqls:
                        sql_clean = sql.strip()
                        if sql_clean:
                            try:
                                cur.execute(sql_clean)
                            except Exception as e:
                                # Ignore table already exists if rerun
                                err_str = str(e)
                                if "already exists" in err_str.lower() or "SQL0601N" in err_str:
                                    logger.warning(f"Table/index already exists, skipping statement: {e}")
                                else:
                                    raise

                    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    cur.execute(
                        "INSERT INTO GITMIND_SCHEMA_MIGRATIONS (MIGRATION_ID, DESCRIPTION, APPLIED_AT) VALUES (?, ?, ?)",
                        (mig.migration_id, mig.description, now),
                    )
                    conn.commit()
                    applied_now.append(mig.migration_id)
                finally:
                    cur.close()

        return applied_now

    def verify_schema(self) -> dict[str, bool]:
        """Verify presence of all expected tables in Db2."""
        expected_tables = [
            "GITMIND_REPOSITORIES",
            "GITMIND_ARTIFACTS",
            "GITMIND_RELATIONS",
            "GITMIND_INDEX_RUNS",
            "GITMIND_AGENT_RUNS",
            "GITMIND_FINDINGS",
            "GITMIND_FINDING_EVIDENCE",
            "GITMIND_AUDIT_EVENTS",
            config.DB2_VECTOR_TABLE,
        ]
        status = {}
        with self.manager.connection() as conn:
            cur = conn.cursor()
            try:
                for table in expected_tables:
                    cur.execute(
                        "SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = ? AND TABNAME = ?",
                        (self.manager.schema, table),
                    )
                    status[table] = bool(cur.fetchone())
            finally:
                cur.close()
        return status

