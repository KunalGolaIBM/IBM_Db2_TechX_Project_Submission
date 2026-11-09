import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from backend.app.database.session import db_session

logger = logging.getLogger("cloud_loop.repository.ingestion")

class IngestionRepository:
    def create_run(self, run_id: str, source: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sql = """
            INSERT INTO INGESTION_RUNS (
                ID, SOURCE, RECORDS_PROCESSED, RECORDS_INSERTED, RECORDS_UPDATED,
                RECORDS_REJECTED, STATUS, STARTED_AT
            ) VALUES (?, ?, 0, 0, 0, 0, 'running', ?)
        """
        db_session.execute(sql, [run_id, source, now])

    def update_progress(self, run_id: str, processed: int, inserted: int, updated: int, rejected: int) -> None:
        sql = """
            UPDATE INGESTION_RUNS SET
                RECORDS_PROCESSED = ?,
                RECORDS_INSERTED = ?,
                RECORDS_UPDATED = ?,
                RECORDS_REJECTED = ?
            WHERE ID = ?
        """
        db_session.execute(sql, [processed, inserted, updated, rejected, run_id])

    def complete_run(
        self,
        run_id: str,
        processed: int,
        inserted: int,
        updated: int,
        rejected: int,
        status: str = "completed",
        error_summary: Optional[str] = None
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sql = """
            UPDATE INGESTION_RUNS SET
                RECORDS_PROCESSED = ?,
                RECORDS_INSERTED = ?,
                RECORDS_UPDATED = ?,
                RECORDS_REJECTED = ?,
                STATUS = ?,
                ERROR_SUMMARY = ?,
                COMPLETED_AT = ?
            WHERE ID = ?
        """
        db_session.execute(sql, [processed, inserted, updated, rejected, status, error_summary, now, run_id])

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM INGESTION_RUNS WHERE ID = ?"
        rows = db_session.query(sql, [run_id])
        if not rows:
            return None
        r = rows[0]
        return {
            "id": r.get("ID") or r.get("id"),
            "source": r.get("SOURCE") or r.get("source"),
            "records_processed": r.get("RECORDS_PROCESSED") or r.get("records_processed") or 0,
            "records_inserted": r.get("RECORDS_INSERTED") or r.get("records_inserted") or 0,
            "records_updated": r.get("RECORDS_UPDATED") or r.get("records_updated") or 0,
            "records_rejected": r.get("RECORDS_REJECTED") or r.get("records_rejected") or 0,
            "status": r.get("STATUS") or r.get("status"),
            "error_summary": r.get("ERROR_SUMMARY") or r.get("error_summary"),
            "started_at": r.get("STARTED_AT") or r.get("started_at"),
            "completed_at": r.get("COMPLETED_AT") or r.get("completed_at"),
        }

    def list_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM INGESTION_RUNS ORDER BY ROWID DESC LIMIT ?"
        rows = db_session.query(sql, [limit])
        return [
            {
                "id": r.get("ID") or r.get("id"),
                "source": r.get("SOURCE") or r.get("source"),
                "records_processed": r.get("RECORDS_PROCESSED") or r.get("records_processed") or 0,
                "records_inserted": r.get("RECORDS_INSERTED") or r.get("records_inserted") or 0,
                "records_updated": r.get("RECORDS_UPDATED") or r.get("records_updated") or 0,
                "records_rejected": r.get("RECORDS_REJECTED") or r.get("records_rejected") or 0,
                "status": r.get("STATUS") or r.get("status"),
                "error_summary": r.get("ERROR_SUMMARY") or r.get("error_summary"),
                "started_at": r.get("STARTED_AT") or r.get("started_at"),
                "completed_at": r.get("COMPLETED_AT") or r.get("completed_at"),
            }
            for r in rows
        ]

ingestion_repo = IngestionRepository()

