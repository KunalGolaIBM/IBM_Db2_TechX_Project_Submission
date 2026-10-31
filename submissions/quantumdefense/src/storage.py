
import os
from dotenv import load_dotenv

load_dotenv()

BACKEND = os.getenv("DB_BACKEND", "sqlite").lower()


def initialize_storage():
    if BACKEND == "ibmdb":
        from db2_manager import get_db2_connection
        import ibm_db

        conn = get_db2_connection()
        try:
            print("IBM Db2 connection successful")
        finally:
            ibm_db.close(conn)
        return

    from database import initialize_database
    initialize_database()
    print("Using SQLite development database")


def save_event(event):
    if BACKEND == "ibmdb":
        from db2_manager import save_security_event
        return save_security_event(event)

    from database import save_event as sqlite_save_event
    return sqlite_save_event(event)


def save_alert(event_id, message):
    if BACKEND == "ibmdb":
        from db2_manager import save_security_alert
        return save_security_alert(event_id, message)

    from database import save_alert as sqlite_save_alert
    return sqlite_save_alert(event_id, message)


def get_events():
    if BACKEND == "ibmdb":
        from db2_manager import get_security_events
        rows = get_security_events()

        return [
            {
                "id": row["EVENT_ID"],
                "event_type": row["EVENT_TYPE"],
                "source_ip": row["SOURCE_IP"],
                "severity": row["SEVERITY"],
                "description": row["DESCRIPTION"],
                "detected_at": row["DETECTED_AT"]
            }
            for row in rows
        ]

    from database import get_events as sqlite_get_events
    return sqlite_get_events()


def get_alerts():
    if BACKEND == "ibmdb":
        from db2_manager import get_security_alerts
        rows = get_security_alerts()

        return [
            {
                "id": row["ALERT_ID"],
                "event_id": row["EVENT_ID"],
                "alert_message": row["ALERT_MESSAGE"],
                "created_at": row["CREATED_AT"]
            }
            for row in rows
        ]

    from database import get_alerts as sqlite_get_alerts
    return sqlite_get_alerts()


def save_ml_result(event_id, result):
    if BACKEND == "ibmdb":
        from db2_manager import save_ml_analysis_result
        return save_ml_analysis_result(event_id, result)

    from database import save_ml_result as sqlite_save_ml_result
    return sqlite_save_ml_result(event_id, result)


def get_ml_results():
    if BACKEND == "ibmdb":
        from db2_manager import get_ml_analysis_results
        rows = get_ml_analysis_results()

        return [
            {
                "id": row["ANALYSIS_ID"],
                "event_id": row["EVENT_ID"],
                "anomaly_detected": row["ANOMALY_DETECTED"],
                "anomaly_score": row["ANOMALY_SCORE"],
                "algorithm": row["ALGORITHM"],
                "created_at": row["CREATED_AT"],
                "event_type": row["EVENT_TYPE"],
                "source_ip": row["SOURCE_IP"]
            }
            for row in rows
        ]

    from database import get_ml_results as sqlite_get_ml_results
    return sqlite_get_ml_results()
