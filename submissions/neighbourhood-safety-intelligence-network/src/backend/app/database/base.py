import logging
from typing import Generator, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.app.core.config import settings
from backend.app.models.entities import Base

logger = logging.getLogger("neighbourhood_safety.database")

engine = None
SessionLocal = None

def get_db_status() -> dict:
    mode = settings.DATABASE_MODE.lower()
    status = {
        "mode": mode,
        "connected": False,
        "driver": None,
        "details": {}
    }

    if mode == "sqlite":
        status["connected"] = engine is not None
        status["driver"] = "sqlite3 / sqlalchemy"
        status["details"] = {"url": settings.DATABASE_URL}
    elif mode == "postgresql":
        status["connected"] = engine is not None
        status["driver"] = "psycopg2 / sqlalchemy"
        status["details"] = {"server": settings.POSTGRES_SERVER, "db": settings.POSTGRES_DB}
    elif mode == "db2":
        from backend.app.database.db2_adapter import Db2Adapter
        db2 = Db2Adapter()
        check = db2.test_connection()
        status["connected"] = check.get("connected", False)
        status["driver"] = "ibm_db"
        status["details"] = check
        from backend.app.ai.semantic.db2_vector_store import vector_store
        status["vector_search"] = vector_store.status()
    return status

def init_db():
    global engine, SessionLocal
    mode = settings.DATABASE_MODE.lower()
    logger.info(f"Initializing database layer in [{mode.upper()}] mode")

    if mode == "sqlite":
        from backend.app.database.sqlite_adapter import init_sqlite
        engine, SessionLocal = init_sqlite()
    elif mode == "postgresql":
        from backend.app.database.postgres_adapter import init_postgres
        engine, SessionLocal = init_postgres()
    elif mode == "db2":
        from backend.app.database.db2_adapter import Db2Adapter
        db2 = Db2Adapter()
        # Strictly verify IBM Db2 connection as required
        verified = db2.test_connection()
        if not verified.get("connected"):
            error_msg = f"IBM Db2 connection failed: {verified.get('error')}. Strict Db2 mode will NOT silently fallback to SQLite."
            logger.error(error_msg)
            raise ConnectionError(error_msg)
        engine, SessionLocal = db2.get_session_factory()
        from backend.app.ai.semantic.db2_vector_store import vector_store
        vector_store.initialise(engine)
    else:
        raise ValueError(f"Unsupported DATABASE_MODE: '{mode}'. Supported: sqlite, postgresql, db2")

def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
