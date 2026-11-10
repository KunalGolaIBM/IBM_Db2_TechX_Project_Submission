#!/usr/bin/env bash
# Read-only status of the live stack, run inside the Codespace by .github/workflows/live-status.yml.
cd "$(dirname "$0")/.."
date -u; git log --oneline -1
ls -la --time-style=+%m-%dT%H:%M data/ | grep -E " \.[a-z]|backup"; echo "--- backup.log"; cat data/backup.log 2>/dev/null
echo "--- start log"; tail -n 12 /tmp/aqi-start.log | cut -c1-220
echo "--- containers"; docker compose ps -a --format "{{.Name}} {{.State}} {{.Status}}"
echo "--- evidence (written to /tmp, the committed file is not touched)"
docker compose run --rm -v /tmp:/out setup python scripts/db2_evidence.py --out /out/ev.md 2>&1 | grep -E "^(PASS|FAIL)|wrote" | cut -c1-260
curl -s -m 10 localhost:8000/api/health; echo
echo "=== EV.MD BEGIN"; cat /tmp/ev.md; echo "=== EV.MD END"
