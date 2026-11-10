#!/usr/bin/env bash
# Read-only status of the live stack, run inside the Codespace by .github/workflows/live-status.yml.
cd "$(dirname "$0")/.."
date -u; git log --oneline -1
ls -la --time-style=+%m-%dT%H:%M data/ | grep -E " \.[a-z]|backup"; echo "--- backup.log"; cat data/backup.log 2>/dev/null
echo "--- start log"; tail -n 12 /tmp/aqi-start.log | cut -c1-220
echo "--- containers"; docker compose ps -a --format "{{.Name}} {{.State}} {{.Status}}"
echo "--- tunnel"; cat /tmp/tunnel.url 2>/dev/null || echo "no tunnel url"; pgrep -x cloudflared >/dev/null && echo "cloudflared running" || echo "cloudflared NOT running"; tail -n 3 /tmp/cloudflared.log 2>/dev/null | cut -c1-200
u=$(cat /tmp/tunnel.url 2>/dev/null); [ -n "$u" ] && echo "tunnel health: $(curl -s -m 20 "$u/api/health")"
if [ "${1:-}" = probe ]; then
  echo "--- fresh question through Granite and Db2 (seconds, event)"; s0=$(date +%s.%N)
  curl -sN -m 150 -X POST localhost:8000/api/ask/stream -H "content-type: application/json" \
    -d '{"question":"How many station-days were suspect in December?","fresh":true}' |
    grep -v '"tok"' | cut -c1-200; echo "total $(( $(date +%s) - ${s0%.*} )) s"
fi
[ "${1:-}" = quick ] || [ "${1:-}" = probe ] && exit 0
echo "--- evidence (written to /tmp, the committed file is not touched)"
docker compose run --rm -v /tmp:/out setup python scripts/db2_evidence.py --out /out/ev.md 2>&1 | grep -E "^(PASS|FAIL)|wrote" | cut -c1-260
curl -s -m 10 localhost:8000/api/health; echo
echo "=== EV.MD BEGIN"; cat /tmp/ev.md; echo "=== EV.MD END"
