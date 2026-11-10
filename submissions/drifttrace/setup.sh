#!/usr/bin/env bash
# DriftTrace one-command local setup. Run from the OFFICIAL REPO ROOT:
#   bash submissions/drifttrace/setup.sh
# Creates (outside the submission folder, gitignored): .venv/, .env.db2.drifttrace, .env.drifttrace
# Starts IBM Db2 Community Edition in Docker (LICENSE=accept accepts IBM's Db2 Community Edition license),
# creates a least-privilege OS/Db2 user 'driftapp', seeds synthetic data and runs the tests.
# Never prints passwords or keys. Safe to re-run (idempotent).
set -euo pipefail

SUB="submissions/drifttrace"
[ -f "$SUB/src/app.py" ] || { echo "Run from the official repository root."; exit 1; }
PY="${PYTHON:-python3.12}"
command -v "$PY" >/dev/null || { echo "Python 3.12 not found (set PYTHON=...)."; exit 1; }
command -v docker >/dev/null || { echo "Docker is required."; exit 1; }

rand() { LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20; }

echo "== 1/6 Python environment"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r "$SUB/requirements.txt"

echo "== 2/6 Private env files (outside $SUB)"
umask 077
if [ ! -f .env.db2.drifttrace ]; then
  printf 'LICENSE=accept\nDB2INSTANCE=db2inst1\nDB2INST1_PASSWORD=%s\nDBNAME=testdb\nIS_OSXFS=true\nPERSISTENT_HOME=true\nARCHIVE_LOGS=false\nAUTOCONFIG=false\n' "$(rand)" > .env.db2.drifttrace
fi
ADMIN_PWD="$(grep '^DB2INST1_PASSWORD=' .env.db2.drifttrace | cut -d= -f2-)"
if [ ! -f .env.drifttrace ]; then
  printf 'DB2_DATABASE=testdb\nDB2_HOSTNAME=127.0.0.1\nDB2_PORT=50000\nDB2_UID=driftapp\nDB2_PWD=%s\nDB2_SCHEMA=DB2INST1\nDB2_SECURITY=\nDB2_ADMIN_UID=db2inst1\nDB2_ADMIN_PWD=%s\nGOOGLE_API_KEY=\nAI_MODEL=gemini-3.5-flash-lite\n' "$(rand)" "$ADMIN_PWD" > .env.drifttrace
  echo "   Created .env.drifttrace - add your GOOGLE_API_KEY there for live AI extraction."
fi
APP_PWD="$(grep '^DB2_PWD=' .env.drifttrace | cut -d= -f2-)"

echo "== 3/6 Db2 Community Edition container"
if ! docker ps -a --format "{{.Names}}" | grep -x drifttrace-db2 >/dev/null; then
  docker run -d --name drifttrace-db2 --privileged --platform linux/amd64 --shm-size=1g --ipc=host \
    -p 127.0.0.1:50000:50000 --env-file .env.db2.drifttrace \
    -v drifttrace_db2_data:/database icr.io/db2_community/db2:latest >/dev/null
else
  docker start drifttrace-db2 >/dev/null
fi
echo "   Waiting for Db2 setup (first start can take 5-20 minutes)..."
for _ in $(seq 1 240); do
  docker logs drifttrace-db2 2>&1 | grep "Setup has completed" >/dev/null && break
  sleep 5
done
docker logs drifttrace-db2 2>&1 | grep "Setup has completed" >/dev/null || { echo "Db2 did not finish setup; check: docker logs drifttrace-db2"; exit 1; }

echo "== 4/6 Least-privilege application user"
docker exec drifttrace-db2 bash -c "id driftapp >/dev/null 2>&1 || useradd -M -s /sbin/nologin driftapp"
printf 'driftapp:%s\n' "$APP_PWD" | docker exec -i drifttrace-db2 chpasswd
unset ADMIN_PWD APP_PWD

echo "== 5/6 Schema, grants, synthetic data"
.venv/bin/python "$SUB/src/seed.py"
.venv/bin/python "$SUB/src/check_db2.py"

echo "== 6/6 Tests"
.venv/bin/python -m pytest "$SUB/tests" -q -p no:cacheprovider -rs

echo
echo "Ready. Start the app with:"
echo "  .venv/bin/streamlit run $SUB/src/app.py"
