"""CLI Database Initializer for IBM Db2 / local mock."""
from app.db.connection import db_manager
from app.db.repository import Db2IncidentRepository
from app.models.incident import Incident, IncidentSeverity, IncidentStatus

def main():
    print(f"Initializing database... Mode: {db_manager.active_mode}")
    repo = Db2IncidentRepository(db_manager)
    if db_manager.is_db2_active:
        print("Executing native IBM Db2 schema (schema_db2.sql)...")
        repo.init_schema_db2()
    else:
        print("Executing SQLite mock schema (schema_sqlite)...")
        repo.init_schema_sqlite()

    # Seed sample baseline incident if empty
    items, total = repo.list(limit=1)
    if total == 0:
        seed = Incident(
            id="INC-BASELINE-01",
            title="Baseline Health Check Event",
            description="Automated synthetic verification incident on IBM Db2 storage engine.",
            service="db2-workrelay-core",
            severity=IncidentSeverity.LOW,
            status=IncidentStatus.RESOLVED,
            resolution="Database schema verified and operational.",
        )
        repo.create(seed)
        print("Database initialized and baseline incident created.")
    else:
        print(f"Database already contains {total} incidents.")

if __name__ == "__main__":
    main()
