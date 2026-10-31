
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "quantumdefense.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database():
    with get_connection() as conn:

        # Security events
        conn.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                source_ip TEXT NOT NULL,
                severity TEXT NOT NULL,
                description TEXT NOT NULL,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Security alerts
        conn.execute("""
            CREATE TABLE IF NOT EXISTS security_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                alert_message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id)
                    REFERENCES security_events(id)
            )
        """)

        # Machine learning analysis results
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ml_analysis_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                anomaly_detected INTEGER NOT NULL,
                anomaly_score REAL NOT NULL,
                algorithm TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (event_id)
                    REFERENCES security_events(id)
            )
        """)


def save_event(event):
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO security_events
            (event_type, source_ip, severity, description)
            VALUES (?, ?, ?, ?)
        """, (
            event["event_type"],
            event["source_ip"],
            event["severity"],
            event["description"]
        ))

        return cursor.lastrowid


def get_events():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM security_events
            ORDER BY id DESC
        """).fetchall()

        return [dict(row) for row in rows]


def save_alert(event_id, message):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO security_alerts
            (event_id, alert_message)
            VALUES (?, ?)
        """, (event_id, message))


def get_alerts():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM security_alerts
            ORDER BY id DESC
        """).fetchall()

        return [dict(row) for row in rows]


def save_ml_result(event_id, result):
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO ml_analysis_results
            (
                event_id,
                anomaly_detected,
                anomaly_score,
                algorithm
            )
            VALUES (?, ?, ?, ?)
        """, (
            event_id,
            int(result["anomaly_detected"]),
            result["anomaly_score"],
            result["method"]
        ))

        return cursor.lastrowid


def get_ml_results():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                m.id,
                m.event_id,
                m.anomaly_detected,
                m.anomaly_score,
                m.algorithm,
                m.created_at,
                e.event_type,
                e.source_ip
            FROM ml_analysis_results m
            JOIN security_events e
                ON m.event_id = e.id
            ORDER BY m.id DESC
        """).fetchall()

        return [dict(row) for row in rows]
