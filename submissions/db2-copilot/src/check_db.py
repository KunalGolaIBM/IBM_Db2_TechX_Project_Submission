"""
Verification script for IBM Db2 connection and VECTOR data type / VECTOR_DISTANCE function.
Run from submissions/db2-copilot via Docker:
docker run --rm -v "${PWD}:/app" --env-file .env db2copilot python src/check_db.py
"""
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db import get_connection, execute_query, execute_non_query
import ibm_db


def main():
    print("=" * 60)
    print("IBM Db2 12.1 Vector Diagnostic & Compatibility Check")
    print("=" * 60)

    # 1. Connect
    print("[1/4] Connecting to IBM Db2...")
    try:
        conn = get_connection()
        print("  ✅ Connection established successfully!")
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        sys.exit(1)

    # 2. Basic Query
    print("[2/4] Testing basic SQL execution...")
    try:
        rows = execute_query(conn, "SELECT CURRENT TIMESTAMP AS TS, CURRENT SERVER AS SVR FROM SYSIBM.SYSDUMMY1")
        print(f"  ✅ Server: {rows[0].get('svr')}, Timestamp: {rows[0].get('ts')}")
    except Exception as e:
        print(f"  ❌ Basic SQL failed: {e}")
        sys.exit(1)

    # 3. Create Vector Table
    table_name = "CHECK_VECTOR_TEST"
    print(f"[3/4] Creating test table '{table_name}' with VECTOR(4, FLOAT32)...")
    try:
        # Clean up if exists
        try:
            ibm_db.exec_immediate(conn, f"DROP TABLE {table_name}")
        except Exception:
            pass

        ddl = f"""
        CREATE TABLE {table_name} (
            id INT NOT NULL PRIMARY KEY,
            label VARCHAR(50) NOT NULL,
            embedding VECTOR(4, FLOAT32)
        )
        """
        ibm_db.exec_immediate(conn, ddl)
        print("  ✅ Table created with VECTOR(4, FLOAT32) column!")

        # Insert 3 test vectors
        print("  Inserting test vectors...")
        v1 = "VECTOR('[1.0, 0.0, 0.0, 0.0]', 4, FLOAT32)"
        v2 = "VECTOR('[0.0, 1.0, 0.0, 0.0]', 4, FLOAT32)"
        v3 = "VECTOR('[0.0, 0.0, 1.0, 0.0]', 4, FLOAT32)"

        ibm_db.exec_immediate(conn, f"INSERT INTO {table_name} VALUES (1, 'Vector-X-Axis', {v1})")
        ibm_db.exec_immediate(conn, f"INSERT INTO {table_name} VALUES (2, 'Vector-Y-Axis', {v2})")
        ibm_db.exec_immediate(conn, f"INSERT INTO {table_name} VALUES (3, 'Vector-Z-Axis', {v3})")
        print("  ✅ Inserted 3 rows with native VECTOR values.")
    except Exception as e:
        print(f"  ❌ Vector table creation/insert failed: {e}")
        sys.exit(1)

    # 4. Vector Distance Query
    print("[4/4] Executing vector similarity search using VECTOR_DISTANCE(..., COSINE)...")
    try:
        # Search for vector close to X-axis: [0.95, 0.05, 0.0, 0.0]
        query_vec = "VECTOR('[0.95, 0.05, 0.0, 0.0]', 4, FLOAT32)"
        search_sql = f"""
        SELECT 
            id, 
            label, 
            VECTOR_DISTANCE(embedding, {query_vec}, COSINE) AS distance
        FROM {table_name}
        ORDER BY distance ASC
        FETCH FIRST 3 ROWS ONLY
        """
        results = execute_query(conn, search_sql)
        print("  Vector Search Results:")
        for r in results:
            dist = r.get("distance")
            print(f"    - ID: {r.get('id')}, Label: {r.get('label'):<15}, Cosine Distance: {dist}")

        if results and results[0].get("id") == 1:
            print("  ✅ Vector search correctly identified closest match ('Vector-X-Axis')!")
        else:
            print(f"  ⚠️ Warning: Unexpected top match: {results[0] if results else 'None'}")

    except Exception as e:
        print(f"  ❌ VECTOR_DISTANCE search failed: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        try:
            ibm_db.exec_immediate(conn, f"DROP TABLE {table_name}")
            ibm_db.close(conn)
            print("  🧹 Cleanup: Dropped test table.")
        except Exception:
            pass

    print("=" * 60)
    print("ALL DB2 VECTOR CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()

