#!/usr/bin/env bash
# Fix for a Db2 Community container quirk seen after the container (or WSL / Docker) restarts:
#   DBI20187E The fencedid file ".../sqllib/adm/fencedid" is invalid because it is not owned by root:db2iadm1
# The image's own setup chowns that file to root:root after a good start, and the next start then refuses it,
# so the container restarts in a loop. Data is not affected. Run once (needs root for the Docker volume):
#   sudo bash scripts/fix_db2_restart.sh
set -euo pipefail
CONTAINER="${1:-hotelops-db2}"
VOLUME="${2:-hotelops_db2data}"
SRC=$(docker volume inspect -f '{{.Mountpoint}}' "$VOLUME")
INSTANCE="${DB2_USER:-db2inst1}"
FILE="$SRC/config/$INSTANCE/sqllib/adm/fencedid"
docker stop -t 5 "$CONTAINER" >/dev/null 2>&1 || true
chown 0:1000 "$FILE"    # root:db2iadm1 (gid 1000 inside the Db2 image)
docker start "$CONTAINER" >/dev/null
echo "Fixed $FILE. Db2 is starting: docker logs -f $CONTAINER  (wait for 'Setup has completed')"
