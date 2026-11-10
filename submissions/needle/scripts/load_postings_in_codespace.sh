#!/usr/bin/env bash
# Local wrapper (Git Bash on the PC): copy the BM25 files into the codespace and load them there.
# The Db2 password is read from needle/.env at runtime and sent to the remote shell on STDIN,
# so it never appears on a command line, in a log, or in a file.
# Prerequisite: `python -m needle.bm25 build` has written data/postings.jsonl.gz and data/corpus_stats.json.
# Usage: scripts/load_postings_in_codespace.sh [steps]   (default: ddl,load,post,check)
#        SKIP_COPY=1 scripts/load_postings_in_codespace.sh post,check
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
envval() { grep -E "^$1=" "$HERE/.env" | head -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"; }
CS="$(envval CODESPACE)"
STEPS="${1:-ddl,load,post,check}"
[[ "$STEPS" =~ ^[a-z,]+$ ]] || { echo "bad steps" >&2; exit 2; }

if [[ "${SKIP_COPY:-0}" != "1" ]]; then
  gh codespace ssh -c "$CS" -- 'mkdir -p /tmp/needle'
  gh codespace cp -c "$CS" -e \
    "$HERE/sql/02_bm25.sql" "$HERE/scripts/load_postings_in_codespace.py" \
    "$HERE/data/postings.jsonl.gz" "$HERE/data/corpus_stats.json" \
    remote:/tmp/needle/
fi

envval DB2_PASSWORD | gh codespace ssh -c "$CS" -- \
  "IFS= read -r DB2_PASSWORD; export DB2_PASSWORD; python3 -u /tmp/needle/load_postings_in_codespace.py --steps $STEPS 2>&1 | tee -a /tmp/needle/load_postings.log"
