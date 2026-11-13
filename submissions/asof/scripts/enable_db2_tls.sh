#!/usr/bin/env bash
# Turns on TLS in the local AsOf Db2 container, so DB2_SSL=true can be tried and tested on one machine.
# A remote Db2 such as Db2 on Cloud serves TLS already and needs none of this: see README, "TLS to Db2".
#
#   scripts/enable_db2_tls.sh            # then, in .env: DB2_SSL=true  DB2_PORT=50001
#                                        #                DB2_SSL_SERVER_CERT=var/tls/db2-server.arm
#
# What it does, idempotently:
# 1. Installs libicu in the container (Db2 12.1's GSKit 9 tool needs it; IBM's image lacks it). This lives in
#    the container layer, like the OS users, so run the script again after the container is recreated.
# 2. As db2inst1: a CMS key database with a GSKit-generated password that only the stash file holds (never
#    printed), and a self-signed RSA 2048 / SHA-256 certificate for localhost and 127.0.0.1, valid 365 days.
#    Both live under the instance home on the data volume, so they survive a container rebuild.
# 3. Points Db2 at them (SSL_SVR_KEYDB, SSL_SVR_STASH, SSL_SVR_LABEL), listens for TLS on 50001
#    (SSL_SVCENAME), sets DB2COMM=SSL,TCPIP and restarts the instance. Plain TCP on 50000 keeps working.
# 4. Copies the public certificate out to var/tls/db2-server.arm, which the client pins.
#
# docker-compose.yml publishes 50001 on 127.0.0.1 only, as it does 50000.
set -euo pipefail
cd "$(dirname "$0")/.."

# The container: DB2_CONTAINER from the environment, else from .env, else asof-db2 (the Compose service).
container="${DB2_CONTAINER:-}"
if [ -z "$container" ] && [ -f .env ]; then
  container="$(grep -E '^DB2_CONTAINER=' .env | tail -1 | cut -d= -f2- || true)"
fi
container="${container:-asof-db2}"
if ! [[ "$container" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$ ]]; then
  echo "DB2_CONTAINER is not a valid container name" >&2; exit 2
fi
docker inspect "$container" >/dev/null 2>&1 || { echo "No container named $container. Start Db2 first: docker compose up -d --wait db2" >&2; exit 2; }

echo "1/4 GSKit dependencies"
docker exec -u root "$container" bash -c 'rpm -q libicu >/dev/null 2>&1 || dnf -y -q install libicu >/dev/null'

echo "2/4 Key database and self-signed certificate (password generated and stashed by GSKit, not shown)"
docker exec -u db2inst1 "$container" bash -lc '
set -euo pipefail
d="$HOME/asof-tls"; mkdir -p "$d"; chmod 700 "$d"; cd "$d"
if [ ! -f server.kdb ]; then
  gsk9certutil_64 -keydb -create -db server.kdb -type cms -stash -genpw >/dev/null
  gsk9certutil_64 -cert -create -db server.kdb -stashed -label asof -dn "CN=localhost,O=AsOf demo" \
    -san_dnsname localhost -san_ipaddr 127.0.0.1 -size 2048 -sigalg SHA256WithRSA -expire 365 >/dev/null
fi
gsk9certutil_64 -cert -extract -db server.kdb -stashed -label asof -target server.arm -format ascii -f >/dev/null
chmod 600 server.kdb server.sth'

echo "3/4 Db2 configuration and restart (TLS on port 50001, TCP stays on 50000)"
docker exec -u db2inst1 "$container" bash -lc '
set -euo pipefail
d="$HOME/asof-tls"
db2 update dbm cfg using SSL_SVR_KEYDB "$d/server.kdb" SSL_SVR_STASH "$d/server.sth" SSL_SVR_LABEL asof SSL_SVCENAME 50001 >/dev/null
db2set DB2COMM=SSL,TCPIP
db2stop force >/dev/null 2>&1 || true
db2start'

echo "4/4 Public certificate for the client"
mkdir -p var/tls
docker cp "$container:/database/config/db2inst1/asof-tls/server.arm" var/tls/db2-server.arm >/dev/null
echo "  var/tls/db2-server.arm (public certificate; var/ is not committed)"
echo "Done. To connect over TLS, set in .env: DB2_SSL=true, DB2_PORT=50001, DB2_SSL_SERVER_CERT=var/tls/db2-server.arm"
