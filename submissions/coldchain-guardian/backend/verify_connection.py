"""Db2 Connection Verification Script."""
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.database.db import test_connection, get_db2_config, execute_query

def main():
    print("==================================================")
    print(" ColdChain Guardian - IBM Db2 Connectivity Check")
    print("==================================================")
    try:
        cfg = get_db2_config()
        print(f"Connecting to: {cfg['user']}@{cfg['host']}:{cfg['port']}/{cfg['database']}")
        res = test_connection()
        print("Status: SUCCESS!")
        print(f"Db2 Server Time: {res.get('server_time')}")
        print(f"Database Name:   {res.get('database_name')}")

        print("\nExecuting live SQL query: SELECT * FROM SYSCAT.DATATYPES WHERE TYPENAME IN ('INTEGER', 'VARCHAR') FETCH FIRST 2 ROWS ONLY")
        sample_rows = execute_query(
            "SELECT TYPENAME, LENGTH FROM SYSCAT.DATATYPES WHERE TYPENAME IN ('INTEGER', 'VARCHAR') FETCH FIRST 2 ROWS ONLY"
        )
        for r in sample_rows:
            print("  Row:", r)

        print("\n[PASSED] Real IBM Db2 connectivity and query verified!")
        return 0
    except Exception as e:
        print(f"\n[FAILED] Db2 Connection Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())

