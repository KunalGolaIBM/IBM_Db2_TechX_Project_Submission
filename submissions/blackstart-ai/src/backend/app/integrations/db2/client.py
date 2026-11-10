import ibm_db
from app.core.config import get_settings


def connect_db2():
    settings = get_settings()

    if not settings.db2_dsn:
        raise RuntimeError("Db2 DSN is not configured.")

    return ibm_db.connect(settings.db2_dsn, "", "")


def test_db2_connection() -> dict:
    connection = None

    try:
        connection = connect_db2()
        return {"connected": True, "message": "IBM Db2 connection successful."}
    except Exception as exc:
        return {"connected": False, "message": str(exc)}
    finally:
        if connection:
            ibm_db.close(connection)
