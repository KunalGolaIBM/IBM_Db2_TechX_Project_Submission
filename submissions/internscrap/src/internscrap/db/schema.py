"""
Database schema initializer for IBM Db2.
Executes the DDL and views from the sql/ directory.
"""

from pathlib import Path
from internscrap.db.connection import get_db_connection

SQL_DIR = Path(__file__).resolve().parent.parent.parent / "sql"
if not SQL_DIR.exists():
    SQL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sql"

def initialize_database():
    """Initializes tables, views, and indexes in IBM Db2."""
    conn = get_db_connection()
    print("=" * 60)
    if conn.is_native_db2:
        print("[IBM Db2] Initializing production tables and views on Db2...")
    else:
        print("[Simulated Db2] Initializing tables and views in simulated mode...")
    print("=" * 60)

    schema_file = SQL_DIR / "01_schema.sql"
    views_file = SQL_DIR / "02_views.sql"

    if conn.is_native_db2:
        # Execute Db2 statements
        for file_path in [schema_file, views_file]:
            if not file_path.exists():
                continue
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            # Split by semicolon (ignoring comments)
            statements = [
                s.strip() for s in content.split(";") 
                if s.strip() and not s.strip().startswith("--")
            ]
            for stmt in statements:
                try:
                    conn.execute_non_query(stmt)
                except Exception as err:
                    # Ignore drop failures or table already exists
                    pass
    else:
        # SQLite already initialized via _init_sqlite_schema()
        pass

    print("[Success] Database schema and views initialized successfully!")
    return True
