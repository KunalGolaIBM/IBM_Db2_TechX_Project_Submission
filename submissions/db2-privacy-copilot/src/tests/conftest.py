"""
Pytest configuration and shared fixtures.
"""
import pytest

from app.db import MOCK_MODE, conn


def pytest_collection_modifyitems(items):
    """Skip live-Db2 tests when the in-memory demo backend is active."""
    if MOCK_MODE:
        skip_db2 = pytest.mark.skip(reason="requires a live IBM Db2 database")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_db2)


@pytest.fixture
def db_conn():
    """Provide a database connection for tests."""
    c = conn()
    yield c
    c.close()


@pytest.fixture
def classified_erasure_columns(db_conn):
    """Provide deterministic PII metadata for erasure integration tests."""
    cur = db_conn.cursor()
    merge_sql = """
        MERGE INTO PII_MAP AS target
        USING (VALUES (?, ?, ?, ?, ?)) AS source
            (TABNAME, COLNAME, LABEL, CONFIDENCE, METHOD)
        ON target.TABNAME = source.TABNAME AND target.COLNAME = source.COLNAME
        WHEN MATCHED THEN
            UPDATE SET LABEL = source.LABEL,
                       CONFIDENCE = source.CONFIDENCE,
                       METHOD = source.METHOD
        WHEN NOT MATCHED THEN
            INSERT (TABNAME, COLNAME, LABEL, CONFIDENCE, METHOD)
            VALUES (source.TABNAME, source.COLNAME, source.LABEL,
                    source.CONFIDENCE, source.METHOD)
    """
    classifications = (
        ("PATIENT", "FULL_NM", "NAME"),
        ("PATIENT", "CUST_MAIL_ID", "EMAIL"),
        ("PATIENT", "PH_NO", "PHONE"),
        ("PATIENT", "GOVT_ID", "GOVT_ID"),
        ("APPOINTMENT", "DOCTOR_NM", "NAME"),
        ("APPOINTMENT", "REASON", "HEALTH"),
    )
    previous = {}
    for table, column, label in classifications:
        cur.execute(
            "SELECT LABEL, CONFIDENCE, METHOD FROM PII_MAP "
            "WHERE TABNAME = ? AND COLNAME = ?",
            (table, column),
        )
        previous[(table, column)] = cur.fetchone()
        cur.execute(merge_sql, (table, column, label, 1.0, "TEST"))
    db_conn.commit()

    yield

    for table, column, _ in classifications:
        old_values = previous[(table, column)]
        if old_values:
            label, confidence, method = old_values
            cur.execute(
                merge_sql,
                (table, column, label, float(confidence), method),
            )
        else:
            cur.execute(
                "DELETE FROM PII_MAP WHERE TABNAME = ? AND COLNAME = ?",
                (table, column),
            )
    db_conn.commit()


@pytest.fixture
def sample_patient_id(db_conn):
    """Create a test patient and return the ID."""
    cur = db_conn.cursor()
    cur.execute("""
        INSERT INTO PATIENT (FULL_NM, CUST_MAIL_ID, PH_NO, DOB_DT, GOVT_ID, ADDR1, CITY_NM, PINCODE)
        VALUES ('Test Patient', 'test@example.com', 9876543210, '1990-01-01', 'TESTPAN123', 
                'Test Address', 'Test City', '123456')
    """)
    db_conn.commit()
    
    cur.execute("SELECT ID FROM PATIENT WHERE CUST_MAIL_ID = 'test@example.com'")
    patient_id = int(cur.fetchone()[0])
    
    yield patient_id
    
    # Cleanup
    cur.execute("DELETE FROM PATIENT WHERE ID = ?", (patient_id,))
    db_conn.commit()
