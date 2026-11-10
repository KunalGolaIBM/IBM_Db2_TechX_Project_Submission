#!/usr/bin/env bash
# Local wrapper (Git Bash on the PC) for scripts/connector_findings.py. Runs the measurement INSIDE the
# codespace so latencies exclude the PC tunnel. The Db2 password is read from needle/.env and sent on STDIN.
# Usage: scripts/connector_findings.sh <setup|f1|f2|f3f4|tempspace|writes|cleanup>
# One-time in the codespace: an isolated venv /tmp/needle/conn_venv with langchain-db2==1.0.0
# (--system-site-packages, so the codespace's ibm_db 3.3.0 is used). The PC's needle/.venv is not touched.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
envval() { grep -E "^$1=" "$HERE/.env" | head -1 | cut -d= -f2- | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"; }
CS="$(envval CODESPACE)"
STEP="${1:?step}"
[[ "$STEP" =~ ^(setup|f1|f2|f3f4|tempspace|writes|cleanup)$ ]] || { echo "bad step" >&2; exit 2; }

gh codespace ssh -c "$CS" -- 'mkdir -p /tmp/needle/conn_out; test -x /tmp/needle/conn_venv/bin/python || (python3 -m venv --system-site-packages /tmp/needle/conn_venv && /tmp/needle/conn_venv/bin/python -m pip install -q "langchain-db2==1.0.0")'
gh codespace cp -c "$CS" -e "$HERE/scripts/connector_findings.py" "$HERE/data/eval_qvecs.json.gz" remote:/tmp/needle/

envval DB2_PASSWORD | gh codespace ssh -c "$CS" -- \
  "IFS= read -r DB2_PASSWORD; export DB2_PASSWORD; cd /tmp/needle && /tmp/needle/conn_venv/bin/python -u connector_findings.py $STEP"

mkdir -p "$HERE/docs/evidence" "$HERE/eval/results"
gh codespace cp -c "$CS" -e "remote:/tmp/needle/conn_out/connector_${STEP}.txt" "$HERE/docs/evidence/"
if [[ "$STEP" == "f3f4" ]]; then
  gh codespace cp -c "$CS" -e "remote:/tmp/needle/conn_out/db2vs_baseline.json" "$HERE/eval/results/"
fi
