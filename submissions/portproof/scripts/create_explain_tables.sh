#!/usr/bin/env bash
# Create Db2's Explain tables for PortProof's schema owner.
#
#   bash scripts/create_explain_tables.sh [container] [database] [owner]
#
# Optional. With them, PortProof asks Db2's optimizer what a statement costs
# before and after a meaning repair, and reports a repair that is correct and
# estimated to be much slower. Without them that check is skipped and nothing
# else changes.
#
# Why a separate script, run as the instance owner. Measured on Db2 Community
# Edition 12.1.5.0: EXPLAIN PLAN fails for the schema owner with SQL0219N, "the
# required Explain table PPOWN.EXPLAIN_INSTANCE does not exist", and
# SYSPROC.SYSINSTALLOBJECTS, which creates them, fails for the same owner with
# SQL0551N. So the tables are created here, once, in the owner's own schema,
# rather than by widening what the owner may do.
set -euo pipefail

CONTAINER="${1:-db2spike}"
DATABASE="${2:-testdb}"
OWNER="${3:-PPOWN}"

echo "==> creating the Explain tables for ${OWNER} in '${DATABASE}'"
docker exec -u db2inst1 "${CONTAINER}" bash -lc "
  db2 connect to ${DATABASE} >/dev/null
  db2 -x \"CALL SYSPROC.SYSINSTALLOBJECTS('EXPLAIN', 'C', CAST(NULL AS VARCHAR(128)), '${OWNER}')\" || true
  # The instance owner created them, so the schema owner holds nothing on them
  # yet (SQL0551N on the first EXPLAIN). It needs to write and clear its own
  # explain rows and nothing more.
  for t in \$(db2 -x \"SELECT TABNAME FROM SYSCAT.TABLES WHERE TABSCHEMA = '${OWNER}'
                       AND TYPE = 'T' AND (TABNAME LIKE 'EXPLAIN%' OR TABNAME LIKE 'ADVISE%'
                       OR TABNAME = 'OBJECT_METRICS')\"); do
    db2 -x \"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE ${OWNER}.\${t} TO USER ${OWNER}\" >/dev/null
  done
  db2 -x \"SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA = '${OWNER}' AND TABNAME LIKE 'EXPLAIN%'\"
"
