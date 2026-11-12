"""IBM Db2 is the application's only database: engine, sessions, startup and health status."""
import logging
from typing import Generator

from sqlalchemy.orm import Session

from backend.app.core.config import settings

logger = logging.getLogger("neighbourhood_safety.database")

engine = None
SessionLocal = None


def get_db_status() -> dict:
    from backend.app.ai.haystack.rag_pipeline import protocol_retriever
    from backend.app.ai.semantic.db2_vector_store import vector_store
    from backend.app.database.db2_adapter import Db2Adapter

    check = Db2Adapter().test_connection()
    return {
        "mode": "db2",
        "connected": check.get("connected", False),
        "driver": "ibm_db",
        "details": check,
        "vector_search": vector_store.status(),
        "hybrid_retrieval": protocol_retriever.status(),
    }


def init_db() -> None:
    """Connect to Db2 (fail fast if unreachable), create missing tables, seed demo data, then
    enable vector search and the hybrid retrieval pipeline."""
    global engine, SessionLocal
    from backend.app.ai.haystack.rag_pipeline import protocol_retriever
    from backend.app.ai.semantic.db2_vector_store import vector_store
    from backend.app.database.db2_adapter import Db2Adapter

    logger.info("Connecting to IBM Db2 %s at %s:%s", settings.DB2_DATABASE, settings.DB2_HOST, settings.DB2_PORT)
    db2 = Db2Adapter()
    verified = db2.test_connection()
    if not verified.get("connected"):
        raise ConnectionError(f"IBM Db2 connection failed: {verified.get('error')}")
    engine, SessionLocal = db2.get_session_factory()
    vector_store.initialise(engine)
    protocol_retriever.enable_db2()


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
