
"""Run the Db2 DDL defined in database/schema.sql.

Features:
- Loads DB2 configuration through db.py.
- Executes schema statements individually.
- Skips existing DB2 objects.
- Verifies all expected tables.
"""

from pathlib import Path

from .db import execute_dml, execute_query


# backend/database/schema.sql
SCHEMA_FILE = (
    Path(__file__).resolve().parents[3]
    / "database"
    / "schema.sql"
)

EXPECTED_TABLES = [
    "PRODUCTS",
    "SHIPMENTS",
    "SENSOR_READINGS",
    "INCIDENTS",
    "RISK_ASSESSMENTS",
    "RECOMMENDATIONS",
    "KNOWLEDGE_DOCUMENTS",
    "AUDIT_LOGS",
]


def is_existing_object_error(exc):
    """Identify DB2 errors indicating an object already exists."""
    error = str(exc).lower()

    return (
        "sqlstate=42710" in error
        or "sqlcode=-601" in error
        or "already exists" in error
    )


def run_schema():
    """Read and execute the DB2 schema."""

    if not SCHEMA_FILE.is_file():
        raise FileNotFoundError(
            f"Schema file not found: {SCHEMA_FILE}"
        )

    print("=" * 55)
    print(" ColdChain Guardian - DB2 Schema Setup")
    print("=" * 55)

    sql = SCHEMA_FILE.read_text(encoding="utf-8")

    # Remove full-line SQL comments before splitting.
    cleaned_lines = []

    for line in sql.splitlines():
        if line.strip().startswith("--"):
            continue
        cleaned_lines.append(line)

    cleaned_sql = "\n".join(cleaned_lines)

    # Split statements using semicolons.
    statements = [
        stmt.strip()
        for stmt in cleaned_sql.split(";")
        if stmt.strip()
    ]

    created = 0
    skipped = 0

    for index, stmt in enumerate(statements, start=1):

        try:
            execute_dml(stmt)
            created += 1

            first_line = stmt.splitlines()[0][:70]

            print(f"[CREATED] {first_line}")

        except Exception as exc:

            if is_existing_object_error(exc):
                skipped += 1

                first_line = stmt.splitlines()[0][:70]

                print(f"[SKIPPED] {first_line} (already exists)")
                continue

            print(f"\n[FAILED] Statement {index}")
            print(stmt)
            raise

    print("\nSchema execution summary:")
    print(f"Created statements : {created}")
    print(f"Skipped statements : {skipped}")

    print("\n[OK] Schema execution completed.")


def verify_tables():
    """Verify that all expected tables exist."""

    print("\nVerifying database tables...")

    rows = execute_query(
        """
        SELECT TABNAME
        FROM SYSCAT.TABLES
        WHERE TABSCHEMA = CURRENT SCHEMA
          AND TYPE = 'T'
        """
    )

    existing = {
        row["tabname"].upper()
        for row in rows
    }

    missing = [
        table
        for table in EXPECTED_TABLES
        if table not in existing
    ]

    if missing:
        print("\n[FAILED] Missing tables:")

        for table in missing:
            print(f"  - {table}")

        raise RuntimeError(
            f"Missing expected tables: {missing}"
        )

    print("\n[SUCCESS] All expected tables are present!")

    for table in EXPECTED_TABLES:
        print(f"  [OK] {table}")

    return True


def main():
    run_schema()
    verify_tables()

    print("\n" + "=" * 55)
    print(" COLDCHAIN GUARDIAN DATABASE READY")
    print("=" * 55)


if __name__ == "__main__":
    main()
