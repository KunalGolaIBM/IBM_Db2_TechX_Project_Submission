"""Database Initialization Script for IBM Db2.

Executes schema DDL to create tables, constraints, and indexes.
"""
import sys
import os
from pathlib import Path

# Add src to python path
current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent / "src"
sys.path.insert(0, str(src_dir))

from recipe_waste_optimizer.db.connection import db_manager, HAVE_IBM_DB


def init_database(drop_existing: bool = False):
    """Read schema.sql and execute against target IBM Db2 database."""
    print("Connecting to IBM Db2...")
    if not HAVE_IBM_DB:
        print("ERROR: ibm_db driver not loaded. Please install dependencies.")
        sys.exit(1)

    schema_file = src_dir / "recipe_waste_optimizer" / "db" / "schema.sql"
    if not schema_file.is_file():
        print(f"ERROR: Schema file not found at {schema_file}")
        sys.exit(1)

    with open(schema_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Split into individual SQL statements by semicolon
    raw_statements = sql_content.split(";")

    tables_order = [
        "INVENTORY_EVENTS",
        "COOKING_HISTORY",
        "RECIPE_EMBEDDINGS",
        "RECIPE_INGREDIENTS",
        "RECIPES",
        "USER_INVENTORY",
        "INGREDIENTS"
    ]

    with db_manager.cursor() as cur:
        if drop_existing:
            print("Dropping existing tables if present...")
            for tbl in tables_order:
                try:
                    cur.execute(f"DROP TABLE {tbl}")
                    print(f"  Dropped table: {tbl}")
                except Exception:
                    pass

        print("Executing DDL statements...")
        executed_count = 0
        for stmt in raw_statements:
            cleaned = stmt.strip()
            # Skip empty or pure comment blocks
            lines = [l for l in cleaned.splitlines() if not l.strip().startswith("--")]
            sql = "\n".join(lines).strip()
            if not sql:
                continue

            try:
                cur.execute(sql)
                executed_count += 1
            except Exception as e:
                # If table already exists and not dropping, continue
                err = str(e).lower()
                if "already exists" in err or "name is already used" in err or "-601" in err:
                    print(f"  Note: Object already exists (skipped)")
                else:
                    print(f"  Warning on statement: {e}")

    print(f"Database initialization complete! Executed {executed_count} statements.")


if __name__ == "__main__":
    drop_flag = "--drop" in sys.argv
    init_database(drop_existing=drop_flag)
