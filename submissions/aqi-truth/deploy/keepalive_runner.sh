#!/usr/bin/env bash
# Run by .github/workflows/keep-demo-alive.yml on a GitHub-hosted runner.
#   keepalive_runner.sh stop          stop the demo Codespace
#   keepalive_runner.sh keep END [P]  keep it up until END (unix seconds), at most ~5.5 h per run; P=1 also probes /api/ask.
#                                     If END is later than this run can last, the run hands over to a fresh run of the
#                                     workflow (workflow_dispatch). At END it stops the Codespace unless the judging window is open.
# Env: GH_TOKEN (classic PAT, "codespace" scope), PUB_TOKEN (the workflow's GITHUB_TOKEN), REPO, WINDOW_START, WINDOW_END.
set -uo pipefail
cs() { gh codespace list -R "$REPO" --json name,state -q '.[0].name'; }
ssh_cs() { timeout 120 gh codespace ssh -c "$NAME" -- "$@"; }
in_window() { local n; n=$(date -u +%s); [ "$n" -ge "$(date -u -d "$WINDOW_START" +%s)" ] && [ "$n" -le "$(date -u -d "$WINDOW_END" +%s)" ]; }

stop_all() {
  gh codespace list -R "$REPO" --json name,state -q '.[] | select(.state=="Available") | .name' | while read -r n; do
    echo "stopping $n"; gh codespace stop -c "$n"; done
}

ensure_stack() {
  # ssh starts a stopped Codespace by itself; the start script is idempotent and runs detached.
  ssh_cs 'cd /workspaces/aqi-truth && git checkout -q -- docs/DB2_VERIFICATION.md 2>/dev/null; git pull -q --ff-only || true; if [ -f /tmp/aqi-start.pid ] && kill -0 "$(cat /tmp/aqi-start.pid)" 2>/dev/null; then echo "start script running"; else CODESPACE_NAME='"$NAME"' setsid nohup bash deploy/codespace_start.sh >> /tmp/aqi-start.log 2>&1 < /dev/null & echo "start script launched"; fi'
  gh codespace ports visibility 8000:public -c "$NAME" >/dev/null 2>&1 || true
}

publish_tunnel() {
  local u cur sha body
  u=$(ssh_cs 'cat /tmp/tunnel.url 2>/dev/null' | tr -d '\r\n')
  [ -n "$u" ] || return 0
  cur=$(GH_TOKEN=$PUB_TOKEN gh api "repos/$REPO/contents/endpoint.json?ref=endpoint" -q .content 2>/dev/null | base64 -d 2>/dev/null | grep -oE 'https://[^"]+' || true)
  [ "$cur" = "$u" ] && return 0
  sha=$(GH_TOKEN=$PUB_TOKEN gh api "repos/$REPO/contents/endpoint.json?ref=endpoint" -q .sha)
  body=$(printf '{"api":"%s","updated":"%s"}\n' "$u" "$(date -u +%FT%TZ)" | base64 -w0)
  GH_TOKEN=$PUB_TOKEN gh api -X PUT "repos/$REPO/contents/endpoint.json" -f branch=endpoint -f message="Second route: $u" -f content="$body" -f sha="$sha" -q .commit.sha >/dev/null \
    && echo "published second route $u (health: $(curl -s -m 20 "$u/api/health"))"
}

probe() {
  local U="https://$NAME-8000.app.github.dev" s0
  echo "--- streamed question through the public port (seconds, event)"; s0=$(date +%s.%N)
  curl -sN -m 150 -X POST "$U/api/ask/stream" -H "Origin: https://debi910.github.io" -H "content-type: application/json" \
    -d '{"question":"How many station-days were suspect in December?","fresh":true}' |
    while IFS= read -r l; do printf '%5.1f %s\n' "$(echo "$(date +%s.%N) - $s0" | bc)" "$(echo "$l" | cut -c1-90)"; done | awk '!/"tok"/ || ++n<=3'
  echo "--- start log"; ssh_cs 'tail -n 8 /tmp/aqi-start.log | cut -c1-200; tail -n 2 /tmp/cloudflared.log | cut -c1-200'
  echo "--- containers and Db2 log"; ssh_cs 'cd /workspaces/aqi-truth && docker compose ps -a --format "{{.Name}} {{.State}} {{.Status}}"; docker compose logs --tail 40 db2 2>&1 | cut -c1-180'
}

case "${1:-}" in
  stop) stop_all ;;
  keep)
    END=$2; PROBE=${3:-0}; T0=$(date -u +%s); LIMIT=$(( T0 + ${RUN_MINUTES:-330} * 60 ))
    NAME=$(cs); [ -n "$NAME" ] || { echo "no Codespace for $REPO"; exit 1; }
    echo "keeping $NAME up until $(date -u -d "@$END" +%FT%TZ) (this run until $(date -u -d "@$(( END < LIMIT ? END : LIMIT ))" +%FT%TZ))"
    ensure_stack; i=0
    while :; do
      now=$(date -u +%s); [ "$now" -ge "$END" ] || [ "$now" -ge "$LIMIT" ] && break
      [ $(( i % 10 )) -eq 0 ] && [ "$i" -gt 0 ] && ensure_stack >/dev/null
      { [ "$i" -lt 4 ] || [ $(( i % 10 )) -eq 0 ]; } && publish_tunnel
      [ "$i" -eq 5 ] && [ "$PROBE" = "1" ] && probe
      printf '%s %s\n' "$(date -u +%H:%M)" "$(ssh_cs 'curl -s -m 20 localhost:8000/api/health || echo starting' | tr -d '\r')"
      i=$(( i + 1 )); sleep 50
    done
    now=$(date -u +%s)
    if [ "$now" -lt "$END" ]; then
      echo "handing over to a new run until $(date -u -d "@$END" +%FT%TZ)"
      GH_TOKEN=$PUB_TOKEN gh api -X POST "repos/$REPO/actions/workflows/keep-demo-alive.yml/dispatches" -f ref=main -f "inputs[until]=$(date -u -d "@$END" +%FT%TZ)" -f "inputs[run_minutes]=${RUN_MINUTES:-330}"
    elif in_window; then echo "judging window open: leaving the Codespace running"
    else echo "done: stopping the Codespace to save hours"; stop_all; fi ;;
  *) echo "usage: $0 stop | keep END [PROBE]"; exit 2 ;;
esac
