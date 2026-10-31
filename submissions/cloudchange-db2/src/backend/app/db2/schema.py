"""IBM Db2 Relational Schema Definitions and Initializer for CloudChange.

Provides idempotent table and index creation for storing complete infrastructure
change analysis runs, canonical changes, impact findings, verifiable predictions,
verification outcomes, and compliance audit events.
"""

import logging
from typing import Any, Optional

from backend.app.db2.connection import Db2ConnectionManager, Db2ExecutionError

logger = logging.getLogger(__name__)

# Complete DDL statements for CloudChange IBM Db2 relational storage
TABLE_DEFINITIONS: list[tuple[str, str]] = [
    (
        "cc_runs",
        """
        CREATE TABLE cc_runs (
            run_id VARCHAR(64) NOT NULL PRIMARY KEY,
            created_at VARCHAR(64) NOT NULL,
            status VARCHAR(32) NOT NULL,
            total_changes INT NOT NULL DEFAULT 0,
            action_create INT NOT NULL DEFAULT 0,
            action_update INT NOT NULL DEFAULT 0,
            action_delete INT NOT NULL DEFAULT 0,
            action_replace INT NOT NULL DEFAULT 0,
            findings_count INT NOT NULL DEFAULT 0,
            findings_high INT NOT NULL DEFAULT 0,
            findings_medium INT NOT NULL DEFAULT 0,
            findings_low INT NOT NULL DEFAULT 0,
            findings_info INT NOT NULL DEFAULT 0,
            unsupported_count INT NOT NULL DEFAULT 0,
            noop_count INT NOT NULL DEFAULT 0,
            read_count INT NOT NULL DEFAULT 0,
            summary_json CLOB(1M),
            raw_run_json CLOB(10M),
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT TIMESTAMP
        )
        """,
    ),
    (
        "cc_canonical_changes",
        """
        CREATE TABLE cc_canonical_changes (
            change_id VARCHAR(64) NOT NULL PRIMARY KEY,
            run_id VARCHAR(64) NOT NULL,
            resource_address VARCHAR(255) NOT NULL,
            resource_type VARCHAR(128) NOT NULL,
            action VARCHAR(32) NOT NULL,
            requires_replacement SMALLINT NOT NULL DEFAULT 0,
            diffs_json CLOB(2M),
            before_json CLOB(2M),
            after_json CLOB(2M),
            CONSTRAINT fk_change_run FOREIGN KEY (run_id)
                REFERENCES cc_runs (run_id) ON DELETE CASCADE
        )
        """,
    ),
    (
        "cc_impact_findings",
        """
        CREATE TABLE cc_impact_findings (
            finding_id VARCHAR(64) NOT NULL PRIMARY KEY,
            run_id VARCHAR(64) NOT NULL,
            rule_id VARCHAR(64) NOT NULL,
            rule_version VARCHAR(32) NOT NULL,
            resource_address VARCHAR(255) NOT NULL,
            category VARCHAR(32) NOT NULL,
            severity VARCHAR(32) NOT NULL,
            title VARCHAR(255) NOT NULL,
            explanation CLOB(1M),
            CONSTRAINT fk_finding_run FOREIGN KEY (run_id)
                REFERENCES cc_runs (run_id) ON DELETE CASCADE
        )
        """,
    ),
    (
        "cc_predictions",
        """
        CREATE TABLE cc_predictions (
            prediction_id VARCHAR(64) NOT NULL PRIMARY KEY,
            run_id VARCHAR(64) NOT NULL,
            resource_address VARCHAR(255),
            metric VARCHAR(128) NOT NULL,
            direction VARCHAR(64),
            verification_approach VARCHAR(64) NOT NULL,
            expected_value_json CLOB(1M) NOT NULL,
            rationale CLOB(1M) NOT NULL,
            evidence_provider VARCHAR(64) NOT NULL,
            evidence_service VARCHAR(64) NOT NULL,
            evidence_resource_type VARCHAR(128) NOT NULL,
            evidence_field VARCHAR(128) NOT NULL,
            CONSTRAINT fk_prediction_run FOREIGN KEY (run_id)
                REFERENCES cc_runs (run_id) ON DELETE CASCADE
        )
        """,
    ),
    (
        "cc_verification_results",
        """
        CREATE TABLE cc_verification_results (
            result_id VARCHAR(64) NOT NULL PRIMARY KEY,
            run_id VARCHAR(64) NOT NULL,
            prediction_id VARCHAR(64) NOT NULL,
            status VARCHAR(32) NOT NULL,
            expected_value_json CLOB(1M),
            observed_value_json CLOB(1M),
            explanation CLOB(1M),
            evidence_reference_json CLOB(2M),
            verified_at VARCHAR(64),
            CONSTRAINT fk_verif_run FOREIGN KEY (run_id)
                REFERENCES cc_runs (run_id) ON DELETE CASCADE
        )
        """,
    ),
    (
        "cc_audit_events",
        """
        CREATE TABLE cc_audit_events (
            event_id VARCHAR(64) NOT NULL PRIMARY KEY,
            run_id VARCHAR(64) NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            recorded_at VARCHAR(64) NOT NULL,
            actor VARCHAR(128) NOT NULL DEFAULT 'system',
            payload_json CLOB(2M),
            CONSTRAINT fk_audit_run FOREIGN KEY (run_id)
                REFERENCES cc_runs (run_id) ON DELETE CASCADE
        )
        """,
    ),
]

