#!/usr/bin/env bash
# Format the access plan of statements that OTHER users actually executed (package cache -> EXPLAIN_FROM_SECTION).
# Runs INSIDE the codespace; uses the instance owner's local CLP connection in the db2 container (no password).
# Usage: bash rcac_explain_section.sh '<LIKE pattern on STMT_TEXT>' <outfile_prefix>
set -euo pipefail
PATTERN="$1"; OUT="$2"; CONTAINER="${CONTAINER:-db2}"; DB="${DB:-VECDB}"
# The pattern is passed through a file in the container to avoid quoting problems; it is not a secret.
printf '%s' "$PATTERN" > /tmp/ndl_pattern.txt
docker cp /tmp/ndl_pattern.txt "$CONTAINER":/tmp/ndl_pattern.txt >/dev/null
docker exec "$CONTAINER" chmod 644 /tmp/ndl_pattern.txt
docker exec "$CONTAINER" su - db2inst1 -c "
db2 connect to $DB >/dev/null
P=\$(cat /tmp/ndl_pattern.txt)
db2 -x \"SELECT HEX(EXECUTABLE_ID), NUM_EXECUTIONS, VARCHAR(STMT_TEXT, 300) FROM TABLE(MON_GET_PKG_CACHE_STMT('D', NULL, NULL, -2)) AS T WHERE STMT_TEXT LIKE '\$P' AND STMT_TEXT NOT LIKE '%MON_GET_PKG_CACHE_STMT%' ORDER BY NUM_EXECUTIONS DESC\" > /tmp/ndl_ids.txt
cat /tmp/ndl_ids.txt
i=0
while read -r hexid nexec rest; do
  [ -z \"\$hexid\" ] && continue
  i=\$((i+1))
  db2 \"CALL EXPLAIN_FROM_SECTION(x'\$hexid', 'M', NULL, -1, 'DB2INST1', ?, ?, ?, ?, ?)\" >/dev/null
  echo \"== section \$i executable_id=\$hexid num_executions=\$nexec\" > /tmp/ndl_sec_\$i.txt
  db2exfmt -d $DB -1 -t >> /tmp/ndl_sec_\$i.txt 2>&1
done < /tmp/ndl_ids.txt
db2 connect reset >/dev/null
"
for f in $(docker exec "$CONTAINER" sh -c 'ls /tmp/ndl_sec_*.txt 2>/dev/null'); do
  base=$(basename "$f" .txt)
  docker exec "$CONTAINER" cat "$f" > "${OUT}_${base#ndl_}.txt"
  docker exec "$CONTAINER" rm -f "$f"
  echo "wrote ${OUT}_${base#ndl_}.txt"
done
