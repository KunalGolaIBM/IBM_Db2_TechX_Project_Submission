"""
MediTwin AI — Db2 Repository Layer
All database CRUD operations using parameterized prepared statements.
Never concatenates user input into SQL.
"""

import json
import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Try ibm_db import
try:
    import ibm_db
    IBM_DB_AVAILABLE = True
except ImportError:
    IBM_DB_AVAILABLE = False


class Db2Repository:
    """Repository for all Db2 CRUD operations using prepared statements."""

    def __init__(self, connection):
        """
        Args:
            connection: A Db2Connection instance (from db.connection).
        """
        self.connection = connection

    # ================================================================
    # PATIENT operations
    # ================================================================

    def create_patient(self, demo_code: str, display_name: str,
                       birth_year: Optional[int] = None) -> Optional[int]:
        """Insert a new patient. Returns patient_id."""
        sql = """
            INSERT INTO PATIENT (demo_code, display_name, birth_year)
            VALUES (?, ?, ?)
        """
        try:
            stmt = ibm_db.prepare(self.connection.conn, sql)
            ibm_db.bind_param(stmt, 1, demo_code)
            ibm_db.bind_param(stmt, 2, display_name)
            ibm_db.bind_param(stmt, 3, birth_year)
            ibm_db.execute(stmt)

            # Get the generated ID
            id_stmt = ibm_db.exec_immediate(
                self.connection.conn, "VALUES IDENTITY_VAL_LOCAL()"
            )
            row = ibm_db.fetch_tuple(id_stmt)
            patient_id = int(row[0]) if row else None
            self.connection.commit()
            return patient_id
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error creating patient: {e}")
            raise

    def get_patient(self, patient_id: int) -> Optional[Dict]:
        """Get a patient by ID."""
        sql = "SELECT * FROM PATIENT WHERE patient_id = ?"
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, patient_id)
        ibm_db.execute(stmt)
        row = ibm_db.fetch_assoc(stmt)
        return dict(row) if row else None

    def get_patient_by_code(self, demo_code: str) -> Optional[Dict]:
        """Get a patient by demo code."""
        sql = "SELECT * FROM PATIENT WHERE demo_code = ?"
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, demo_code)
        ibm_db.execute(stmt)
        row = ibm_db.fetch_assoc(stmt)
        return dict(row) if row else None

    def list_patients(self) -> List[Dict]:
        """Get all patients."""
        sql = "SELECT * FROM PATIENT ORDER BY patient_id"
        stmt = ibm_db.exec_immediate(self.connection.conn, sql)
        return self.connection.fetch_all(stmt)

    # ================================================================
    # DOCUMENT operations
    # ================================================================

    def create_document(self, patient_id: int, file_name: str,
                        document_type: str = "LAB_REPORT",
                        extracted_text: str = None,
                        source_hash: str = None) -> Optional[int]:
        """
        Insert a new document with duplicate hash protection.
        Returns document_id or existing document_id if duplicate.
        """
        # First check if document with same hash already exists for this patient
        if source_hash:
            existing = self.get_document_by_hash(patient_id, source_hash)
            if existing:
                logger.info(f"Document with hash {source_hash[:10]} already exists (ID: {existing['DOCUMENT_ID']})")
                return existing["DOCUMENT_ID"]

        sql = """
            INSERT INTO DOCUMENT (patient_id, file_name, document_type,
                                  extracted_text, source_hash)
            VALUES (?, ?, ?, ?, ?)
        """
        try:
            stmt = ibm_db.prepare(self.connection.conn, sql)
            ibm_db.bind_param(stmt, 1, patient_id)
            ibm_db.bind_param(stmt, 2, file_name)
            ibm_db.bind_param(stmt, 3, document_type)
            ibm_db.bind_param(stmt, 4, extracted_text)
            ibm_db.bind_param(stmt, 5, source_hash)
            ibm_db.execute(stmt)

            id_stmt = ibm_db.exec_immediate(
                self.connection.conn, "VALUES IDENTITY_VAL_LOCAL()"
            )
            row = ibm_db.fetch_tuple(id_stmt)
            doc_id = int(row[0]) if row else None
            self.connection.commit()
            return doc_id
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Error creating document: {e}")
            raise

    def get_document_by_hash(self, patient_id: int, source_hash: str) -> Optional[Dict]:
        """Find an existing document for a patient by SHA-256 hash."""
        sql = "SELECT * FROM DOCUMENT WHERE patient_id = ? AND source_hash = ?"
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, patient_id)
        ibm_db.bind_param(stmt, 2, source_hash)
        ibm_db.execute(stmt)
        row = ibm_db.fetch_assoc(stmt)
        return dict(row) if row else None

    def update_document_status(self, document_id: int, status: str,
                                extracted_text: str = None):
        """Update document parse status and optionally the extracted text."""
        if extracted_text is not None:
            sql = """
                UPDATE DOCUMENT SET parse_status = ?, extracted_text = ?
                WHERE document_id = ?
            """
            stmt = ibm_db.prepare(self.connection.conn, sql)
            ibm_db.bind_param(stmt, 1, status)
            ibm_db.bind_param(stmt, 2, extracted_text)
            ibm_db.bind_param(stmt, 3, document_id)
        else:
            sql = "UPDATE DOCUMENT SET parse_status = ? WHERE document_id = ?"
            stmt = ibm_db.prepare(self.connection.conn, sql)
            ibm_db.bind_param(stmt, 1, status)
            ibm_db.bind_param(stmt, 2, document_id)
        ibm_db.execute(stmt)
        self.connection.commit()

    def get_document(self, document_id: int) -> Optional[Dict]:
        """Get a document by ID."""
        sql = "SELECT * FROM DOCUMENT WHERE document_id = ?"
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, document_id)
        ibm_db.execute(stmt)
        row = ibm_db.fetch_assoc(stmt)
        return dict(row) if row else None

    def list_documents(self, patient_id: int = None) -> List[Dict]:
        """List documents, optionally filtered by patient."""
        if patient_id:
            sql = "SELECT * FROM DOCUMENT WHERE patient_id = ? ORDER BY uploaded_at DESC"
            stmt = ibm_db.prepare(self.connection.conn, sql)
            ibm_db.bind_param(stmt, 1, patient_id)
            ibm_db.execute(stmt)
        else:
            sql = "SELECT * FROM DOCUMENT ORDER BY uploaded_at DESC"
            stmt = ibm_db.exec_immediate(self.connection.conn, sql)
        return self.connection.fetch_all(stmt)

    # ================================================================
    # OBSERVATION operations
    # ================================================================

    def create_observation(self, patient_id: int, document_id: int,
                           test_name: str, test_code: str = None,
                           value_numeric: float = None, value_text: str = None,
                           unit: str = None, reference_low: float = None,
                           reference_high: float = None,
                           observed_at: str = None, source_page: int = None,
                           source_snippet: str = None,
                           extraction_confidence: float = None) -> Optional[int]:
        """
        Insert a new observation with PENDING status.
        Guarantees cross-patient integrity: document must belong to patient_id.
        Preserves original values in original_value_numeric and original_unit.
        """
        # Cross-patient verification
        doc = self.get_document(document_id)
        if not doc:
            raise ValueError(f"Referenced document {document_id} does not exist.")
        doc_patient = doc.get("PATIENT_ID") or doc.get("patient_id")
        if int(doc_patient) != int(patient_id):
            raise ValueError(
                f"Cross-patient integrity violation: Document {document_id} belongs to "
                f"patient {doc_patient}, cannot attach observation for patient {patient_id}."
            )

        sql = """
            INSERT INTO OBSERVATION
                (patient_id, document_id, test_code, test_name,
                 value_numeric, value_text, unit,
                 original_value_numeric, original_unit,
                 reference_low, reference_high, observed_at,
                 source_page, source_snippet, extraction_confidence,
                 review_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
        """
        try:
            stmt = ibm_db.prepare(self.connection.conn, sql)
            ibm_db.bind_param(stmt, 1, patient_id)
            ibm_db.bind_param(stmt, 2, document_id)
            ibm_db.bind_param(stmt, 3, test_code)
            ibm_db.bind_param(stmt, 4, test_name)
            ibm_db.bind_param(stmt, 5, value_numeric)
            ibm_db.bind_param(stmt, 6, value_text)
            ibm_db.bind_param(stmt, 7, unit)
            ibm_db.bind_param(stmt, 8, value_numeric)  # original_value_numeric
            ibm_db.bind_param(stmt, 9, unit)           # original_unit
            ibm_db.bind_param(stmt, 10, reference_low)
            ibm_db.bind_param(stmt, 11, reference_high)
            ibm_db.bind_param(stmt, 12, observed_at)
            ibm_db.bind_param(stmt, 13, source_page)
            ibm_db.bind_param(stmt, 14, source_snippet)
            ibm_db.bind_param(stmt, 15, extraction_confidence)
            ibm_db.execute(stmt)

            id_stmt = ibm_db.exec_immediate(
                self.connection.conn, "VALUES IDENTITY_VAL_LOCAL()"
            )
            row = ibm_db.fetch_tuple(id_stmt)
            obs_id = int(row[0]) if row else None
            return obs_id
        except Exception as e:
            logger.error(f"Error creating observation: {e}")
            raise

    def update_observation_review(self, observation_id: int, status: str,
                                   reviewed_by: str = "CLINICAL_REVIEWER",
                                   value_numeric: Optional[float] = None,
                                   value_text: Optional[str] = None,
                                   unit: Optional[str] = None,
                                   observed_at: Optional[str] = None,
                                   test_code: Optional[str] = None,
                                   reviewer_notes: Optional[str] = None):
        """
        Update observation review status, apply validated corrections,
        and atomically record audit event within a single transaction.
        Handles value_numeric == 0.0 correctly without erring as false/None.
        """
        # Fetch current record first to detect changes
        current = self.get_observation(observation_id)
        if not current:
            raise ValueError(f"Observation {observation_id} not found.")

        # Determine corrected values
        orig_val = current.get("VALUE_NUMERIC")
        new_val = value_numeric if value_numeric is not None else orig_val
        new_code = test_code if test_code is not None else current.get("TEST_CODE")
        new_unit = unit if unit is not None else current.get("UNIT")
        new_date = observed_at if observed_at is not None else current.get("OBSERVED_AT")

        is_corrected = (
            (value_numeric is not None and float(value_numeric) != float(orig_val if orig_val is not None else -999999)) or
            (unit is not None and unit != current.get("UNIT")) or
            (test_code is not None and test_code != current.get("TEST_CODE")) or
            (observed_at is not None and str(observed_at) != str(current.get("OBSERVED_AT")))
        )

        corr_val = new_val if is_corrected else current.get("CORRECTED_VALUE_NUMERIC")
        corr_unit = new_unit if is_corrected else current.get("CORRECTED_UNIT")

        sql = """
            UPDATE OBSERVATION
            SET review_status = ?,
                reviewed_by = ?,
                reviewed_at = CURRENT_TIMESTAMP,
                value_numeric = ?,
                value_text = COALESCE(?, value_text),
                unit = ?,
                observed_at = ?,
                test_code = ?,
                corrected_value_numeric = ?,
                corrected_unit = ?
            WHERE observation_id = ?
        """
        with self.connection.transaction():
            stmt = ibm_db.prepare(self.connection.conn, sql)
            ibm_db.bind_param(stmt, 1, status)
            ibm_db.bind_param(stmt, 2, reviewed_by)
            ibm_db.bind_param(stmt, 3, new_val)
            ibm_db.bind_param(stmt, 4, value_text)
            ibm_db.bind_param(stmt, 5, new_unit)
            ibm_db.bind_param(stmt, 6, new_date)
            ibm_db.bind_param(stmt, 7, new_code)
            ibm_db.bind_param(stmt, 8, corr_val)
            ibm_db.bind_param(stmt, 9, corr_unit)
            ibm_db.bind_param(stmt, 10, observation_id)
            ibm_db.execute(stmt)

            # Atomically write audit record in the exact same transaction
            audit_sql = """
                INSERT INTO AUDIT_LOG (actor_id, action, entity_type, entity_id, details_json)
                VALUES (?, ?, 'OBSERVATION', ?, ?)
            """
            audit_stmt = ibm_db.prepare(self.connection.conn, audit_sql)
            action_name = f"OBSERVATION_{status}"
            details = {
                "reviewer": reviewed_by,
                "notes": reviewer_notes,
                "is_corrected": is_corrected,
                "original_value": orig_val,
                "new_value": new_val,
                "original_unit": current.get("UNIT"),
                "new_unit": new_unit,
                "original_code": current.get("TEST_CODE"),
                "new_code": new_code,
            }
            details_json = json.dumps(details)
            ibm_db.bind_param(audit_stmt, 1, reviewed_by)
            ibm_db.bind_param(audit_stmt, 2, action_name)
            ibm_db.bind_param(audit_stmt, 3, observation_id)
            ibm_db.bind_param(audit_stmt, 4, details_json)
            ibm_db.execute(audit_stmt)

    def get_pending_observations(self, patient_id: int = None) -> List[Dict]:
        """Get observations awaiting review."""
        if patient_id:
            sql = """
                SELECT o.*, d.file_name
                FROM OBSERVATION o
                JOIN DOCUMENT d ON o.document_id = d.document_id
                WHERE o.review_status = 'PENDING' AND o.patient_id = ?
                ORDER BY o.created_at DESC
            """
            stmt = ibm_db.prepare(self.connection.conn, sql)
            ibm_db.bind_param(stmt, 1, patient_id)
            ibm_db.execute(stmt)
        else:
            sql = """
                SELECT o.*, d.file_name
                FROM OBSERVATION o
                JOIN DOCUMENT d ON o.document_id = d.document_id
                WHERE o.review_status = 'PENDING'
                ORDER BY o.created_at DESC
            """
            stmt = ibm_db.exec_immediate(self.connection.conn, sql)
        return self.connection.fetch_all(stmt)

    def get_approved_observations(self, patient_id: int,
                                   test_code: str = None,
                                   start_date: str = None,
                                   end_date: str = None) -> List[Dict]:
        """Get approved observations for a patient, with optional filters."""
        conditions = ["o.review_status = 'APPROVED'", "o.patient_id = ?"]
        params = [patient_id]

        if test_code:
            conditions.append("o.test_code = ?")
            params.append(test_code)
        if start_date:
            conditions.append("o.observed_at >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("o.observed_at <= ?")
            params.append(end_date)

        where = " AND ".join(conditions)
        sql = f"""
            SELECT o.*, d.file_name
            FROM OBSERVATION o
            JOIN DOCUMENT d ON o.document_id = d.document_id
            WHERE {where}
            ORDER BY o.observed_at ASC, o.observation_id ASC
        """
        stmt = ibm_db.prepare(self.connection.conn, sql)
        for i, p in enumerate(params, 1):
            ibm_db.bind_param(stmt, i, p)
        ibm_db.execute(stmt)
        return self.connection.fetch_all(stmt)

    def get_observation(self, observation_id: int) -> Optional[Dict]:
        """Get a single observation by ID."""
        sql = """
            SELECT o.*, d.file_name
            FROM OBSERVATION o
            JOIN DOCUMENT d ON o.document_id = d.document_id
            WHERE o.observation_id = ?
        """
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, observation_id)
        ibm_db.execute(stmt)
        row = ibm_db.fetch_assoc(stmt)
        return dict(row) if row else None

    def get_distinct_test_codes(self, patient_id: int) -> List[Dict]:
        """Get distinct test codes/names for a patient (approved only)."""
        sql = """
            SELECT DISTINCT test_code, test_name
            FROM OBSERVATION
            WHERE patient_id = ? AND review_status = 'APPROVED'
            ORDER BY test_name
        """
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, patient_id)
        ibm_db.execute(stmt)
        return self.connection.fetch_all(stmt)

    def get_latest_observation(self, patient_id: int,
                                test_code: str) -> Optional[Dict]:
        """Get the most recent approved observation for a metric."""
        sql = """
            SELECT o.*, d.file_name
            FROM OBSERVATION o
            JOIN DOCUMENT d ON o.document_id = d.document_id
            WHERE o.patient_id = ? AND o.test_code = ?
                  AND o.review_status = 'APPROVED'
            ORDER BY o.observed_at DESC, o.observation_id DESC
            FETCH FIRST 1 ROW ONLY
        """
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, patient_id)
        ibm_db.bind_param(stmt, 2, test_code)
        ibm_db.execute(stmt)
        row = ibm_db.fetch_assoc(stmt)
        return dict(row) if row else None

    # ================================================================
    # TIMELINE_EVENT operations
    # ================================================================

    def create_timeline_event(self, patient_id: int, event_type: str,
                               event_time: str, title: str,
                               summary: str = None,
                               related_document_id: int = None) -> Optional[int]:
        """Insert a timeline event."""
        sql = """
            INSERT INTO TIMELINE_EVENT
                (patient_id, event_type, event_time, title, summary, related_document_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, patient_id)
        ibm_db.bind_param(stmt, 2, event_type)
        ibm_db.bind_param(stmt, 3, event_time)
        ibm_db.bind_param(stmt, 4, title)
        ibm_db.bind_param(stmt, 5, summary)
        ibm_db.bind_param(stmt, 6, related_document_id)
        ibm_db.execute(stmt)
        self.connection.commit()

        id_stmt = ibm_db.exec_immediate(
            self.connection.conn, "VALUES IDENTITY_VAL_LOCAL()"
        )
        row = ibm_db.fetch_tuple(id_stmt)
        return int(row[0]) if row else None

    def get_timeline(self, patient_id: int) -> List[Dict]:
        """Get timeline events for a patient."""
        sql = """
            SELECT * FROM TIMELINE_EVENT
            WHERE patient_id = ?
            ORDER BY event_time DESC
        """
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, patient_id)
        ibm_db.execute(stmt)
        return self.connection.fetch_all(stmt)

    # ================================================================
    # AUDIT_LOG operations
    # ================================================================

    def log_audit(self, action: str, entity_type: str,
                  entity_id: int = None, actor_id: str = "SYSTEM",
                  details: dict = None):
        """Append an audit log entry."""
        sql = """
            INSERT INTO AUDIT_LOG (actor_id, action, entity_type, entity_id, details_json)
            VALUES (?, ?, ?, ?, ?)
        """
        details_json = json.dumps(details) if details else None
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, actor_id)
        ibm_db.bind_param(stmt, 2, action)
        ibm_db.bind_param(stmt, 3, entity_type)
        ibm_db.bind_param(stmt, 4, entity_id)
        ibm_db.bind_param(stmt, 5, details_json)
        ibm_db.execute(stmt)
        self.connection.commit()

    def get_audit_log(self, entity_type: str = None,
                      limit: int = 50) -> List[Dict]:
        """Get recent audit log entries."""
        if entity_type:
            sql = f"""
                SELECT * FROM AUDIT_LOG
                WHERE entity_type = ?
                ORDER BY logged_at DESC
                FETCH FIRST {int(limit)} ROWS ONLY
            """
            stmt = ibm_db.prepare(self.connection.conn, sql)
            ibm_db.bind_param(stmt, 1, entity_type)
            ibm_db.execute(stmt)
        else:
            sql = f"""
                SELECT * FROM AUDIT_LOG
                ORDER BY logged_at DESC
                FETCH FIRST {int(limit)} ROWS ONLY
            """
            stmt = ibm_db.exec_immediate(self.connection.conn, sql)
        return self.connection.fetch_all(stmt)

    # ================================================================
    # STATISTICS for Dashboard
    # ================================================================

    def get_dashboard_stats(self) -> Dict[str, int]:
        """Get summary counts for the dashboard."""
        stats = {}
        queries = {
            "total_patients": "SELECT COUNT(*) AS cnt FROM PATIENT",
            "total_documents": "SELECT COUNT(*) AS cnt FROM DOCUMENT",
            "total_observations": "SELECT COUNT(*) AS cnt FROM OBSERVATION WHERE review_status = 'APPROVED'",
            "pending_reviews": "SELECT COUNT(*) AS cnt FROM OBSERVATION WHERE review_status = 'PENDING'",
        }
        for key, sql in queries.items():
            try:
                stmt = ibm_db.exec_immediate(self.connection.conn, sql)
                row = ibm_db.fetch_assoc(stmt)
                stats[key] = int(row["CNT"]) if row else 0
            except Exception:
                stats[key] = 0
        return stats

    def search_observations_by_keyword(self, patient_id: int,
                                        keyword: str) -> List[Dict]:
        """Search approved observations by test name keyword."""
        sql = """
            SELECT o.*, d.file_name
            FROM OBSERVATION o
            JOIN DOCUMENT d ON o.document_id = d.document_id
            WHERE o.patient_id = ?
              AND o.review_status = 'APPROVED'
              AND UPPER(o.test_name) LIKE UPPER(?)
            ORDER BY o.observed_at DESC
        """
        stmt = ibm_db.prepare(self.connection.conn, sql)
        ibm_db.bind_param(stmt, 1, patient_id)
        ibm_db.bind_param(stmt, 2, f"%{keyword}%")
        ibm_db.execute(stmt)
        return self.connection.fetch_all(stmt)
