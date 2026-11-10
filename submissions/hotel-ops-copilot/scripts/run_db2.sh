#!/usr/bin/env bash
# Start IBM Db2 Community Edition without the docker compose plugin.
# Reads ../.env (same variables as docker-compose.yml). Run from anywhere.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a; source "${HERE}/.env"; set +a

docker run -d --name hotelops-db2 --privileged \
  -p "${DB2_PORT:-50000}:50000" \
  -e LICENSE=accept \
  -e DB2INSTANCE="${DB2_USER:-db2inst1}" \
  -e DB2INST1_PASSWORD="${DB2_PASSWORD:?set DB2_PASSWORD in .env}" \
  -e DBNAME="${DB2_DATABASE:-HOTELDB}" \
  -e BLU=false -e ENABLE_ORACLE_COMPATIBILITY=false -e PERSISTENT_HOME=true \
  -e AGENT_USER="${DB2_AGENT_USER:-opsagent}" \
  -e AGENT_PASSWORD="${DB2_AGENT_PASSWORD:?set DB2_AGENT_PASSWORD in .env}" \
  -v hotelops_db2data:/database \
  -v "${HERE}/docker/custom:/var/custom" \
  icr.io/db2_community/db2:latest

echo "Db2 is starting. Follow progress with: docker logs -f hotelops-db2  (wait for 'Setup has completed')"
