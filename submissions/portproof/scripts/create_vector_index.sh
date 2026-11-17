#!/usr/bin/env bash
# Build Db2's approximate vector index over PortProof's fix memory.
#
#   bash scripts/create_vector_index.sh [container] [database]
#
# Run this once, AFTER `python -m src.setup_db` has created the FIX_MEMORY
# table. It is optional: PortProof's recall is correct without it and simply
# distances every row instead of consulting an index.
#
# Why it is a separate script, run as the instance owner, rather than part of
# setup_db. Two things were measured on Db2 Community Edition 12.1.5.0:
#
#   1. CREATE VECTOR INDEX on a VECTOR(384, FLOAT32) column fails in a 4K page
#      tablespace with SQL0614N, "the combined length of the specified columns
#      is too long". 4K pages cap an index key at 1024 bytes; 384 FLOAT32
#      values are 1536. scripts/create_db2_users.sh therefore creates a 32K
#      tablespace called PPVEC, and src/fixmemory.py places FIX_MEMORY in it.
#
#   2. Even in PPVEC, the statement fails for PortProof's schema owner with
#      SQL0551N: "Authorization ID PPOWN. Operation: CREATE TABLE. Object:
#      SYSIBM.AGT...". Building the index implicitly creates a helper table in
#      the SYSIBM schema, which the deliberately-not-DBADM owner cannot write
#      to. So the index is created by the instance owner here, once, rather
#      than by granting the application's own identity far more than it needs
#      for the rest of its life.
set -euo pipefail

CONTAINER="${1:-db2spike}"
DATABASE="${2:-testdb}"

echo "==> creating the vector index in '${DATABASE}'"
docker exec -u db2inst1 "${CONTAINER}" bash -lc "
  db2 connect to ${DATABASE} >/dev/null

  db2 -x \"CREATE VECTOR INDEX PORTPROOF.IX_FIX_MEMORY_VEC
             ON PORTPROOF.FIX_MEMORY (EMBEDDING) WITH DISTANCE COSINE\" || true

  # INDEXTYPE 'VANN' is an approximate nearest neighbour index. If this prints
  # only the primary key, the index was not created and the reason is above.
  db2 -x \"SELECT INDNAME, INDEXTYPE FROM SYSCAT.INDEXES
            WHERE TABSCHEMA = 'PORTPROOF' AND TABNAME = 'FIX_MEMORY'\"
"

echo
echo "The distance metric must match the queries (COSINE). Verify the engine"
echo "will use it with:  python -m src.main --ledger"
