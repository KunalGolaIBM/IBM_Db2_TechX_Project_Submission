#!/usr/bin/env bash
# Run this in a Codespace terminal and leave the browser tab open during judging.
# It shows startup progress, then prints a health line every minute so the terminal is never idle.
URL="https://${CODESPACE_NAME}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
echo "Public URL: $URL"
until grep -q READY /tmp/aqi-start.log 2>/dev/null; do tail -n 2 /tmp/aqi-start.log 2>/dev/null; sleep 30; done
echo "Stack is up. Keep this tab open."
while true; do
  printf '%s  ' "$(date '+%H:%M')"; curl -s -m 20 localhost:8000/api/health || echo "app not answering"; echo
  sleep 60
done
