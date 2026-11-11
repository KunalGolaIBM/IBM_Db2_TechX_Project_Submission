"""
CivicConnect – IBM Db2 Schema Setup & Connection Utilities
Sets up the full relational schema for complaint lifecycle management,
department routing, audit trails, and citizen feedback analytics.
"""

import os
import ibm_db
import ibm_db_dbi

# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def get_connection_string() -> str:
    """Build IBM Db2 connection string from environment variables."""
    return (
        f"DATABASE={os.environ['DB2_DATABASE']};"
        f"HOSTNAME={os.environ['DB2_HOST']};"
        f"PORT={os.environ.get('DB2_PORT', '50000')};"
        f"PROTOCOL=TCPIP;"
        f"UID={os.environ['DB2_USER']};"
        f"PWD={os.environ['DB2_PASSWORD']};"
        f"SECURITY={os.environ.get('DB2_SECURITY', 'SSL')};"
    )


def get_ibm_db_connection():
    """Return a low-level ibm_db connection handle."""
    return ibm_db.connect(get_connection_string(), "", "")


def get_dbi_connection():
    """Return a DB-API 2.0 compatible connection (for pandas / SQLAlchemy use)."""
    return ibm_db_dbi.connect(get_connection_string(), "", "")


# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

CREATE_DEPARTMENTS = """
CREATE TABLE IF NOT EXISTS CIVICCONNECT.DEPARTMENTS (
    DEPARTMENT_ID    VARCHAR(64)   NOT NULL,
    NAME             VARCHAR(100)  NOT NULL,
    DESCRIPTION      VARCHAR(500),
    ACTIVE           SMALLINT      NOT NULL DEFAULT 1,
    CREATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (DEPARTMENT_ID)
)
"""

CREATE_COMPLAINTS = """
CREATE TABLE IF NOT EXISTS CIVICCONNECT.COMPLAINTS (
    ID               VARCHAR(128)  NOT NULL,
    COMPLAINT_ID     VARCHAR(64)   NOT NULL,
    USER_ID          VARCHAR(128)  NOT NULL,
    CITIZEN_NAME     VARCHAR(100),
    CITIZEN_EMAIL    VARCHAR(150),
    TITLE            VARCHAR(200)  NOT NULL,
    DESCRIPTION      CLOB(32K),
    CATEGORY         VARCHAR(100),
    DEPARTMENT_ID    VARCHAR(64),
    DEPARTMENT_NAME  VARCHAR(100),
    LOCATION         VARCHAR(255)  NOT NULL,
    LANDMARK         VARCHAR(255),
    IMAGE_URL        VARCHAR(1000),
    PRIORITY         VARCHAR(20)   NOT NULL DEFAULT 'medium',
    STATUS           VARCHAR(50)   NOT NULL DEFAULT 'Submitted',
    AI_SUMMARY       CLOB(8K),
    AI_KEYWORDS      VARCHAR(500),
    REJECTION_REASON VARCHAR(1000),
    REOPEN_REASON    VARCHAR(1000),
    RESOLUTION_NOTES CLOB(8K),
    CREATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    RESOLVED_AT      TIMESTAMP,
    PRIMARY KEY (ID),
    UNIQUE (COMPLAINT_ID)
)
"""

CREATE_COMPLAINT_UPDATES = """
CREATE TABLE IF NOT EXISTS CIVICCONNECT.COMPLAINT_UPDATES (
    ID               VARCHAR(128)  NOT NULL,
    COMPLAINT_ID     VARCHAR(64)   NOT NULL,
    PREVIOUS_STATUS  VARCHAR(50),
    NEW_STATUS       VARCHAR(50)   NOT NULL,
    UPDATED_BY       VARCHAR(100),
    UPDATED_BY_UID   VARCHAR(128),
    ROLE             VARCHAR(50),
    NOTE             CLOB(4K),
    CREATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ID)
)
"""

CREATE_NOTIFICATIONS = """
CREATE TABLE IF NOT EXISTS CIVICCONNECT.NOTIFICATIONS (
    ID               VARCHAR(128)  NOT NULL,
    USER_ID          VARCHAR(128)  NOT NULL,
    TITLE            VARCHAR(150),
    MESSAGE          VARCHAR(1000),
    COMPLAINT_ID     VARCHAR(64),
    IS_READ          SMALLINT      NOT NULL DEFAULT 0,
    CREATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ID)
)
"""

CREATE_FEEDBACK = """
CREATE TABLE IF NOT EXISTS CIVICCONNECT.CITIZEN_FEEDBACK (
    ID               VARCHAR(128)  NOT NULL,
    COMPLAINT_ID     VARCHAR(64)   NOT NULL,
    USER_ID          VARCHAR(128)  NOT NULL,
    RATING           SMALLINT      NOT NULL,
    COMMENT          VARCHAR(1000),
    CREATED_AT       TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ID)
)
"""

CREATE_COMPLAINT_ANALYTICS = """
CREATE TABLE IF NOT EXISTS CIVICCONNECT.COMPLAINT_ANALYTICS (
    SNAPSHOT_DATE     DATE          NOT NULL,
    CATEGORY          VARCHAR(100)  NOT NULL,
    DEPARTMENT_NAME   VARCHAR(100),
    TOTAL_COMPLAINTS  INT           NOT NULL DEFAULT 0,
    RESOLVED_COUNT    INT           NOT NULL DEFAULT 0,
    PENDING_COUNT     INT           NOT NULL DEFAULT 0,
    AVG_RESOLUTION_HRS DECIMAL(10,2),
    PRIMARY KEY (SNAPSHOT_DATE, CATEGORY)
)
"""

ALL_DDL_STATEMENTS = [
    CREATE_DEPARTMENTS,
    CREATE_COMPLAINTS,
    CREATE_COMPLAINT_UPDATES,
    CREATE_NOTIFICATIONS,
    CREATE_FEEDBACK,
    CREATE_COMPLAINT_ANALYTICS,
]


def setup_schema():
    """Create all CivicConnect tables in IBM Db2. Idempotent."""
    conn = get_ibm_db_connection()
    try:
        # Ensure schema exists
        try:
            stmt = ibm_db.exec_immediate(conn, "CREATE SCHEMA CIVICCONNECT")
        except Exception:
            pass  # Schema already exists

        for ddl in ALL_DDL_STATEMENTS:
            try:
                ibm_db.exec_immediate(conn, ddl)
                print(f"[Db2 Setup] Table created/verified OK.")
            except Exception as e:
                if "already exists" in str(e).lower() or "-601" in str(e):
                    pass  # Table already present; skip silently
                else:
                    raise

        print("[Db2 Setup] Schema setup complete — all CivicConnect tables ready.")
    finally:
        ibm_db.close(conn)


if __name__ == "__main__":
    setup_schema()
