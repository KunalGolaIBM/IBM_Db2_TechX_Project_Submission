#!/usr/bin/env bash
# Starts the full AQI Truth stack inside a GitHub Codespace and makes port 8000 public.
# Runs automatically on every Codespace start (see .devcontainer/devcontainer.json); log: /tmp/aqi-start.log
set -euo pipefail
echo $$ > /tmp/aqi-start.pid
cd "$(dirname "$0")/.."
echo "start $(date -u +%H:%M:%S)"
if [ ! -f .env ]; then
  cp .env.example .env
  sed -i "s/^DB2_PASSWORD=.*/DB2_PASSWORD=$(openssl rand -hex 12)/; s/^DB2_READER_PASSWORD=.*/DB2_READER_PASSWORD=$(openssl rand -hex 12)/" .env
  chmod 600 .env
fi
grep -q '^DB2_APP_PASSWORD=' .env || printf 'DB2_APP_USER=aqapp\nDB2_APP_PASSWORD=%s\n' "$(openssl rand -hex 12)" >> .env
sed -i "s/^DB2_APP_PASSWORD=change-me-app$/DB2_APP_PASSWORD=$(openssl rand -hex 12)/" .env
URL="https://${CODESPACE_NAME:-unknown}-8000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-app.github.dev}"
grep -q '^ALLOWED_ORIGINS=' .env || echo "ALLOWED_ORIGINS=https://debi910.github.io,${URL}" >> .env
until docker info >/dev/null 2>&1; do sleep 2; done
echo "docker ready"
# Second public route: a Cloudflare quick tunnel (no account, no card) for networks that block *.github.dev.
# Its random https://<words>.trycloudflare.com address goes to /tmp/tunnel.url; the keep-alive job publishes it
# on the 'endpoint' branch, where the GitHub Pages site looks for it.
if ! pgrep -x cloudflared >/dev/null; then
  [ -x /tmp/cloudflared ] || { curl -fsSL -o /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 && chmod +x /tmp/cloudflared; } || true
  rm -f /tmp/tunnel.url   # a new tunnel gets a new address; never publish the old one
  [ -x /tmp/cloudflared ] && setsid nohup /tmp/cloudflared tunnel --no-autoupdate --protocol http2 --url http://localhost:8000 > /tmp/cloudflared.log 2>&1 < /dev/null &
