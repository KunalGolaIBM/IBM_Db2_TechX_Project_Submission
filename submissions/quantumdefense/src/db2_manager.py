
import os
import ibm_db
from dotenv import load_dotenv

load_dotenv()


def get_db2_connection():
    """Create a connection to IBM Db2."""

    required = [
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD"
    ]

    missing = [key for key in required if not os.getenv(key)]

    if missing:
        raise RuntimeError(
            "Missing Db2 configuration: " + ", ".join(missing)
        )

    connection_string = (
        f"DATABASE={os.getenv('DB_NAME')};"
        f"HOSTNAME={os.getenv('DB_HOST')};"
        f"PORT={os.getenv('DB_PORT')};"
        f"PROTOCOL=TCPIP;"
        f"UID={os.getenv('DB_USER')};"
        f"PWD={os.getenv('DB_PASSWORD')};"
    )

    if os.getenv("DB_SSL", "false").lower() == "true":
        connection_string += "SECURITY=SSL;"

    return ibm_db.connect(connection_string, "", "")


def save_security_event(event):
    """Save a security event in IBM Db2."""

    conn = get_db2_connection()

    try:
        sql = """
            INSERT INTO SECURITY_EVENTS
            (EVENT_TYPE, SOURCE_IP, SEVERITY, DESCRIPTION)
            VALUES (?, ?, ?, ?)
        """

        stmt = ibm_db.prepare(conn, sql)

        ibm_db.execute(stmt, (
            event["event_type"],
            event["source_ip"],
            event["severity"],
            event.get("description", "")
        ))

        identity_stmt = ibm_db.exec_immediate(
            conn,
            "SELECT IDENTITY_VAL_LOCAL() AS EVENT_ID "
            "FROM SYSIBM.SYSDUMMY1"
        )

        identity = ibm_db.fetch_assoc(identity_stmt)

        if not identity or identity.get("EVENT_ID") is None:
            raise RuntimeError("Could not retrieve the event ID")

        event_id = int(identity["EVENT_ID"])

        ibm_db.commit(conn)
        return event_id

    except Exception:
        ibm_db.rollback(conn)
        raise

    finally:
        ibm_db.close(conn)


def save_security_alert(event_id, message):
    """Save a security alert in IBM Db2."""

    conn = get_db2_connection()

    try:
        sql = """
            INSERT INTO SECURITY_ALERTS
            (EVENT_ID, ALERT_MESSAGE)
            VALUES (?, ?)
        """

        stmt = ibm_db.prepare(conn, sql)
        ibm_db.execute(stmt, (event_id, message))

        ibm_db.commit(conn)

    except Exception:
        ibm_db.rollback(conn)
        raise

    finally:
        ibm_db.close(conn)


def get_security_events():
    """Retrieve security events."""

    conn = get_db2_connection()

    try:
        sql = """
            SELECT EVENT_ID, EVENT_TYPE, SOURCE_IP,
                   SEVERITY, DESCRIPTION, DETECTED_AT
            FROM SECURITY_EVENTS
            ORDER BY EVENT_ID DESC
        """

        stmt = ibm_db.exec_immediate(conn, sql)
        results = []

        row = ibm_db.fetch_assoc(stmt)

        while row:
            results.append(row)
            row = ibm_db.fetch_assoc(stmt)

        return results

    finally:
        ibm_db.close(conn)


def get_security_alerts():
    """Retrieve security alerts."""

    conn = get_db2_connection()

    try:
        sql = """
            SELECT ALERT_ID, EVENT_ID,
                   ALERT_MESSAGE, CREATED_AT
            FROM SECURITY_ALERTS
            ORDER BY ALERT_ID DESC
        """

        stmt = ibm_db.exec_immediate(conn, sql)
        results = []

        row = ibm_db.fetch_assoc(stmt)

        while row:
            results.append(row)
            row = ibm_db.fetch_assoc(stmt)

        return results

    finally:
        ibm_db.close(conn)


def save_ml_analysis_result(event_id, result):
    """Save machine-learning analysis in IBM Db2."""

    conn = get_db2_connection()

    try:
        sql = """
            INSERT INTO ML_ANALYSIS_RESULTS
            (
                EVENT_ID,
                ANOMALY_DETECTED,
                ANOMALY_SCORE,
                ALGORITHM
            )
            VALUES (?, ?, ?, ?)
        """

        stmt = ibm_db.prepare(conn, sql)

        ibm_db.execute(stmt, (
            event_id,
            int(result["anomaly_detected"]),
            float(result["anomaly_score"]),
            result["method"]
        ))

        ibm_db.commit(conn)

    except Exception:
        ibm_db.rollback(conn)
        raise

    finally:
        ibm_db.close(conn)


def get_ml_analysis_results():
    """Retrieve machine-learning analysis history."""

    conn = get_db2_connection()

    try:
        sql = """
            SELECT
                M.ANALYSIS_ID,
                M.EVENT_ID,
                M.ANOMALY_DETECTED,
                M.ANOMALY_SCORE,
                M.ALGORITHM,
                M.CREATED_AT,
                E.EVENT_TYPE,
                E.SOURCE_IP
            FROM ML_ANALYSIS_RESULTS M
            INNER JOIN SECURITY_EVENTS E
                ON M.EVENT_ID = E.EVENT_ID
            ORDER BY M.ANALYSIS_ID DESC
        """

        stmt = ibm_db.exec_immediate(conn, sql)
        results = []

        row = ibm_db.fetch_assoc(stmt)

        while row:
            results.append(row)
            row = ibm_db.fetch_assoc(stmt)

        return results

    finally:
        ibm_db.close(conn)


def get_security_statistics():
    """Calculate security event statistics."""

    conn = get_db2_connection()

    try:
        sql = """
            SELECT
                COUNT(*) AS TOTAL_EVENTS,
                SUM(CASE WHEN SEVERITY = 'Critical'
                    THEN 1 ELSE 0 END) AS CRITICAL_EVENTS,
                SUM(CASE WHEN SEVERITY = 'High'
                    THEN 1 ELSE 0 END) AS HIGH_EVENTS
            FROM SECURITY_EVENTS
        """

        stmt = ibm_db.exec_immediate(conn, sql)
        return ibm_db.fetch_assoc(stmt)

    finally:
        ibm_db.close(conn)
