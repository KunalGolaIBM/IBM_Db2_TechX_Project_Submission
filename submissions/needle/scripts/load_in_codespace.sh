#!/usr/bin/env bash
# Local wrapper (Git Bash on the PC): copy the data + loader into the codespace and run the load there.
# The Db2 password is read from needle/.env at runtime and sent to the remote shell on STDIN,
# so it never appears on a command line, in a log, or in a file.
# Usage: scripts/load_in_codespace.sh [steps]   (default: ddl,raw,doc,alias,affected,post)
#        SKIP_COPY=1 scripts/load_in_codespace.sh doc,post
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
envval() { grep -E "^$1=" "$HERE/.env" | head -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"; }
CS="$(envval CODESPACE)"
STEPS="${1:-ddl,raw,doc,alias,affected,post}"
[[ "$STEPS" =~ ^[a-z,]+$ ]] || { echo "bad steps" >&2; exit 2; }

if [[ "${SKIP_COPY:-0}" != "1" ]]; then
  gh codespace ssh -c "$CS" -- 'mkdir -p /tmp/needle'
  gh codespace cp -c "$CS" -e \
    "$HERE/sql/01_schema.sql" "$HERE/scripts/load_in_codespace.py" \
    "$HERE/data/docs.jsonl" "$HERE/data/emb.jsonl.gz" "$HERE/data/raw.jsonl.gz" \
    remote:/tmp/needle/
fi

envval DB2_PASSWORD | gh codespace ssh -c "$CS" -- \
  "IFS= read -r DB2_PASSWORD; export DB2_PASSWORD; python3 -u /tmp/needle/load_in_codespace.py --steps $STEPS 2>&1 | tee -a /tmp/needle/load.log"
