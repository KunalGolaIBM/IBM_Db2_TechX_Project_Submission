"""IBM Db2 Persistence Adapter for CloudChange.

Implements high-performance, ACID-compliant persistence of infrastructure change
assessment models using the official Python ibm_db driver with parameterized SQL.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.app.db2.config import Db2Config
from backend.app.db2.connection import Db2ConnectionManager
from backend.app.db2.schema import init_db2_schema
from backend.app.models.run import Run, RunStatus


class Db2PersistenceAdapter:
    """Dedicated persistence adapter interfacing CloudChange domain models with IBM Db2."""

    def __init__(
        self,
        config: Optional[Db2Config] = None,
        connection_manager: Optional[Db2ConnectionManager] = None,
    ) -> None:
        self.config = config or Db2Config.from_env()
        self.conn_manager = connection_manager or Db2ConnectionManager(self.config)

    def init_schema(self) -> None:
        """Initialize the Db2 relational schema idempotently."""
        conn = self.conn_manager.connect()
        try:
            init_db2_schema(
                conn=conn,
                connection_manager=self.conn_manager,
                schema_name=self.config.schema_name,
            )
        finally:
            self.conn_manager.close(conn)

    def save_run(self, run: Run) -> Run:
        """Persist or update a complete Run and its normalized child entities within an atomic Db2 transaction."""
        summary = run.summary
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.conn_manager.transaction() as conn:
            # 1. Check if run already exists in cc_runs
            check_sql = "SELECT run_id FROM cc_runs WHERE run_id = ?"
            stmt = self.conn_manager.execute_statement(conn, check_sql, (run.run_id,))
            existing = self.conn_manager.fetch_one_assoc(stmt)

            status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
            summary_json_str = summary.model_dump_json()
            raw_run_json_str = run.model_dump_json()

            if existing:
                # Update parent run header
                update_run_sql = """
                    UPDATE cc_runs
                    SET status = ?,
                        total_changes = ?,
                        action_create = ?,
                        action_update = ?,
                        action_delete = ?,
                        action_replace = ?,
                        findings_count = ?,
                        findings_high = ?,
                        findings_medium = ?,
                        findings_low = ?,
                        findings_info = ?,
                        unsupported_count = ?,
                        noop_count = ?,
                        read_count = ?,
                        summary_json = ?,
                        raw_run_json = ?,
                        updated_at = CURRENT TIMESTAMP
                    WHERE run_id = ?
                """
                update_params = (
                    status_val,
                    summary.total_changes,
                    summary.actions.CREATE,
                    summary.actions.UPDATE,
                    summary.actions.DELETE,
                    summary.actions.REPLACE,
                    summary.findings_count,
                    summary.findings_by_severity.HIGH,
                    summary.findings_by_severity.MEDIUM,
                    summary.findings_by_severity.LOW,
                    summary.findings_by_severity.INFO,
                    summary.unsupported_count,
                    summary.noop_count,
                    summary.read_count,
                    summary_json_str,
                    raw_run_json_str,
                    run.run_id,
                )
                self.conn_manager.execute_statement(conn, update_run_sql, update_params)

                # Delete dependent child entries to refresh state
                self.conn_manager.execute_statement(conn, "DELETE FROM cc_canonical_changes WHERE run_id = ?", (run.run_id,))
                self.conn_manager.execute_statement(conn, "DELETE FROM cc_impact_findings WHERE run_id = ?", (run.run_id,))
                self.conn_manager.execute_statement(conn, "DELETE FROM cc_predictions WHERE run_id = ?", (run.run_id,))
                self.conn_manager.execute_statement(conn, "DELETE FROM cc_verification_results WHERE run_id = ?", (run.run_id,))
                audit_event_type = f"RUN_UPDATED_{status_val}"
            else:
                # Insert parent run header
                insert_run_sql = """
                    INSERT INTO cc_runs (
                        run_id, created_at, status, total_changes,
                        action_create, action_update, action_delete, action_replace,
                        findings_count, findings_high, findings_medium, findings_low, findings_info,
                        unsupported_count, noop_count, read_count, summary_json, raw_run_json, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT TIMESTAMP)
                """
                insert_params = (
                    run.run_id,
                    run.created_at,
                    status_val,
                    summary.total_changes,
                    summary.actions.CREATE,
                    summary.actions.UPDATE,
                    summary.actions.DELETE,
                    summary.actions.REPLACE,
                    summary.findings_count,
                    summary.findings_by_severity.HIGH,
                    summary.findings_by_severity.MEDIUM,
                    summary.findings_by_severity.LOW,
                    summary.findings_by_severity.INFO,
                    summary.unsupported_count,
                    summary.noop_count,
                    summary.read_count,
                    summary_json_str,
                    raw_run_json_str,
                )
                self.conn_manager.execute_statement(conn, insert_run_sql, insert_params)
                audit_event_type = "RUN_CREATED"

            # 2. Insert canonical changes
            if run.changes:
                insert_change_sql = """
                    INSERT INTO cc_canonical_changes (
                        change_id, run_id, resource_address, resource_type,
                        action, requires_replacement, diffs_json, before_json, after_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                for change in run.changes:
                    change_id = str(uuid.uuid4())
                    action_str = change.action.value if hasattr(change.action, "value") else str(change.action)
                    diffs_str = json.dumps([d.model_dump() for d in change.diffs]) if change.diffs else "[]"
                    before_str = json.dumps(change.before) if change.before is not None else None
                    after_str = json.dumps(change.after) if change.after is not None else None
                    repl_int = 1 if change.requires_replacement else 0

                    c_params = (
                        change_id,
                        run.run_id,
                        change.resource_address,
                        change.resource_type,
                        action_str,
                        repl_int,
                        diffs_str,
                        before_str,
                        after_str,
                    )
                    self.conn_manager.execute_statement(conn, insert_change_sql, c_params)

            # 3. Insert impact findings
            if run.findings:
                insert_finding_sql = """
                    INSERT INTO cc_impact_findings (
                        finding_id, run_id, rule_id, rule_version,
                        resource_address, category, severity, title, explanation
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                for finding in run.findings:
                    finding_id = str(uuid.uuid4())
                    cat_str = finding.category.value if hasattr(finding.category, "value") else str(finding.category)
                    sev_str = finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)

                    f_params = (
                        finding_id,
                        run.run_id,
                        finding.rule_id,
                        finding.rule_version,
                        finding.resource_address,
                        cat_str,
                        sev_str,
                        finding.title,
                        finding.explanation,
                    )
                    self.conn_manager.execute_statement(conn, insert_finding_sql, f_params)

            # 4. Insert predictions
            if run.predictions:
                insert_pred_sql = """
                    INSERT INTO cc_predictions (
                        prediction_id, run_id, resource_address, metric,
                        direction, verification_approach, expected_value_json,
                        rationale, evidence_provider, evidence_service,
                        evidence_resource_type, evidence_field
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                for pred in run.predictions:
                    approach_str = (
                        pred.verification_approach.value
                        if hasattr(pred.verification_approach, "value")
                        else str(pred.verification_approach)
                    )
                    exp_val_str = json.dumps(pred.expected_value)

                    p_params = (
                        pred.prediction_id,
                        run.run_id,
                        pred.resource_address,
                        pred.metric,
                        pred.direction,
                        approach_str,
                        exp_val_str,
                        pred.rationale,
                        pred.evidence_requirement.provider,
                        pred.evidence_requirement.service,
                        pred.evidence_requirement.resource_type,
                        pred.evidence_requirement.field,
                    )
                    self.conn_manager.execute_statement(conn, insert_pred_sql, p_params)

            # 5. Insert verification results
            if run.verification_results:
                insert_verif_sql = """
                    INSERT INTO cc_verification_results (
                        result_id, run_id, prediction_id, status,
                        expected_value_json, observed_value_json,
                        explanation, evidence_reference_json, verified_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                for res in run.verification_results:
                    res_id = str(uuid.uuid4())
                    res_status_str = res.status.value if hasattr(res.status, "value") else str(res.status)
                    exp_val_str = json.dumps(res.expected_value)
                    obs_val_str = json.dumps(res.observed_value) if res.observed_value is not None else None
                    ev_ref_str = json.dumps(res.evidence_reference) if res.evidence_reference is not None else None

                    v_params = (
                        res_id,
                        run.run_id,
                        res.prediction_id,
                        res_status_str,
                        exp_val_str,
                        obs_val_str,
                        res.explanation,
                        ev_ref_str,
                        now_iso,
                    )
                    self.conn_manager.execute_statement(conn, insert_verif_sql, v_params)

            # 6. Append immutable audit event
            insert_audit_sql = """
                INSERT INTO cc_audit_events (
                    event_id, run_id, event_type, recorded_at, actor, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?)
            """
            audit_id = str(uuid.uuid4())
            audit_payload = {
                "status": status_val,
                "changes_count": len(run.changes),
                "findings_count": len(run.findings),
                "predictions_count": len(run.predictions),
                "verifications_count": len(run.verification_results),
            }
            a_params = (
                audit_id,
                run.run_id,
                audit_event_type,
                now_iso,
                "cloudchange-engine",
                json.dumps(audit_payload),
            )
            self.conn_manager.execute_statement(conn, insert_audit_sql, a_params)

        return run

    def get_run(self, run_id: str) -> Optional[Run]:
        """Retrieve a Run by its UUID using prepared statement and deserialize."""
        conn = self.conn_manager.connect()
        try:
            sql = "SELECT raw_run_json FROM cc_runs WHERE run_id = ?"
            stmt = self.conn_manager.execute_statement(conn, sql, (run_id,))
            row = self.conn_manager.fetch_one_assoc(stmt)
            if not row or not row.get("raw_run_json"):
                return None
            return Run.model_validate_json(row["raw_run_json"])
        finally:
            self.conn_manager.close(conn)

    def list_runs(
        self,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> list[Run]:
        """List persisted runs ordered by creation timestamp."""
        conn = self.conn_manager.connect()
        try:
            if status:
                sql = (
                    "SELECT raw_run_json FROM cc_runs "
                    "WHERE status = ? "
                    "ORDER BY created_at DESC "
                    f"FETCH FIRST {int(limit)} ROWS ONLY"
                )
                stmt = self.conn_manager.execute_statement(conn, sql, (status,))
            else:
                sql = (
                    "SELECT raw_run_json FROM cc_runs "
                    "ORDER BY created_at DESC "
                    f"FETCH FIRST {int(limit)} ROWS ONLY"
                )
                stmt = self.conn_manager.execute_statement(conn, sql)

            rows = self.conn_manager.fetch_all_assoc(stmt)
            runs: list[Run] = []
            for row in rows:
                raw_json = row.get("raw_run_json")
                if raw_json:
                    runs.append(Run.model_validate_json(raw_json))
            return runs
        finally:
            self.conn_manager.close(conn)

    def count_runs(self) -> int:
        """Count total stored runs."""
        conn = self.conn_manager.connect()
        try:
            sql = "SELECT COUNT(*) AS total_count FROM cc_runs"
            stmt = self.conn_manager.execute_statement(conn, sql)
            row = self.conn_manager.fetch_one_assoc(stmt)
            if row and "total_count" in row:
                return int(row["total_count"])
            return 0
        finally:
            self.conn_manager.close(conn)

    def delete_run(self, run_id: str) -> bool:
        """Delete a run and cascade delete its associated entities in Db2."""
        with self.conn_manager.transaction() as conn:
            sql = "DELETE FROM cc_runs WHERE run_id = ?"
            self.conn_manager.execute_statement(conn, sql, (run_id,))
            return True

    def clear(self) -> None:
        """Clear all stored runs (used for test isolation)."""
        with self.conn_manager.transaction() as conn:
            self.conn_manager.execute_statement(conn, "DELETE FROM cc_runs")

    # -------------------------------------------------------------------------
    # Governance & Relational Analytics Queries
    # -------------------------------------------------------------------------

    def get_audit_history(self, run_id: str) -> list[dict[str, Any]]:
        """Retrieve the immutable chronological audit log for a given run."""
        conn = self.conn_manager.connect()
        try:
            sql = """
                SELECT event_id, run_id, event_type, recorded_at, actor, payload_json
                FROM cc_audit_events
                WHERE run_id = ?
                ORDER BY recorded_at ASC
            """
            stmt = self.conn_manager.execute_statement(conn, sql, (run_id,))
            rows = self.conn_manager.fetch_all_assoc(stmt)
            for r in rows:
                if r.get("payload_json"):
                    try:
                        r["payload"] = json.loads(r["payload_json"])
                    except Exception:
                        r["payload"] = r["payload_json"]
            return rows
        finally:
            self.conn_manager.close(conn)

    def get_findings_by_severity(self, severity: str) -> list[dict[str, Any]]:
        """Query all impact findings across infrastructure runs matching a severity level."""
        conn = self.conn_manager.connect()
        try:
            sql = """
                SELECT finding_id, run_id, rule_id, rule_version,
                       resource_address, category, severity, title, explanation
                FROM cc_impact_findings
                WHERE severity = ?
                ORDER BY resource_address ASC
            """
            stmt = self.conn_manager.execute_statement(conn, sql, (severity.upper(),))
            return self.conn_manager.fetch_all_assoc(stmt)
        finally:
            self.conn_manager.close(conn)

    def get_high_risk_changes(self) -> list[dict[str, Any]]:
        """Query all canonical changes that trigger destructive resource replacement."""
        conn = self.conn_manager.connect()
        try:
            sql = """
                SELECT change_id, run_id, resource_address, resource_type,
                       action, requires_replacement
                FROM cc_canonical_changes
                WHERE requires_replacement = 1
                ORDER BY resource_address ASC
            """
            stmt = self.conn_manager.execute_statement(conn, sql)
            return self.conn_manager.fetch_all_assoc(stmt)
        finally:
            self.conn_manager.close(conn)

    def get_verification_metrics(self) -> dict[str, Any]:
        """Aggregate post-deployment verification outcomes across all runs."""
        conn = self.conn_manager.connect()
        try:
            sql = """
                SELECT status, COUNT(*) AS status_count
                FROM cc_verification_results
                GROUP BY status
            """
            stmt = self.conn_manager.execute_statement(conn, sql)
            rows = self.conn_manager.fetch_all_assoc(stmt)
            metrics = {"total": 0, "by_status": {}}
            for row in rows:
                st = row.get("status", "UNKNOWN")
                cnt = int(row.get("status_count", 0))
                metrics["by_status"][st] = cnt
                metrics["total"] += cnt
            return metrics
        finally:
            self.conn_manager.close(conn)
