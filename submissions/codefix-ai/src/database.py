"""
CodeFix AI — IBM Db2 Database Integration Module

This module implements direct integration with IBM Db2 using the official
ibm_db Python driver. It provides parameterized CRUD operations, schema
initialization, connection management, and safe error handling.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from config import Config

logger = logging.getLogger("CodeFixAI.Database")

try:
    import ibm_db  # type: ignore
    IBM_DB_AVAILABLE = True
except ImportError:
    IBM_DB_AVAILABLE = False
    logger.warning("ibm_db driver is not installed.")


def _close_conn(conn):
    """Safely close an IBM Db2 connection handle without bubbling exceptions."""
    if conn and IBM_DB_AVAILABLE:
        try:
            ibm_db.close(conn)
        except Exception:
            pass


def get_connection():
    """
    Establish and return a connection to the IBM Db2 instance.
    Returns the connection handle or None if unavailable/unconfigured.
    """
    if not IBM_DB_AVAILABLE:
        logger.error("ibm_db driver not available.")
        return None

    if not Config.is_db2_configured():
        logger.debug("IBM Db2 is not configured in .env; running in Setup Mode.")
        return None

    conn_str = Config.get_db2_conn_string()
    try:
        conn = ibm_db.connect(conn_str, "", "")
        return conn
    except Exception as e:
        # Sanitize error message to prevent leaking credentials
        logger.error("Failed to connect to IBM Db2 instance.", exc_info=True)
        return None


def check_db2_connection() -> Tuple[bool, str]:
    """
    Test live connectivity to the IBM Db2 database.
    Returns: (is_connected, status_message)
    """
    if not IBM_DB_AVAILABLE:
        return False, "Driver 'ibm_db' is not installed."

    if not Config.is_db2_configured():
        return False, "IBM Db2 credentials not configured in .env (Setup Mode active)."

    conn = get_connection()
    if conn:
        try:
            _close_conn(conn)
            return True, f"Connected to IBM Db2 database '{Config.DB2_DATABASE}' at {Config.DB2_HOSTNAME}:{Config.DB2_PORT}."
        except Exception:
            return True, "Connected to IBM Db2."
    else:
        return False, "Could not establish connection to IBM Db2 instance. Check host, port, credentials, and network/VPN."


def init_db() -> Tuple[bool, str]:
    """
    Initialize the IBM Db2 database schema.
    Creates CODEFIX_HISTORY table and indexes if they do not exist.
    """
    if not Config.is_db2_configured():
        return False, "IBM Db2 credentials not configured. Table creation skipped."

    conn = get_connection()
    if not conn:
        return False, "Could not connect to IBM Db2 to initialize schema."

    create_table_sql = """
    CREATE TABLE CODEFIX_HISTORY (
        ID VARCHAR(36) NOT NULL PRIMARY KEY,
        SESSION_ID VARCHAR(64) NOT NULL,
        LANGUAGE VARCHAR(32) NOT NULL,
        MODE VARCHAR(32) NOT NULL,
        USER_PROMPT CLOB(1048576),
        ORIGINAL_CODE CLOB(1048576),
        ERROR_MESSAGE CLOB(1048576),
        GENERATED_CODE CLOB(1048576),
        EXPLANATION CLOB(1048576),
        MODEL_NAME VARCHAR(64) NOT NULL,
        CREATED_AT TIMESTAMP DEFAULT CURRENT TIMESTAMP
    )
    """

    create_index_sql = """
    CREATE INDEX IDX_CODEFIX_SESSION ON CODEFIX_HISTORY (SESSION_ID, CREATED_AT DESC)
    """

    try:
        # Check if table already exists by executing a test query
        check_sql = "SELECT 1 FROM CODEFIX_HISTORY FETCH FIRST 1 ROWS ONLY"
        try:
            stmt = ibm_db.exec_immediate(conn, check_sql)
            if stmt:
                ibm_db.free_result(stmt)
                _close_conn(conn)
                return True, "Table CODEFIX_HISTORY already exists."
        except Exception:
            # Table does not exist; proceed to create
            pass

        # Execute table creation
        ibm_db.exec_immediate(conn, create_table_sql)
        logger.info("Created table CODEFIX_HISTORY in IBM Db2.")

        # Execute index creation
        try:
            ibm_db.exec_immediate(conn, create_index_sql)
            logger.info("Created index IDX_CODEFIX_SESSION.")
        except Exception as idx_err:
            logger.warning(f"Index creation note: {idx_err}")

        _close_conn(conn)
        return True, "IBM Db2 schema successfully initialized."
    except Exception as e:
        logger.error(f"Error initializing Db2 schema: {e}", exc_info=True)
        try:
            _close_conn(conn)
        except Exception:
            pass
        return False, f"Schema initialization failed: {str(e)}"


def save_history_record(record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Save an AI interaction record into IBM Db2 using parameterized SQL.
    Returns: (success, error_message)
    """
    if not Config.is_db2_configured():
        return False, "IBM Db2 is not configured in .env. Record not persisted to database."

    conn = get_connection()
    if not conn:
        return False, "Unable to connect to IBM Db2 to save record."

    sql = """
    INSERT INTO CODEFIX_HISTORY (
        ID, SESSION_ID, LANGUAGE, MODE, USER_PROMPT,
        ORIGINAL_CODE, ERROR_MESSAGE, GENERATED_CODE, EXPLANATION, MODEL_NAME
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = (
        str(record.get("id", "")),
        str(record.get("session_id", "default")),
        str(record.get("language", "python")),
        str(record.get("mode", "write")),
        str(record.get("user_prompt", "")),
        str(record.get("original_code", "")),
        str(record.get("error_message", "")),
        str(record.get("generated_code", "")),
        str(record.get("explanation", "")),
        str(record.get("model_name", Config.OLLAMA_MODEL))
    )

    try:
        stmt = ibm_db.prepare(conn, sql)
        if not stmt:
            _close_conn(conn)
            return False, "Failed to prepare parameterized SQL statement."

        success = ibm_db.execute(stmt, params)
        _close_conn(conn)

        if success:
            logger.info(f"Saved record {record.get('id')} to IBM Db2 successfully.")
            return True, None
        else:
            return False, "IBM Db2 statement execution failed."
    except Exception as e:
        logger.error(f"Failed to insert record into Db2: {e}", exc_info=True)
        try:
            _close_conn(conn)
        except Exception:
            pass
        return False, f"Database insert failed: {str(e)}"


def get_history_records(
    session_id: Optional[str] = None,
    mode: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Retrieve historical requests and solutions from IBM Db2 using parameterized queries.
    Returns a list of dictionary records.
    """
    if not Config.is_db2_configured():
        return []

    conn = get_connection()
    if not conn:
        return []

    query = """
    SELECT ID, SESSION_ID, LANGUAGE, MODE, USER_PROMPT,
           ORIGINAL_CODE, ERROR_MESSAGE, GENERATED_CODE, EXPLANATION,
           MODEL_NAME, VARCHAR_FORMAT(CREATED_AT, 'YYYY-MM-DD HH24:MI:SS') AS CREATED_AT
    FROM CODEFIX_HISTORY
    WHERE 1=1
    """
    params = []

    if session_id:
        query += " AND SESSION_ID = ?"
        params.append(str(session_id))
    if mode and mode != "all":
        query += " AND MODE = ?"
        params.append(str(mode))
    if language and language != "all":
        query += " AND LANGUAGE = ?"
        params.append(str(language))

    query += " ORDER BY CREATED_AT DESC"
    query += f" FETCH FIRST {int(limit)} ROWS ONLY"

    records = []
    try:
        stmt = ibm_db.prepare(conn, query)
        if stmt:
            ibm_db.execute(stmt, tuple(params))
            row = ibm_db.fetch_assoc(stmt)
            while row:
                # Convert keys to lowercase for template consistency
                formatted_row = {
                    "id": row.get("ID", ""),
                    "session_id": row.get("SESSION_ID", ""),
                    "language": row.get("LANGUAGE", ""),
                    "mode": row.get("MODE", ""),
                    "user_prompt": row.get("USER_PROMPT", ""),
                    "original_code": row.get("ORIGINAL_CODE", ""),
                    "error_message": row.get("ERROR_MESSAGE", ""),
                    "generated_code": row.get("GENERATED_CODE", ""),
                    "explanation": row.get("EXPLANATION", ""),
                    "model_name": row.get("MODEL_NAME", ""),
                    "created_at": row.get("CREATED_AT", "")
                }
                records.append(formatted_row)
                row = ibm_db.fetch_assoc(stmt)
            ibm_db.free_result(stmt)
        _close_conn(conn)
    except Exception as e:
        logger.error(f"Failed to query history from IBM Db2: {e}", exc_info=True)
        try:
            _close_conn(conn)
        except Exception:
            pass

    return records


