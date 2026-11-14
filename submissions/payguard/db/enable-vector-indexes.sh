#!/usr/bin/env bash
# Run inside the Db2 Community Edition container as root after its first setup:
# docker exec payguard-db2 bash /var/custom/enable-vector-indexes.sh
set -euo pipefail
su - db2inst1 -c 'db2set DB2_VECTOR_INDEXING=YES; db2stop force; db2start'
