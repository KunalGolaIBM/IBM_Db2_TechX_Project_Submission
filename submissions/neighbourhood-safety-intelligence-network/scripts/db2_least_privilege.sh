#!/usr/bin/env bash
# Create the least-privilege Db2 login "nsinapp" inside the Db2 Community Edition container and
# grant it the NSIN_APP role (data access only). Run from the submission folder after the stack
# has started once as db2inst1 (which creates the tables):
#
#   NSIN_APP_PASSWORD='choose-a-strong-password' ./scripts/db2_least_privilege.sh
#
# Then restart the backend with DB2_USER=nsinapp, DB2_PASSWORD=<that password>, DB2_SCHEMA=DB2INST1.
set -euo pipefail

CONTAINER="${DB2_CONTAINER:-nsin_db2}"
: "${NSIN_APP_PASSWORD:?Set NSIN_APP_PASSWORD to the password for the nsinapp login}"
cd "$(dirname "$0")/.."

echo "Creating OS login nsinapp in $CONTAINER (Db2 authenticates operating-system users)..."
docker exec "$CONTAINER" bash -c 'id nsinapp >/dev/null 2>&1 || useradd -M -s /sbin/nologin nsinapp'
printf 'nsinapp:%s\n' "$NSIN_APP_PASSWORD" | docker exec -i "$CONTAINER" chpasswd

echo "Applying db/least_privilege.sql as db2inst1..."
docker cp db/least_privilege.sql "$CONTAINER":/tmp/least_privilege.sql
# CREATE ROLE fails harmlessly when the script is re-run, so do not stop on individual statement errors.
docker exec "$CONTAINER" su - db2inst1 -c "db2 connect to NSIN > /dev/null && db2 -tvf /tmp/least_privilege.sql" || true

echo "Effective table privileges of role NSIN_APP:"
docker exec "$CONTAINER" su - db2inst1 -c "db2 connect to NSIN > /dev/null && db2 \"SELECT VARCHAR(TABNAME, 24) AS TABLE, SELECTAUTH AS SEL, INSERTAUTH AS INS, UPDATEAUTH AS UPD, DELETEAUTH AS DEL FROM SYSCAT.TABAUTH WHERE GRANTEE = 'NSIN_APP' ORDER BY TABNAME\""