def get_record_by_id(record_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a single record by its ID using parameterized SQL.
    """
    if not Config.is_db2_configured():
        return None

    conn = get_connection()
    if not conn:
        return None

    query = """
    SELECT ID, SESSION_ID, LANGUAGE, MODE, USER_PROMPT,
           ORIGINAL_CODE, ERROR_MESSAGE, GENERATED_CODE, EXPLANATION,
           MODEL_NAME, VARCHAR_FORMAT(CREATED_AT, 'YYYY-MM-DD HH24:MI:SS') AS CREATED_AT
    FROM CODEFIX_HISTORY
    WHERE ID = ?
    """

    try:
        stmt = ibm_db.prepare(conn, query)
        if stmt:
            ibm_db.execute(stmt, (str(record_id),))
            row = ibm_db.fetch_assoc(stmt)
            if row:
                result = {
                    "id": row.get("ID", ""),
                    "session_id": row.get("SESSION_ID", ""),
                    "language": row.get("LANGUAGE", ""),
                    "mode": row.get("MODE", ""),
                    "user_prompt": row.get("USER_PROMPT", ""),
                    "original_code": row.get("ORIGINAL_CODE", ""),
                    "error_message": row.get("ERROR_MESSAGE", ""),
                    "generated_code": row.get("GENERATED_CODE", ""),
                    "explanation": row.get("EXPLANATION", ""),
                    "model_name": row.get("MODEL_NAME", ""),
                    "created_at": row.get("CREATED_AT", "")
                }
                ibm_db.free_result(stmt)
                _close_conn(conn)
                return result
        _close_conn(conn)
    except Exception as e:
        logger.error(f"Failed to get record {record_id} from IBM Db2: {e}", exc_info=True)
        try:
            _close_conn(conn)
        except Exception:
            pass

    return None


def delete_record_by_id(record_id: str) -> bool:
    """
    Delete a single record from IBM Db2 by its ID using parameterized SQL.
    """
    if not Config.is_db2_configured():
        return False

    conn = get_connection()
    if not conn:
        return False

    sql = "DELETE FROM CODEFIX_HISTORY WHERE ID = ?"

    try:
        stmt = ibm_db.prepare(conn, sql)
        if stmt:
            success = ibm_db.execute(stmt, (str(record_id),))
            _close_conn(conn)
            return bool(success)
        _close_conn(conn)
        return False
    except Exception as e:
        logger.error(f"Failed to delete record {record_id} from IBM Db2: {e}", exc_info=True)
        try:
            _close_conn(conn)
        except Exception:
            pass
        return False