fi
( for i in $(seq 1 60); do u=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' /tmp/cloudflared.log 2>/dev/null | head -1); [ -n "$u" ] && { echo "$u" > /tmp/tunnel.url; break; }; sleep 2; done ) &
# One-off (approved 9 Nov 2026): the Db2 container failed its own setup after being recreated, so start from a
# fresh database volume and reload the public data. Downloaded files in data/raw and the Granite models are kept.
if [ ! -f data/.fresh_v2 ]; then
  echo "one-off: rebuilding the Db2 database"
  docker compose rm -sf db2 || true
  docker volume ls -q | grep -E '_db2data$' | xargs -r docker volume rm || true
  rm -f data/.full_loaded data/.audit_v2
  touch data/.fresh_v2
fi
echo "starting compose"
# Db2 first. A recreated container (new settings) keeps the database volume but not the OS users that Db2
# authenticates against, and its health check waits for them; so create them (idempotent) once Db2 answers.
docker compose up -d db2 ollama
until docker compose exec -T db2 bash -c 'su - db2inst1 -c "db2 connect to ${DBNAME:-AQIDB}" >/dev/null 2>&1'; do sleep 10; done
docker compose exec -T db2 bash /var/custom/01_reader.sh
echo "db2 ready, users in place"
# Safety rule (10 Nov 2026): back the live database up once before the add-only 10 Nov changes (sql/09, the 2026
# re-fetch) touch it. Offline image, ~10 s; restore with: db2 restore db AQIDB from /database/backup taken at <timestamp>
if [ -f data/.full_loaded ] && [ ! -f data/.backup_1110 ]; then
  docker compose stop app >/dev/null 2>&1 || true
  docker compose exec -T db2 bash -c 'mkdir -p /database/backup && chown db2inst1 /database/backup && su - db2inst1 -c "db2 force applications all >/dev/null; db2 deactivate db ${DBNAME:-AQIDB} >/dev/null; db2 backup db ${DBNAME:-AQIDB} to /database/backup compress without prompting"' \
    | tee -a data/backup.log | grep -q "Backup successful" && touch data/.backup_1110
  [ -f data/.backup_1110 ] || { echo "BACKUP FAILED: not applying the 10 Nov changes"; touch data/.no_changes; }
fi
until docker compose up -d --build; do echo "compose up failed; retrying in 30 s"; sleep 30; done
until [ "$(docker compose ps -a setup --format '{{.State}}')" = "exited" ]; do sleep 15; done
# Schema migrations (new triggers, indexes, views, grants) without touching loaded data.
# 10 Nov rule: sql/09 is applied only after the backup above and only before 05:30 UTC; once applied, re-runs are no-ops.
CUTOFF_OK=$([ "$(date -u +%FT%H%M)" \< "2026-11-10T0530" ] && echo 1 || echo 0)
if [ ! -f data/.full_loaded ] || { [ -f data/.backup_1110 ] && { [ -f data/.m09 ] || [ "$CUTOFF_OK" = 1 ]; }; }; then
  docker compose run --rm setup python src/load.py data/sample 2025-10-01 2025-10-31 --if-empty --no-embed && touch data/.m09 || true
fi
# One-off after the 9 Nov 2026 method fixes: re-audit the loaded range with the new rules (appends new verdicts with
# receipts; the readings and their history are untouched), then refresh the Db2 evidence file.
if [ -f data/.full_loaded ] && [ ! -f data/.audit_v2 ]; then
  docker compose run --rm setup python src/load.py data/sample 2025-09-01 2025-12-31 --append --reaudit --no-embed && touch data/.audit_v2
  mkdir -p docs && docker compose run --rm -v "$PWD/docs:/app/docs" setup python scripts/db2_evidence.py || true
  docker compose up -d --force-recreate app
fi
if [ ! -f data/.full_loaded ]; then
  docker compose run --rm -v "$PWD/data/raw:/app/data/raw" setup sh -c \
    "python scripts/fetch_openaq.py data/raw 2025 09,10,11,12 && python src/load.py data/raw 2025-09-01 2025-12-31 --append --reaudit" \
    && touch data/.full_loaded data/.audit_v2
  mkdir -p docs && docker compose run --rm -v "$PWD/docs:/app/docs" setup python scripts/db2_evidence.py || true
  docker compose restart app
fi
# Second period, Oct 2026 onward (as far as the archive reaches). Each fetch goes to a new folder, so a later
# fetch of the same days MERGEs in any values CPCB revised since; the old ones stay in READING_HIST.
if [ -f data/.full_loaded ] && [ ! -f data/.y2026a ] && [ ! -f data/.no_changes ] && [ "$(date -u +%FT%H%M)" \< "2026-11-10T0530" ]; then
  docker compose run --rm -v "$PWD/data/raw:/app/data/raw" setup sh -c \
    "python scripts/fetch_openaq.py data/raw/2026a 2026 10,11 && python src/load.py data/raw/2026a 2026-10-01 2026-11-05 --append --no-embed" \
    && touch data/.y2026a
  docker compose restart app
fi
# Re-fetch of the same 2026 days on 10 Nov (approved 9 Nov): CPCB revises recent values, so this MERGE records real
# revisions in READING_HIST and the affected receipts report DATA_CHANGED. Loads up to the last well-covered day.
# Safety rule: no live-database changes after 11:00 IST (05:30 UTC) on 10 Nov; a later start skips this block.
if [ -f data/.y2026a ] && [ ! -f data/.y2026b ] && [ ! -f data/.no_changes ] && [ "$(date -u +%FT%H%M)" \> "2026-11-09" ] && [ "$(date -u +%FT%H%M)" \< "2026-11-10T0530" ]; then
  docker compose run --rm -v "$PWD/data/raw:/app/data/raw" setup python scripts/fetch_openaq.py data/raw/2026b 2026 10,11 || true
  END=$(cat data/raw/2026b/*-2026-11.csv 2>/dev/null | grep -oE '"2026-11-[0-9]{2}T' | sort | uniq -c | awk '$1>5000{d=$2} END{print substr(d,2,10)}')
  if [ -n "$END" ]; then
    docker compose run --rm -v "$PWD/data/raw:/app/data/raw" setup python src/load.py data/raw/2026b 2026-10-01 "$END" --append --no-embed \
      && touch data/.y2026b
    docker compose restart app
  fi
fi
[ -n "${CODESPACE_NAME:-}" ] && gh codespace ports visibility 8000:public -c "$CODESPACE_NAME" 2>/dev/null || echo "port visibility is set by the keep-alive job"
echo "READY: $URL"
