#!/usr/bin/env bash
# One command from a fresh clone to a running AsOf:
#
#   ./quickstart.sh             # set up everything, then serve http://127.0.0.1:8000
#   ./quickstart.sh --no-serve  # set up everything and stop (CI uses this)
#
# 1. A Python 3.12 virtualenv with the locked dependencies (.venv).
# 2. .env from .env.example. If no Db2 owner password is set, it either asks for the password of the Db2
#    already listening on localhost:50000, or generates one for the Db2 this script starts. Secrets are
#    written to .env (mode 600) and never printed.
# 3. Db2: the one already on localhost:50000 (README paths A and B), otherwise AsOf's Compose service (path C).
# 4. python -m asof.setup: users, schema, seed data, grants, self-check.
# 5. The API and UI.
set -euo pipefail
cd "$(dirname "$0")"

SERVE=1
[[ "${1:-}" == "--no-serve" ]] && SERVE=0
say() { printf '\n== %s\n' "$*"; }
port_open() { (exec 3<>/dev/tcp/127.0.0.1/50000) 2>/dev/null; }

PY=""
for candidate in python3.12 python3; do
  if command -v "$candidate" > /dev/null && "$candidate" -c 'import sys; sys.exit(sys.version_info[:2] != (3, 12))'; then
    PY="$candidate"; break
  fi
done
[[ -n "$PY" ]] || { echo "AsOf needs Python 3.12 (python3.12 was not found)."; exit 1; }

say "1/5 Python environment (.venv, locked dependencies)"
[[ -d .venv ]] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
if [[ "$(uname -s)" == "Linux" ]]; then  # the CPU build: the default wheel pulls gigabytes of CUDA libraries
  .venv/bin/pip install -q torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
fi
.venv/bin/pip install -q -r requirements.txt -c requirements.lock
.venv/bin/pip install -q -e . --no-deps

say "2/5 Configuration (.env)"
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "  created .env from .env.example"
fi
chmod 600 .env
owner_pw="$(sed -n 's/^DB2_PASSWORD=//p; s/^DB2_ADMIN_PASSWORD=//p' .env | grep -v '^$' | head -1 || true)"
if [[ -z "$owner_pw" || "$owner_pw" == "change-me-db2-admin" ]]; then
  if port_open; then
    read -rsp "  A Db2 is listening on localhost:50000. Its owner (db2inst1) password: " owner_pw; echo
  else
    owner_pw="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(18))')"
    echo "  generated an owner password for the Db2 this script will start (saved in .env, not shown)"
  fi
  DB2_PW="$owner_pw" .venv/bin/python - <<'PY'
import os, pathlib, re
p = pathlib.Path(".env")
text = p.read_text(encoding="utf-8")
line = "DB2_PASSWORD=" + os.environ["DB2_PW"]
text, n = re.subn(r"(?m)^DB2_PASSWORD=.*$", lambda _: line, text)
p.write_text(text if n else text.rstrip("\n") + "\n" + line + "\n", encoding="utf-8")
PY
fi
unset owner_pw

say "3/5 IBM Db2"
if port_open; then
  echo "  using the Db2 already listening on localhost:50000"
else
  command -v docker > /dev/null || { echo "  No Db2 on localhost:50000 and no docker: see README, Setup paths A to C."; exit 1; }
  echo "  starting AsOf's Db2 service (the first start can take several minutes; it waits until testdb is ready)"
  docker compose up -d --wait db2
fi

say "4/5 Schema, users and data"
.venv/bin/python -m asof.setup

key="$(sed -n 's/^OPENROUTER_API_KEY=//p' .env | head -1)"
provider="$(sed -n 's/^LLM_PROVIDER=//p' .env | head -1)"
if [[ -z "$key" && "$provider" != "ollama" && "$provider" != "openai_compatible" ]]; then
  echo
  echo "  NOTE: no OPENROUTER_API_KEY in .env. Every check will fail closed (held for a specialist) until you add"
  echo "  one, or set LLM_PROVIDER=ollama with a local Ollama. The ledger, replay, timeline and change impact work regardless."
fi
unset key

if [[ "$SERVE" == "1" ]]; then
  say "5/5 AsOf on http://127.0.0.1:8000 (Ctrl+C to stop)"
  exec .venv/bin/python src/main.py
else
  say "5/5 Done. Start AsOf with: .venv/bin/python src/main.py"
fi