# Secondary B-Tree performance and governance indexes
INDEX_DEFINITIONS: list[tuple[str, str]] = [
    ("idx_cc_runs_status", "CREATE INDEX idx_cc_runs_status ON cc_runs (status)"),
    ("idx_cc_runs_created", "CREATE INDEX idx_cc_runs_created ON cc_runs (created_at DESC)"),
    ("idx_cc_changes_run", "CREATE INDEX idx_cc_changes_run ON cc_canonical_changes (run_id)"),
    ("idx_cc_changes_addr", "CREATE INDEX idx_cc_changes_addr ON cc_canonical_changes (resource_address)"),
    ("idx_cc_findings_run", "CREATE INDEX idx_cc_findings_run ON cc_impact_findings (run_id)"),
    ("idx_cc_findings_sev", "CREATE INDEX idx_cc_findings_sev ON cc_impact_findings (severity)"),
    ("idx_cc_findings_cat", "CREATE INDEX idx_cc_findings_cat ON cc_impact_findings (category)"),
    ("idx_cc_predictions_run", "CREATE INDEX idx_cc_predictions_run ON cc_predictions (run_id)"),
    ("idx_cc_verif_run", "CREATE INDEX idx_cc_verif_run ON cc_verification_results (run_id)"),
    ("idx_cc_verif_status", "CREATE INDEX idx_cc_verif_status ON cc_verification_results (status)"),
    ("idx_cc_audit_run", "CREATE INDEX idx_cc_audit_run ON cc_audit_events (run_id)"),
]


def _is_already_exists_error(err_str: str) -> bool:
    """Check if the Db2 error indicates the object already exists (idempotent DDL)."""
    err_lower = err_str.lower()
    return any(marker in err_lower for marker in [
        "-601",
        "sql0601n",
        "-605",
        "sql0605n",
        "already exists",
        "duplicate object",
        "42710",
    ])


def init_db2_schema(
    conn: Any,
    connection_manager: Optional[Db2ConnectionManager] = None,
    schema_name: Optional[str] = "CLOUDCHANGE",
) -> None:
    """Initialize the complete CloudChange schema, tables, and indexes in IBM Db2 idempotently."""
    cm = connection_manager or Db2ConnectionManager()

    # 1. Optionally switch current schema
    if schema_name:
        try:
            cm.execute_statement(conn, f"SET CURRENT SCHEMA = {schema_name}")
        except Exception as exc:
            # If schema does not exist, attempt to create it
            if "not found" in str(exc).lower() or "undefined" in str(exc).lower():
                try:
                    cm.execute_statement(conn, f"CREATE SCHEMA {schema_name}")
                    cm.execute_statement(conn, f"SET CURRENT SCHEMA = {schema_name}")
                except Exception:
                    logger.debug("Schema creation fallback encountered; proceeding with default schema.")

    # 2. Idempotently create tables
    for table_name, ddl in TABLE_DEFINITIONS:
        try:
            cm.execute_statement(conn, ddl)
            logger.info("Created Db2 table: %s", table_name)
        except Db2ExecutionError as exc:
            if _is_already_exists_error(str(exc)):
                logger.debug("Table '%s' already exists in Db2.", table_name)
            else:
                raise

    # 3. Idempotently create indexes
    for index_name, ddl in INDEX_DEFINITIONS:
        try:
            cm.execute_statement(conn, ddl)
            logger.info("Created Db2 index: %s", index_name)
        except Db2ExecutionError as exc:
            if _is_already_exists_error(str(exc)):
                logger.debug("Index '%s' already exists in Db2.", index_name)
            else:
                raise
