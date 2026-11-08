#!/usr/bin/env bash
# Collect optimizer statistics through the Db2 CLP inside the local container.
# Used when SYSPROC.ADMIN_CMD (a fenced routine) is unavailable under amd64 emulation.
set -euo pipefail

CONTAINER="${DB2_CONTAINER:-metricguard-db2}"
DBNAME="${DB2_DATABASE:-MGDB}"

if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  echo "runstats: container ${CONTAINER} not running; skipping (remote Db2 uses ADMIN_CMD)."
  exit 0
fi

docker exec "${CONTAINER}" su - db2inst1 -c "
  db2 -v connect to ${DBNAME} >/dev/null &&
  for t in PRODUCTS ORDERS ORDER_ITEMS REFUNDS METRIC_DEFINITIONS; do
    db2 \"RUNSTATS ON TABLE METRICGUARD.\$t WITH DISTRIBUTION AND DETAILED INDEXES ALL\" | grep -E 'DB20000I|SQL[0-9]+N'
  done
  db2 connect reset >/dev/null"
echo "runstats: done."
