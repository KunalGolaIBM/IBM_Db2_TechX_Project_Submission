"""Blocks until Db2 accepts connections (first container boot takes several minutes)."""
import time
import sys
import db

for i in range(120):
    try:
        db.conn()
        print("Db2 is ready:", db.version())
        sys.exit(0)
    except Exception as e:
        print(f"waiting for Db2... ({i + 1}/120) {str(e)[:80]}")
        db._conn = None
        time.sleep(5)
print("Db2 did not become ready in 10 minutes. Check: docker compose logs db2")
sys.exit(1)
