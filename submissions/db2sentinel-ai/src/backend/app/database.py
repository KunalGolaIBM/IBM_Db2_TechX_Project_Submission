import sqlite3
import hashlib
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from .config import settings
from .db2_connector import Db2Connector

logger = logging.getLogger("db2sentinel.database")

class DatabaseManager:
    """
    Unified database manager for Db2Sentinel AI.
    Transparently prioritizes real IBM Db2 via ibm_db.
    When IBM Db2 is offline or unavailable in the local environment,
    provides a fully compliant local relational fallback so all security
    investigation workflows, APIs, and tests function reliably.
    """
    def __init__(self):
        self.db2 = Db2Connector(
            host=settings.DB2_HOST,
            port=settings.DB2_PORT,
            database=settings.DB2_DATABASE,
            username=settings.DB2_USERNAME,
            password=settings.DB2_PASSWORD,
            security=settings.DB2_SECURITY,
            ssl_cert=settings.DB2_SSL_CERTIFICATE
        )
        self.active_mode = "initializing"
        self._sqlite_path = "sentinel_local.db"
        self.initialize()

    def initialize(self):
        """Attempts connection to Db2; initializes local relational fallback if offline."""
        connected = self.db2.connect()
        if connected:
            self.active_mode = "db2_connected"
            logger.info("DatabaseManager active in IBM Db2 mode.")
        else:
            if settings.DB2_DEMO_FALLBACK:
                self.active_mode = "demo_fallback"
                logger.info("IBM Db2 offline. Initializing local relational fallback for demonstration.")
                self._init_sqlite_schema()
            else:
                self.active_mode = "error"
                logger.error("IBM Db2 offline and demo fallback is disabled.")

    def _init_sqlite_schema(self):
        """Initializes the exact Sentinel schema in SQLite for local demonstration."""
        conn = sqlite3.connect(self._sqlite_path)
        cursor = conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS SENTINEL_EVENTS (
                EVENT_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                EVENT_TYPE TEXT NOT NULL,
                USERNAME TEXT NOT NULL,
                SOURCE_IP TEXT,
                DATABASE_NAME TEXT DEFAULT 'SENTINELDB',
                SQL_OPERATION TEXT,
                OBJECT_NAME TEXT,
                STATUS TEXT NOT NULL,
                EVENT_TIMESTAMP TEXT NOT NULL,
                SEVERITY TEXT DEFAULT 'LOW',
                EVENT_SOURCE TEXT DEFAULT 'DB2_AUDIT_FACILITY',
                RAW_DETAILS TEXT
            );

            CREATE TABLE IF NOT EXISTS SENTINEL_ALERTS (
                ALERT_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                EVENT_ID INTEGER,
                ALERT_NAME TEXT NOT NULL,
                DESCRIPTION TEXT NOT NULL,
                SEVERITY TEXT NOT NULL,
                RISK_SCORE REAL NOT NULL,
                STATUS TEXT DEFAULT 'OPEN',
                CREATED_AT TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS SENTINEL_INCIDENTS (
                INCIDENT_ID TEXT PRIMARY KEY,
                TITLE TEXT NOT NULL,
                DESCRIPTION TEXT,
                SEVERITY TEXT NOT NULL,
                RISK_SCORE REAL NOT NULL,
                STATUS TEXT DEFAULT 'INVESTIGATING',
                ASSIGNED_TO TEXT DEFAULT 'LangGraph Supervisor',
                CREATED_AT TEXT NOT NULL,
                UPDATED_AT TEXT NOT NULL,
                AI_SUMMARY TEXT
            );

            CREATE TABLE IF NOT EXISTS SENTINEL_INVESTIGATIONS (
                INVESTIGATION_ID TEXT PRIMARY KEY,
                INCIDENT_ID TEXT NOT NULL,
                AGENT_NAME TEXT NOT NULL,
                FINDINGS TEXT NOT NULL,
                RECOMMENDATION TEXT,
                CONFIDENCE REAL DEFAULT 0.90,
                CREATED_AT TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS SENTINEL_APPROVALS (
                APPROVAL_ID TEXT PRIMARY KEY,
                INCIDENT_ID TEXT NOT NULL,
                PROPOSED_ACTION TEXT NOT NULL,
                REQUESTED_BY TEXT DEFAULT 'Response Agent',
                APPROVAL_STATUS TEXT DEFAULT 'PENDING',
                REVIEWER TEXT,
                REVIEWED_AT TEXT,
                AUDIT_NOTES TEXT
            );

            CREATE TABLE IF NOT EXISTS SENTINEL_AUDIT_LOG (
                LOG_ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ACTION_TAKEN TEXT NOT NULL,
                EXECUTED_BY TEXT NOT NULL,
                DB2_QUERY TEXT,
                EXECUTION_TIMESTAMP TEXT NOT NULL,
                VERIFICATION_HASH TEXT
            );
        """)
        conn.commit()
        conn.close()

    def get_status(self) -> Dict[str, Any]:
        """Returns the current database engine status, connection parameters, and health."""
        if self.active_mode == "db2_connected":
            db2_diag = self.db2.check_connection()
            return {
                "active_mode": "db2_connected",
                "engine": "IBM Db2 11.5 / 12.1",
                "connected": True,
                "is_demo_mode": False,
                "details": db2_diag
            }
        elif self.active_mode == "demo_fallback":
            return {
                "active_mode": "demo_fallback",
                "engine": "IBM Db2 Simulation & Local Demonstration Relational Store",
                "connected": True,
                "is_demo_mode": True,
                "message": "IBM Db2 server not reached locally; operating in high-fidelity demonstration fallback mode.",
                "db2_target": f"{settings.DB2_HOST}:{settings.DB2_PORT}/{settings.DB2_DATABASE}"
            }
        else:
            return {
                "active_mode": "error",
                "engine": "None",
                "connected": False,
                "is_demo_mode": False,
                "error": "Failed to connect to IBM Db2 and fallback is disabled."
            }

    # =========================================================================
    # EVENT OPERATIONS
    # =========================================================================

    def get_events(self, limit: int = 100, offset: int = 0, event_type: Optional[str] = None, username: Optional[str] = None, severity: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM SENTINEL_EVENTS WHERE 1=1"
        params = []
        if event_type:
            query += " AND EVENT_TYPE = ?"
            params.append(event_type)
        if username:
            query += " AND USERNAME = ?"
            params.append(username)
        if severity:
            query += " AND SEVERITY = ?"
            params.append(severity)
        query += " ORDER BY EVENT_ID DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        if self.active_mode == "db2_connected":
            # Db2 syntax for pagination: FETCH FIRST n ROWS ONLY
            db2_sql = f"SELECT * FROM SENTINEL_EVENTS WHERE 1=1"
            db2_params = []
            if event_type:
                db2_sql += " AND EVENT_TYPE = ?"
                db2_params.append(event_type)
            if username:
                db2_sql += " AND USERNAME = ?"
                db2_params.append(username)
            if severity:
                db2_sql += " AND SEVERITY = ?"
                db2_params.append(severity)
            db2_sql += f" ORDER BY EVENT_ID DESC FETCH FIRST {limit} ROWS ONLY"
            return self.db2.execute_query(db2_sql, tuple(db2_params))
        else:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return [{k.lower(): v for k, v in r.items()} for r in rows]

    def get_event(self, event_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM SENTINEL_EVENTS WHERE EVENT_ID = ?"
        if self.active_mode == "db2_connected":
            results = self.db2.execute_query(sql, (event_id,))
            return results[0] if results else None
        else:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (event_id,))
            row = cursor.fetchone()
            conn.close()
            return {k.lower(): v for k, v in dict(row).items()} if row else None

    def insert_event(self, data: Dict[str, Any]) -> int:
        ts = data.get("event_timestamp") or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        details = data.get("raw_details")
        if isinstance(details, (dict, list)):
            details = json.dumps(details)

        sql = """
            INSERT INTO SENTINEL_EVENTS (EVENT_TYPE, USERNAME, SOURCE_IP, DATABASE_NAME, SQL_OPERATION, OBJECT_NAME, STATUS, EVENT_TIMESTAMP, SEVERITY, EVENT_SOURCE, RAW_DETAILS)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            data.get("event_type", "UNKNOWN"),
            data.get("username", "ANONYMOUS"),
            data.get("source_ip", "127.0.0.1"),
            data.get("database_name", settings.DB2_DATABASE),
            data.get("sql_operation", "NONE"),
            data.get("object_name", "UNKNOWN"),
            data.get("status", "SUCCESS"),
            ts,
            data.get("severity", "LOW"),
            data.get("event_source", "APPLICATION"),
            details
        )
        if self.active_mode == "db2_connected":
            self.db2.execute_statement(sql, params)
            last_id = self.db2.execute_query("SELECT IDENTITY_VAL_LOCAL() AS ID FROM SYSIBM.SYSDUMMY1")
            return int(last_id[0].get("id", 1)) if last_id else 1
        else:
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return new_id

    # =========================================================================
    # ALERT OPERATIONS
    # =========================================================================

    def get_alerts(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM SENTINEL_ALERTS ORDER BY ALERT_ID DESC LIMIT ? OFFSET ?"
        if self.active_mode == "db2_connected":
            db2_sql = f"SELECT * FROM SENTINEL_ALERTS ORDER BY ALERT_ID DESC FETCH FIRST {limit} ROWS ONLY"
            return self.db2.execute_query(db2_sql)
        else:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (limit, offset))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return [{k.lower(): v for k, v in r.items()} for r in rows]

    def insert_alert(self, data: Dict[str, Any]) -> int:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
            INSERT INTO SENTINEL_ALERTS (EVENT_ID, ALERT_NAME, DESCRIPTION, SEVERITY, RISK_SCORE, STATUS, CREATED_AT)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            data.get("event_id"),
            data.get("alert_name", "Security Alert"),
            data.get("description", "Potential suspicious activity detected"),
            data.get("severity", "MEDIUM"),
            float(data.get("risk_score", 50.0)),
            data.get("status", "OPEN"),
            now
        )
        if self.active_mode == "db2_connected":
            self.db2.execute_statement(sql, params)
            last_id = self.db2.execute_query("SELECT IDENTITY_VAL_LOCAL() AS ID FROM SYSIBM.SYSDUMMY1")
            return int(last_id[0].get("id", 1)) if last_id else 1
        else:
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return new_id

    # =========================================================================
    # INCIDENT OPERATIONS
    # =========================================================================

    def get_incidents(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM SENTINEL_INCIDENTS ORDER BY CREATED_AT DESC LIMIT ? OFFSET ?"
        if self.active_mode == "db2_connected":
            db2_sql = f"SELECT * FROM SENTINEL_INCIDENTS ORDER BY CREATED_AT DESC FETCH FIRST {limit} ROWS ONLY"
            return self.db2.execute_query(db2_sql)
        else:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (limit, offset))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return [{k.lower(): v for k, v in r.items()} for r in rows]

    def get_incident(self, incident_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM SENTINEL_INCIDENTS WHERE INCIDENT_ID = ?"
        if self.active_mode == "db2_connected":
            results = self.db2.execute_query(sql, (incident_id,))
            return results[0] if results else None
        else:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (incident_id,))
            row = cursor.fetchone()
            conn.close()
            return {k.lower(): v for k, v in dict(row).items()} if row else None

    def insert_incident(self, data: Dict[str, Any]) -> str:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        inc_id = data.get("incident_id") or f"INC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        sql = """
            INSERT INTO SENTINEL_INCIDENTS (INCIDENT_ID, TITLE, DESCRIPTION, SEVERITY, RISK_SCORE, STATUS, ASSIGNED_TO, CREATED_AT, UPDATED_AT, AI_SUMMARY)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            inc_id,
            data.get("title", "Database Security Incident"),
            data.get("description", "Automated incident created by detection engine"),
            data.get("severity", "HIGH"),
            float(data.get("risk_score", 75.0)),
            data.get("status", "INVESTIGATING"),
            data.get("assigned_to", "LangGraph Supervisor"),
            now,
            now,
            data.get("ai_summary", "")
        )
        if self.active_mode == "db2_connected":
            self.db2.execute_statement(sql, params)
        else:
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
        return inc_id

    def update_incident(self, incident_id: str, updates: Dict[str, Any]):
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        set_clauses = ["UPDATED_AT = ?"]
        params = [now]
        for k, v in updates.items():
            set_clauses.append(f"{k.upper()} = ?")
            params.append(v)
        params.append(incident_id)
        sql = f"UPDATE SENTINEL_INCIDENTS SET {', '.join(set_clauses)} WHERE INCIDENT_ID = ?"

        if self.active_mode == "db2_connected":
            self.db2.execute_statement(sql, tuple(params))
        else:
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute(sql, tuple(params))
            conn.commit()
            conn.close()

    # =========================================================================
    # INVESTIGATION FINDINGS
    # =========================================================================

    def get_investigations(self, incident_id: str) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM SENTINEL_INVESTIGATIONS WHERE INCIDENT_ID = ? ORDER BY CREATED_AT ASC"
        if self.active_mode == "db2_connected":
            return self.db2.execute_query(sql, (incident_id,))
        else:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, (incident_id,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return [{k.lower(): v for k, v in r.items()} for r in rows]

    def insert_investigation(self, data: Dict[str, Any]) -> str:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        inv_id = data.get("investigation_id") or f"INV-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:17]}"
        sql = """
            INSERT INTO SENTINEL_INVESTIGATIONS (INVESTIGATION_ID, INCIDENT_ID, AGENT_NAME, FINDINGS, RECOMMENDATION, CONFIDENCE, CREATED_AT)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            inv_id,
            data.get("incident_id"),
            data.get("agent_name", "AI Agent"),
            data.get("findings", ""),
            data.get("recommendation", ""),
            float(data.get("confidence", 0.90)),
            now
        )
        if self.active_mode == "db2_connected":
            self.db2.execute_statement(sql, params)
        else:
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
        return inv_id

    # =========================================================================
    # HUMAN-IN-THE-LOOP APPROVALS
    # =========================================================================

    def get_approvals(self, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM SENTINEL_APPROVALS ORDER BY APPROVAL_ID DESC"
        if self.active_mode == "db2_connected":
            return self.db2.execute_query(f"{sql} FETCH FIRST {limit} ROWS ONLY")
        else:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"{sql} LIMIT ?", (limit,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return [{k.lower(): v for k, v in r.items()} for r in rows]

    def insert_approval(self, data: Dict[str, Any]) -> str:
        app_id = data.get("approval_id") or f"APP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        sql = """
            INSERT INTO SENTINEL_APPROVALS (APPROVAL_ID, INCIDENT_ID, PROPOSED_ACTION, REQUESTED_BY, APPROVAL_STATUS, REVIEWER, REVIEWED_AT, AUDIT_NOTES)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            app_id,
            data.get("incident_id"),
            data.get("proposed_action", "Review access"),
            data.get("requested_by", "Response Agent"),
            data.get("approval_status", "PENDING"),
            data.get("reviewer"),
            data.get("reviewed_at"),
            data.get("audit_notes")
        )
        if self.active_mode == "db2_connected":
            self.db2.execute_statement(sql, params)
        else:
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()
        return app_id

    def update_approval(self, approval_id: str, status: str, reviewer: str, notes: Optional[str] = None):
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
            UPDATE SENTINEL_APPROVALS 
            SET APPROVAL_STATUS = ?, REVIEWER = ?, REVIEWED_AT = ?, AUDIT_NOTES = ?
            WHERE APPROVAL_ID = ?
        """
        params = (status, reviewer, now, notes or f"Action {status.lower()} by {reviewer}", approval_id)
        if self.active_mode == "db2_connected":
            self.db2.execute_statement(sql, params)
        else:
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            conn.close()

    # =========================================================================
    # AUDIT TRAIL
    # =========================================================================

    def log_audit(self, action: str, executed_by: str, query: Optional[str] = None) -> int:
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        raw_to_hash = f"{action}:{executed_by}:{now}:{query or ''}"
        verif_hash = hashlib.sha256(raw_to_hash.encode()).hexdigest()

        sql = """
            INSERT INTO SENTINEL_AUDIT_LOG (ACTION_TAKEN, EXECUTED_BY, DB2_QUERY, EXECUTION_TIMESTAMP, VERIFICATION_HASH)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (action, executed_by, query or "N/A", now, verif_hash)
        if self.active_mode == "db2_connected":
            self.db2.execute_statement(sql, params)
            last_id = self.db2.execute_query("SELECT IDENTITY_VAL_LOCAL() AS ID FROM SYSIBM.SYSDUMMY1")
            return int(last_id[0].get("id", 1)) if last_id else 1
        else:
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            new_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return new_id

    def get_audit_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM SENTINEL_AUDIT_LOG ORDER BY LOG_ID DESC"
        if self.active_mode == "db2_connected":
            return self.db2.execute_query(f"{sql} FETCH FIRST {limit} ROWS ONLY")
        else:
            conn = sqlite3.connect(self._sqlite_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(f"{sql} LIMIT ?", (limit,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return [{k.lower(): v for k, v in r.items()} for r in rows]

    # =========================================================================
    # METRICS & DEMO MANAGEMENT
    # =========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Calculates live executive metrics from the database."""
        if self.active_mode == "db2_connected":
            evt_c = self.db2.execute_query("SELECT COUNT(*) AS CNT FROM SENTINEL_EVENTS")
            alrt_c = self.db2.execute_query("SELECT COUNT(*) AS CNT FROM SENTINEL_ALERTS")
            inc_c = self.db2.execute_query("SELECT COUNT(*) AS CNT FROM SENTINEL_INCIDENTS")
            crit_c = self.db2.execute_query("SELECT COUNT(*) AS CNT FROM SENTINEL_INCIDENTS WHERE SEVERITY = 'CRITICAL'")
            avg_r = self.db2.execute_query("SELECT AVG(RISK_SCORE) AS SCORE FROM SENTINEL_ALERTS")
            return {
                "total_events": int(evt_c[0].get("cnt", 0)) if evt_c else 0,
                "total_alerts": int(alrt_c[0].get("cnt", 0)) if alrt_c else 0,
                "open_incidents": int(inc_c[0].get("cnt", 0)) if inc_c else 0,
                "critical_incidents": int(crit_c[0].get("cnt", 0)) if crit_c else 0,
                "avg_risk_score": round(float(avg_r[0].get("score") or 0.0), 1) if avg_r else 0.0
            }
        else:
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM SENTINEL_EVENTS")
            evt_c = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM SENTINEL_ALERTS")
            alrt_c = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM SENTINEL_INCIDENTS")
            inc_c = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM SENTINEL_INCIDENTS WHERE SEVERITY = 'CRITICAL'")
            crit_c = cursor.fetchone()[0]
            cursor.execute("SELECT AVG(RISK_SCORE) FROM SENTINEL_ALERTS")
            avg_r = cursor.fetchone()[0] or 0.0
            conn.close()
            return {
                "total_events": evt_c,
                "total_alerts": alrt_c,
                "open_incidents": inc_c,
                "critical_incidents": crit_c,
                "avg_risk_score": round(float(avg_r), 1)
            }

    def seed_demo_data(self):
        """Seeds standard controlled baseline and attack demonstration data."""
        # 1. Baseline normal event
        self.insert_event({
            "event_type": "AUTHENTICATION",
            "username": "APP_SERVICE_USER",
            "source_ip": "10.0.1.15",
            "sql_operation": "CONNECT",
            "object_name": "SENTINELDB",
            "status": "SUCCESS",
            "severity": "LOW",
            "event_source": "DB2_AUDIT_FACILITY",
            "raw_details": {"auth_type": "SERVER_ENCRYPT", "client_pid": 4812}
        })
        # 2. Baseline reporting query
        self.insert_event({
            "event_type": "QUERY_EXECUTION",
            "username": "REPORT_USER",
            "source_ip": "10.0.2.40",
            "sql_operation": "SELECT",
            "object_name": "MONTHLY_SALES_REPORTS",
            "status": "SUCCESS",
            "severity": "LOW",
            "event_source": "DB2_ACTIVITY_MONITOR",
            "raw_details": {"rows_read": 320, "cpu_time_ms": 18}
        })
        # 3. Brute force failed logins from 198.51.100.44
        for attempt in range(1, 7):
            self.insert_event({
                "event_type": "AUTHENTICATION",
                "username": "DB2ADMIN",
                "source_ip": "198.51.100.44",
                "sql_operation": "CONNECT",
                "object_name": "SENTINELDB",
                "status": "FAILURE",
                "severity": "HIGH",
                "event_source": "DB2_AUDIT_FACILITY",
                "raw_details": {"reason": "INVALID_CREDENTIALS", "attempt": attempt, "simulated": True}
            })
        # 4. Off-hours login
        self.insert_event({
            "event_type": "AUTHENTICATION",
            "username": "REPORT_USER",
            "source_ip": "198.51.100.44",
            "sql_operation": "CONNECT",
            "object_name": "SENTINELDB",
            "status": "SUCCESS",
            "severity": "MEDIUM",
            "event_source": "DB2_AUDIT_FACILITY",
            "raw_details": {"note": "Off-hours login from foreign subnet", "simulated": True}
        })
        # 5. Sensitive financial table read (28,400 rows)
        self.insert_event({
            "event_type": "SENSITIVE_ACCESS",
            "username": "REPORT_USER",
            "source_ip": "198.51.100.44",
            "sql_operation": "SELECT",
            "object_name": "CUSTOMER_FINANCIAL_RECORDS",
            "status": "SUCCESS",
            "severity": "CRITICAL",
            "event_source": "DB2_ACTIVITY_MONITOR",
            "raw_details": {"rows_read": 28400, "baseline_avg": 350, "z_score": 8.42, "simulated": True}
        })
        # 6. Privilege catalog reconnaissance query
        self.insert_event({
            "event_type": "PRIVILEGE_RECON",
            "username": "REPORT_USER",
            "source_ip": "198.51.100.44",
            "sql_operation": "SELECT",
            "object_name": "SYSCAT.DBAUTH",
            "status": "SUCCESS",
            "severity": "HIGH",
            "event_source": "DB2_ACTIVITY_MONITOR",
            "raw_details": {"mitre_tactic": "T1087_Account_Discovery", "simulated": True}
        })
        self.log_audit("DEMO_SEEDED", "System Admin", "Populated controlled test events for detection demonstration")

    def reset_demo_data(self):
        """Clears test events without dropping schema structure."""
        if self.active_mode == "db2_connected":
            self.db2.execute_statement("DELETE FROM SENTINEL_APPROVALS")
            self.db2.execute_statement("DELETE FROM SENTINEL_INVESTIGATIONS")
            self.db2.execute_statement("DELETE FROM SENTINEL_INCIDENTS")
            self.db2.execute_statement("DELETE FROM SENTINEL_ALERTS")
            self.db2.execute_statement("DELETE FROM SENTINEL_EVENTS")
        else:
            conn = sqlite3.connect(self._sqlite_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM SENTINEL_APPROVALS")
            cursor.execute("DELETE FROM SENTINEL_INVESTIGATIONS")
            cursor.execute("DELETE FROM SENTINEL_INCIDENTS")
            cursor.execute("DELETE FROM SENTINEL_ALERTS")
            cursor.execute("DELETE FROM SENTINEL_EVENTS")
            conn.commit()
            conn.close()
        self.log_audit("DEMO_RESET", "System Admin", "Cleared demo test dataset")

# Global singleton
db_manager = DatabaseManager()
