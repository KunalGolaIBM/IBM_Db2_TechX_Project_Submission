import logging
import time
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, DatabaseError

from config import settings
from models import Base

logger = logging.getLogger("uvicorn.error")

# Determine connection string - exclusively IBM Db2
db_uri = settings.sqlalchemy_database_uri

if not db_uri.startswith("db2"):
    raise RuntimeError(
        f"Invalid database URI: '{db_uri}'. "
        "This application is strictly built for IBM Db2 and requires a db2+ibm_db connection URI."
    )

try:
    from sqlalchemy.dialects import registry
    registry.load("db2.ibm_db")
except Exception as e:
    raise RuntimeError(
        f"IBM Db2 SQLAlchemy driver (ibm_db_sa / ibm_db) failed to load: {e}. "
        "The application requires the IBM Db2 driver. Please run inside the Docker container "
        "or ensure ibm_db and ibm_db_sa with IBM DB2 clidriver are installed."
    )

engine = create_engine(
    db_uri,
    echo=settings.DEBUG,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.
    Ensures sessions are closed properly.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def wait_for_database(max_retries: int = 40, delay: float = 3.0) -> bool:
    """
    Waits for IBM Db2 container to become fully responsive.
    Db2 requires 45-75 seconds to initialize instance and database on cold boot.
    Fails with a clear error if connection cannot be established.
    """
    logger.info(f"Connecting to IBM Db2 at {settings.DB2_HOST}:{settings.DB2_PORT}/{settings.DB2_DATABASE}...")
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM SYSIBM.SYSDUMMY1"))
                logger.info("Successfully connected to IBM Db2 database!")
                return True
        except (OperationalError, DatabaseError, Exception) as err:
            logger.warning(f"IBM Db2 not ready yet (attempt {attempt}/{max_retries}): {err}")
            time.sleep(delay)
    
    error_msg = (
        f"FATAL: Failed to connect to IBM Db2 database at {settings.DB2_HOST}:{settings.DB2_PORT}/{settings.DB2_DATABASE} "
        f"after {max_retries} retries. Ensure the IBM Db2 container is running, healthy, and accessible."
    )
    logger.error(error_msg)
    raise RuntimeError(error_msg)


def init_db():
    """
    Creates tables in IBM Db2 if they don't already exist,
    and runs clean schema migrations to ensure new AI columns exist.
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("IBM Db2 database tables verified/created successfully.")

        # Ensure new columns exist on grievances table via Db2 catalog inspection
        with engine.connect() as conn:
            cols_result = conn.execute(
                text("SELECT COLNAME FROM SYSCAT.COLUMNS WHERE UPPER(TABNAME) = 'GRIEVANCES'")
            ).fetchall()
            existing_cols = {row[0].strip().upper() for row in cols_result}

            table_altered = False
            if "AI_CATEGORY" not in existing_cols:
                logger.info("Migrating IBM Db2: Adding ai_category column to grievances...")
                conn.execute(text("ALTER TABLE grievances ADD COLUMN ai_category VARCHAR(50)"))
                table_altered = True

            if "AI_PRIORITY" not in existing_cols:
                logger.info("Migrating IBM Db2: Adding ai_priority column to grievances...")
                conn.execute(text("ALTER TABLE grievances ADD COLUMN ai_priority VARCHAR(20)"))
                table_altered = True

            if "AI_SUMMARY" not in existing_cols:
                logger.info("Migrating IBM Db2: Adding ai_summary column to grievances...")
                conn.execute(text("ALTER TABLE grievances ADD COLUMN ai_summary VARCHAR(255)"))
                table_altered = True

            if table_altered:
                conn.commit()
                try:
                    conn.execute(text("CALL SYSPROC.ADMIN_CMD('REORG TABLE grievances')"))
                    conn.commit()
                    logger.info("Executed IBM Db2 REORG on grievances table.")
                except Exception as reorg_err:
                    logger.warning(f"Db2 REORG notice (informational): {reorg_err}")

            # Backfill existing grievances where ai_category is NULL
            try:
                conn.execute(text("""
                    UPDATE grievances 
                    SET ai_category = category,
                        ai_priority = priority,
                        ai_summary = SUBSTR(COALESCE(subject, description), 1, 250)
                    WHERE ai_category IS NULL
                """))
                conn.commit()
            except Exception as backfill_err:
                logger.warning(f"Db2 backfill notice: {backfill_err}")

            # Verify and register IBM Db2 Stored Procedure: SP_ESCALATE_OVERDUE
            try:
                proc_row = conn.execute(
                    text("SELECT ROUTINENAME FROM SYSCAT.ROUTINES WHERE UPPER(ROUTINENAME) = 'SP_ESCALATE_OVERDUE'")
                ).fetchone()
                if not proc_row:
                    logger.info("Registering IBM Db2 Stored Procedure: SP_ESCALATE_OVERDUE...")
                    conn.execute(text("""
                        CREATE OR REPLACE PROCEDURE SP_ESCALATE_OVERDUE (OUT escalated_count INT)
                        LANGUAGE SQL
                        BEGIN
                            DECLARE v_count INT DEFAULT 0;
                            SELECT COUNT(*) INTO v_count
                            FROM grievances
                            WHERE status != 'Resolved'
                              AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15;
                            UPDATE grievances
                            SET priority = 'Critical'
                            WHERE status != 'Resolved'
                              AND (DAYS(CURRENT DATE) - DAYS(DATE(created_at))) > 15
                              AND priority != 'Critical';
                            SET escalated_count = v_count;
                        END
                    """))
                    conn.commit()
                    logger.info("Successfully registered SP_ESCALATE_OVERDUE in IBM Db2.")
                else:
                    logger.info("IBM Db2 Stored Procedure SP_ESCALATE_OVERDUE verified.")
            except Exception as proc_err:
                logger.warning(f"IBM Db2 Stored Procedure registration notice: {proc_err}")

            # Verify and register IBM Db2 Kernel Trigger: TRG_AUDIT_STATUS_CHANGE
            try:
                trg_row = conn.execute(
                    text("SELECT TRIGNAME FROM SYSCAT.TRIGGERS WHERE UPPER(TRIGNAME) = 'TRG_AUDIT_STATUS_CHANGE'")
                ).fetchone()
                if not trg_row:
                    logger.info("Registering IBM Db2 Kernel Trigger: TRG_AUDIT_STATUS_CHANGE...")
                    conn.execute(text("""
                        CREATE TRIGGER TRG_AUDIT_STATUS_CHANGE
                        AFTER UPDATE OF status, priority ON grievances
                        REFERENCING OLD AS O NEW AS N
                        FOR EACH ROW
                        WHEN (N.status <> O.status OR N.priority <> O.priority)
                        INSERT INTO grievance_updates (
                            grievance_id, 
                            previous_status, 
                            new_status, 
                            notes, 
                            updated_by, 
                            created_at
                        ) VALUES (
                            N.id, 
                            O.status, 
                            N.status, 
                            CONCAT('Kernel Trigger Audit: Priority changed to ', CONCAT(N.priority, CONCAT(', Status changed to ', N.status))), 
                            'Db2 Engine (TRG_AUDIT_STATUS_CHANGE)', 
                            CURRENT TIMESTAMP
                        )
                    """))
                    conn.commit()
                    logger.info("Successfully registered TRG_AUDIT_STATUS_CHANGE in IBM Db2.")
                else:
                    logger.info("IBM Db2 Kernel Trigger TRG_AUDIT_STATUS_CHANGE verified.")
            except Exception as trg_err:
                logger.warning(f"IBM Db2 Kernel Trigger registration notice: {trg_err}")

    except Exception as e:
        logger.error(f"Error creating/migrating IBM Db2 database tables: {e}")
        raise RuntimeError(f"Failed to initialize schema in IBM Db2: {e}")
