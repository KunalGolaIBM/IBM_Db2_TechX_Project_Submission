#!/usr/bin/env bash
# Container entrypoint: wait for Db2, build the schema on first start, then serve the UI.
set -euo pipefail
cd /app
echo "[hotelops] waiting for Db2 at ${DB2_HOST:-localhost}:${DB2_PORT:-50000} (first start of Db2 takes 5-10 min) ..."
python - <<'PY'
import sys, time
sys.path.insert(0, "src")
from hotelops.db import get_db, reset_connections
deadline = time.time() + 30 * 60
while True:
    try:
        get_db("admin").scalar("SELECT 1 FROM SYSIBM.SYSDUMMY1")
        get_db("agent").scalar("SELECT 1 FROM SYSIBM.SYSDUMMY1")
        break
    except Exception as exc:  # Db2 still initialising, or the agent OS user not created yet
        if time.time() > deadline:
            sys.exit(f"Db2 not reachable: {exc}")
        reset_connections()
        time.sleep(10)
PY
if python -c "import sys; sys.path.insert(0,'src'); from hotelops.db import get_db; get_db('admin').scalar('SELECT COUNT(*) FROM HOTELOPS.ROOMS')" 2>/dev/null; then
  echo "[hotelops] schema already loaded - keeping existing data (run 'python src/setup_db.py --reset' to rebuild)"
else
  echo "[hotelops] first start: building schema, loading data, embedding reviews, applying security"
  python src/setup_db.py
fi
exec streamlit run src/app.py --server.address 0.0.0.0 --server.port "${APP_PORT:-8501}" \
     --server.headless true --browser.gatherUsageStats false
