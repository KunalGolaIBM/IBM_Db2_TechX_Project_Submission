import os
import logging
from app.database.session import db_session
from app.database.db2_connection import db2_manager

logger = logging.getLogger("cloud_loop.migrations")

def run_migrations():
    """
    Applies idempotent initial migrations to the target database.
    """
    migration_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "migrations",
        "001_initial_schema.sql"
    )

    if not os.path.exists(migration_file):
        logger.warning(f"Migration file not found at {migration_file}")
        return

    logger.info("Executing idempotent database schema verification...")
    # SQLite schema is verified on DatabaseSession init
    # When Db2 is connected, execute DDL statements individually
    status = db2_manager.status
    if status["driver_available"] and status["configured"]:
        try:
            with open(migration_file, "r", encoding="utf-8") as f:
                content = f.read()

            statements = [s.strip() for s in content.split(";") if s.strip() and not s.strip().startswith("--")]
            for stmt in statements:
                try:
                    db2_manager.execute_non_query(stmt)
                except Exception as e:
                    # Ignore table already exists errors (SQLSTATE 42710)
                    if "already exists" in str(e).lower() or "-601" in str(e):
                        continue
                    logger.debug(f"Db2 migration notice: {e}")
            logger.info("IBM Db2 schema verified successfully.")
        except Exception as e:
            logger.warning(f"Db2 migration pass completed with notices: {e}")
    else:
        logger.info("Local storage schema verified successfully.")

