#!/usr/bin/env bash
# One command from a fresh clone to a running app:
#   bash scripts/quickstart.sh            # start Db2, install, load data, open the UI on :8501
#   bash scripts/quickstart.sh --no-ui    # same, but stop after loading and testing
#
# Needs: docker, Python 3.10-3.12. Linux, macOS or WSL2 (see the README's Windows note).
# Safe to re-run: the database is rebuilt from scratch each time (~20 s).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
VENV="${VENV:-.venv}"
PY="${PYTHON:-python3}"
say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

# 1. .env with generated passwords (never committed)
if [ ! -f .env ]; then
  say "Creating .env with random Db2 passwords"
  cp .env.example .env
  sed -i.bak "s/^DB2_PASSWORD=.*/DB2_PASSWORD=Db2$(openssl rand -hex 10)/" .env
  sed -i.bak "s/^DB2_AGENT_PASSWORD=.*/DB2_AGENT_PASSWORD=Ag$(openssl rand -hex 10)/" .env
  sed -i.bak "s/^GOOGLE_API_KEY=.*/GOOGLE_API_KEY=/" .env
  rm -f .env.bak
fi
grep -qE '^GOOGLE_API_KEY=.+' .env || echo "Note: GOOGLE_API_KEY is empty. Approvals, time travel, dashboard and audit work; add a key for the agents."

# 2. Db2 container
RUNNING="$(docker ps --format '{{.Names}}')"; ALL="$(docker ps -a --format '{{.Names}}')"
if grep -qx hotelops-db2 <<<"$RUNNING"; then
  say "Db2 container already running"
else
  if grep -qx hotelops-db2 <<<"$ALL"; then
    say "Starting existing Db2 container"; docker start hotelops-db2 >/dev/null
  else
    say "Starting IBM Db2 Community Edition (first start downloads ~3 GB and takes 5-10 min)"
    bash scripts/run_db2.sh
  fi
fi
say "Waiting for Db2 to accept connections"
for _ in $(seq 1 240); do
  # (no `grep -q` on a pipe: with pipefail an early grep exit fails the whole pipeline)
  if [ "$(docker logs hotelops-db2 2>&1 | grep -c 'Setup has completed')" -gt 0 ] &&
     docker exec hotelops-db2 bash -lc "su - \${DB2INSTANCE:-db2inst1} -c 'db2 connect to \${DBNAME:-HOTELDB}' >/dev/null 2>&1"; then
    echo "Db2 is ready"; break
  fi
  sleep 5
done

# 3. Python environment
if [ ! -x "$VENV/bin/python" ]; then
  say "Creating virtual environment $VENV"
  "$PY" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
say "Installing Python dependencies"
if command -v uv >/dev/null 2>&1; then
  uv pip install -q -r requirements.txt
else
  python -m pip install -q -r requirements.txt
fi

# 4. Schema, data, embeddings, security, then the test suite
say "Building the HOTELOPS schema and loading data"
python src/setup_db.py --reset
say "Running tests (unit + live Db2 integration)"
python -m pytest -q tests/

if [ "${1:-}" = "--no-ui" ]; then exit 0; fi
say "Opening the app at http://localhost:8501"
exec streamlit run src/app.py --server.headless true --browser.gatherUsageStats false
