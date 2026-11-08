#!/usr/bin/env bash
# Idempotent fix-ups for the IBM Db2 Community Edition container when it runs under
# amd64 emulation on Apple Silicon. Safe to run repeatedly; no-op when nothing is wrong.
#
# Fix 1: sqllib/adm/.fenced is missing after db2icrt under emulation. Db2 identifies the
#        fenced user by that file's owner; without it every FENCED routine (e.g.
#        SYSPROC.ENV_GET_INST_INFO, ADMIN_CMD helpers) fails with SQL1646N.
set -euo pipefail

CONTAINER="${DB2_CONTAINER:-metricguard-db2}"
FENCED="/database/config/db2inst1/sqllib/adm/.fenced"

if docker exec "${CONTAINER}" test -f "${FENCED}"; then
  echo "post-setup: ${FENCED} present; nothing to do."
  exit 0
fi

echo "post-setup: restoring ${FENCED} (owner db2fenc1) and restarting the Db2 instance..."
docker exec "${CONTAINER}" bash -c "touch '${FENCED}' && chown db2fenc1:db2fadm1 '${FENCED}' && chmod 644 '${FENCED}'"
docker exec "${CONTAINER}" su - db2inst1 -c "db2stop force; db2start; db2 activate database \${DBNAME:-MGDB}" \
  | grep -E "SQL1064N|SQL1063N|DB20000I|SQL[0-9]+N" || true
echo "post-setup: done."
