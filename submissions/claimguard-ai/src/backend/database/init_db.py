"""
ClaimGuard AI - Database Initialization Script
Executes schema.sql against IBM Db2 to create all tables, indexes, and initial seeds.
"""

import sys
import logging
from pathlib import Path

# Ensure backend root is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.config import settings
from backend.database.connection import db2_manager, IBM_DB_AVAILABLE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("claimguard.init_db")


def initialize_db2_database():
    """Reads schema.sql and runs statements on IBM Db2."""
    if not IBM_DB_AVAILABLE:
        logger.error("ibm_db driver is not installed. Run 'pip install ibm_db'.")
        return False

    conn = db2_manager.get_connection()
    if not conn:
        logger.error("Could not connect to IBM Db2 at %s:%s", settings.DB2_HOST, settings.DB2_PORT)
        logger.error("Error details: %s", db2_manager._last_error)
        logger.info(
            "\nEnsure your local Db2 container is running:\n"
            "docker run -d --name db2server -p 50000:50000 --env-file .env.db2 icr.io/db2_community/db2:latest\n"
        )
        return False

    schema_file = Path(__file__).resolve().parent / "schema.sql"
    if not schema_file.is_file():
        logger.error("Schema file not found at %s", schema_file)
        return False

    logger.info("Reading schema DDL from %s...", schema_file)
    with open(schema_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Split statements by semicolon
    statements = [stmt.strip() for stmt in sql_content.split(";") if stmt.strip()]

    success_count = 0
    import ibm_db

    for stmt in statements:
        # Ignore comments
        cleaned = "\n".join(line for line in stmt.splitlines() if not line.strip().startswith("--")).strip()
        if not cleaned:
            continue

        try:
            ibm_db.exec_immediate(conn, cleaned)
            success_count += 1
            first_line = cleaned.splitlines()[0][:60]
            logger.info("Executed: %s...", first_line)
        except Exception as e:
            err_msg = ""
            try:
                err_msg = ibm_db.stmt_errormsg()
            except Exception:
                pass
            # If table/index already exists (SQL0601N), report as warning
            if "SQL0601N" in err_msg or "already exists" in str(e).lower():
                logger.warning("Object already exists: %s", err_msg.strip())
            else:
                logger.warning("Statement warning/error: %s | %s", e, err_msg.strip())

    logger.info("Database initialization completed (%d statements processed)!", success_count)
    return True


if __name__ == "__main__":
    success = initialize_db2_database()
    sys.exit(0 if success else 1)
