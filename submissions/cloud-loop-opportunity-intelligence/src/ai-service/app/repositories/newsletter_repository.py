import logging
from datetime import datetime, timezone
from app.database.session import db_session
from app.database.db2_connection import db2_manager

logger = logging.getLogger("cloud_loop.repository.newsletter")

class NewsletterRepository:
    def subscribe(self, email: str) -> bool:
        clean_email = email.strip().lower()
        status_info = db2_manager.status

        if status_info["driver_available"] and status_info["configured"]:
            # Db2 MERGE duplicate handling
            sql_merge = """
                MERGE INTO CLOUDLOOP.NEWSLETTER_SUBSCRIBERS AS target
                USING (VALUES (?)) AS source (EMAIL)
                ON (target.EMAIL = source.EMAIL)
                WHEN NOT MATCHED THEN
                  INSERT (EMAIL, CREATED_AT) VALUES (source.EMAIL, CURRENT TIMESTAMP)
            """
            try:
                db_session.execute(sql_merge, [clean_email])
                return True
            except Exception as e:
                logger.warning(f"Db2 newsletter MERGE notice: {e}")

        # Local SQLite / fallback
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sql_sqlite = """
            INSERT INTO NEWSLETTER_SUBSCRIBERS (EMAIL, CREATED_AT)
            VALUES (?, ?)
            ON CONFLICT(EMAIL) DO NOTHING
        """
        db_session.execute(sql_sqlite, [clean_email, now])
        return True

newsletter_repo = NewsletterRepository()
