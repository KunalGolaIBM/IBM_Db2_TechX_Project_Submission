#!/usr/bin/env bash
# Teach Db2 to read the source engines directly, through federation.
#
#   bash scripts/create_federation.sh [db2_container] [database] [pg_container] [mysql_container]
#
# This is optional. PortProof proves equivalence without it. What federation
# buys is a second, independent opinion on *why* two engines disagreed: with
# nicknames in place, Db2 itself can compare the source rows against the rows
# PortProof loaded into Db2, inside a single statement, so a divergence can be
# split into "the data arrived differently" and "the query means something
# different". See src/federation.py for how that is used.
#
# Why it is run as the instance owner rather than by setup_db: CREATE WRAPPER
# and CREATE SERVER need DBADM, and PortProof's schema owner is deliberately
# not DBADM. The nicknames are then granted to the application identity, which
# only ever reads them.
#
# Four things were measured on Db2 Community Edition 12.1.5.0 and are worth
# knowing before anyone repeats this:
#
#   1. CREATE WRAPPER JDBC with no LIBRARY clause works and resolves to
#      libdb2rcjdbc.so. Naming libdb2qgjava.so instead fails with SQL1883N,
#      "UNFENCED_WRAPPER_CLASS is a required WRAPPER option": that library is
#      the wrapper SDK, for wrappers you write yourself, not a ready driver.
#
#   2. The server options HOST, PORT and DBNAME are rejected for this wrapper
#      with SQL1881N. URL is the only way to say where the source is.
#
#   3. Db2 ships its own JDBC drivers in federation/jdbc/lib, and defaults
#      DRIVER_CLASS to com.ibm.fluidquery.jdbc.<type>.<Type>Driver. Those are
#      DataDirect drivers, so they want a DataDirect URL,
#      jdbc:ibm:postgresql://host:port;DatabaseName=db. Handing them an
#      ordinary jdbc:postgresql:// URL fails with SQL1336N, "the remote host
#      'unknown' was not found", which reads like a DNS problem and is not one.
#      DRIVER_PACKAGE must be an absolute path; a bare file name fails with
#      "FOpostgresql.jar is not accessible!".
#
#   4. The bundled MySQL driver refuses MySQL Community Server outright:
#      SQL1822N, "[IBM][MySQL JDBC Driver]Connections to MySQL Community
#      Server...". That is a licence restriction in the driver, not a Db2
#      limitation, and the fix is to point DRIVER_PACKAGE and DRIVER_CLASS at
#      Oracle's own Connector/J. This script does that when it finds the jar,
#      and says so plainly when it does not.
set -euo pipefail

CONTAINER="${1:-db2spike}"
DATABASE="${2:-testdb}"
PG_CONTAINER="${3:-pppg}"
MYSQL_CONTAINER="${4:-ppmysql}"

FEDLIB="/opt/ibm/db2/V12.1/federation/jdbc/lib"
MYSQL_JAR="${FEDLIB}/mysql-connector-j.jar"

: "${PG_PASSWORD:?set PG_PASSWORD (it is read from the environment, never stored in this file)}"
: "${MYSQL_PASSWORD:?set MYSQL_PASSWORD (it is read from the environment, never stored in this file)}"

PG_USER="${PG_USER:-postgres}"
PG_DATABASE="${PG_DATABASE:-pptest}"
MYSQL_USER="${MYSQL_USER:-root}"
MYSQL_DATABASE="${MYSQL_DATABASE:-pptest}"

# The Db2 identities that will read the nicknames. Each needs a user mapping,
# because without one Db2 sends the local authid and password to the remote,
# which fails with SQL1101N for MySQL and 28P01 for PostgreSQL and reads like a
# mystery until you know that is what it is doing.
DB2_IDENTITIES="DB2INST1 ${DB2_SETUP_USER:-ppown} ${DB2_USER:-ppapp}"

# A user mapping stores a remote password in the Db2 catalogue. The admin
# accounts in .env must therefore not be the ones mapped: they can write, and a
# federated reader never needs to. So the script mints a read-only account on
# each source engine, with a fresh password it never writes to disk, and maps
# the Db2 identities to that instead.
PP_FED_USER="ppread"
PP_FED_PASSWORD="$(openssl rand -base64 24 | tr -d '/+=' | cut -c1-24)"

echo "==> checking that the instance is configured for federation"
docker exec -u db2inst1 "${CONTAINER}" bash -lc '
  db2 get dbm cfg | grep -i "(FEDERATED)"
'

echo "==> creating a read-only account on each source engine"
docker exec -e PGPASSWORD="${PG_PASSWORD}" "${PG_CONTAINER}" psql -U "${PG_USER}" \
  -d "${PG_DATABASE}" -v ON_ERROR_STOP=0 -q \
  -c "DROP OWNED BY ${PP_FED_USER}" \
  -c "DROP ROLE IF EXISTS ${PP_FED_USER}" \
  -c "CREATE ROLE ${PP_FED_USER} LOGIN PASSWORD '${PP_FED_PASSWORD}'" \
  -c "GRANT CONNECT ON DATABASE ${PG_DATABASE} TO ${PP_FED_USER}" \
  -c "GRANT USAGE ON SCHEMA public TO ${PP_FED_USER}" \
  -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO ${PP_FED_USER}" \
  -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO ${PP_FED_USER}" \
  2>&1 | grep -viE "^$|does not exist" || true
echo "    postgresql: ${PP_FED_USER} may SELECT and nothing else"

docker exec -e MYPW="${MYSQL_PASSWORD}" -e NEWPW="${PP_FED_PASSWORD}" \
  "${MYSQL_CONTAINER}" bash -lc "
  mysql -u '${MYSQL_USER}' -p\"\$MYPW\" -e \"
    DROP USER IF EXISTS '${PP_FED_USER}'@'%';
    CREATE USER '${PP_FED_USER}'@'%' IDENTIFIED BY '\$NEWPW';
    GRANT SELECT ON \\\`${MYSQL_DATABASE}\\\`.* TO '${PP_FED_USER}'@'%';
    FLUSH PRIVILEGES;\"
" 2>&1 | grep -vi "password on the command line" || true
echo "    mysql: ${PP_FED_USER} may SELECT and nothing else"

echo "==> finding the source engines from inside the Db2 container"
# The published host ports are irrelevant here: Db2 dials out from inside its
# own container, so it needs the address on the Docker network, and the
# engine's native port rather than the one mapped onto the host.
PG_HOST="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "${PG_CONTAINER}")"
MYSQL_HOST="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "${MYSQL_CONTAINER}")"
echo "    postgresql at ${PG_HOST}:5432, mysql at ${MYSQL_HOST}:3306"

echo "==> looking for Oracle Connector/J for MySQL"
# The test runs through `bash -lc` rather than as a bare argument because Git
# Bash on Windows rewrites a leading-slash argument into a Windows path, so
# `docker exec c test -f /opt/...` asks about C:/Program Files/Git/opt/...
# and always answers no. Inside a quoted shell string the path survives.
if docker exec "${CONTAINER}" bash -lc "test -f '${MYSQL_JAR}'"; then
  echo "    found ${MYSQL_JAR}"
else
  echo "    not present; trying to fetch it (needs network access from the container)"
  docker exec "${CONTAINER}" bash -lc "
    curl -fsS --max-time 90 -o '${MYSQL_JAR}' \
      https://repo1.maven.org/maven2/com/mysql/mysql-connector-j/8.4.0/mysql-connector-j-8.4.0.jar \
      && chmod 755 '${MYSQL_JAR}'
  " || echo "    could not fetch it; the MySQL server will be created but will not connect (see note 4)"
fi

echo "==> creating the wrapper, the servers, the user mappings and the nicknames"
docker exec -u db2inst1 \
  -e PP_FED_PASSWORD="${PP_FED_PASSWORD}" \
  "${CONTAINER}" bash -lc "
set -uo pipefail
db2 connect to ${DATABASE} >/dev/null

# Idempotent: a second run should be quiet, not noisy. Dropping a server drops
# its nicknames and user mappings with it.
for n in PG_CUSTOMERS PG_ORDERS PG_ORDER_ITEMS PG_EVENTS \
         MY_CUSTOMERS MY_ORDERS MY_ORDER_ITEMS MY_EVENTS; do
  db2 -x \"DROP NICKNAME \$n\" >/dev/null 2>&1 || true
done
db2 -x 'DROP SERVER PGSRV' >/dev/null 2>&1 || true
db2 -x 'DROP SERVER MYSRV' >/dev/null 2>&1 || true
db2 -x 'DROP WRAPPER JDBC' >/dev/null 2>&1 || true

db2 -x 'CREATE WRAPPER JDBC'

db2 -x \"CREATE SERVER PGSRV TYPE POSTGRESQL VERSION '17' WRAPPER JDBC
          OPTIONS (URL 'jdbc:ibm:postgresql://${PG_HOST}:5432;DatabaseName=${PG_DATABASE}',
                   DRIVER_PACKAGE '${FEDLIB}/FOpostgresql.jar')\"

db2 -x \"CREATE SERVER MYSRV TYPE MYSQL VERSION '8.4' WRAPPER JDBC
          OPTIONS (URL 'jdbc:mysql://${MYSQL_HOST}:3306/${MYSQL_DATABASE}',
                   DRIVER_PACKAGE '${MYSQL_JAR}',
                   DRIVER_CLASS 'com.mysql.cj.jdbc.Driver')\"

# The password is bound into the statement text here because Db2's CLP has no
# parameter markers. It comes from the environment, is never written to a file,
# and -x keeps it off the echoed output. Db2 encrypts it in SYSCAT.USEROPTIONS.
for id in ${DB2_IDENTITIES}; do
  up=\$(echo \$id | tr '[:lower:]' '[:upper:]')
  db2 -x \"CREATE USER MAPPING FOR \$up SERVER PGSRV
            OPTIONS (REMOTE_AUTHID '${PP_FED_USER}', REMOTE_PASSWORD '\$PP_FED_PASSWORD')\" >/dev/null
  db2 -x \"CREATE USER MAPPING FOR \$up SERVER MYSRV
            OPTIONS (REMOTE_AUTHID '${PP_FED_USER}', REMOTE_PASSWORD '\$PP_FED_PASSWORD')\" >/dev/null
  echo \"    \$up is mapped to the read-only remote account\"
done

for t in customers orders order_items events; do
  u=\$(echo \$t | tr '[:lower:]' '[:upper:]')
  db2 -x \"CREATE NICKNAME PG_\$u FOR PGSRV.\\\"public\\\".\\\"\$t\\\"\" >/dev/null \
    || echo \"    PG_\$u not created (the table may not exist in PostgreSQL yet)\"
  db2 -x \"CREATE NICKNAME MY_\$u FOR MYSRV.\\\"${MYSQL_DATABASE}\\\".\\\"\$t\\\"\" >/dev/null \
    || echo \"    MY_\$u not created (the table may not exist in MySQL yet)\"
  for id in ${DB2_IDENTITIES}; do
    db2 -x \"GRANT SELECT ON PG_\$u TO USER \$id\" >/dev/null 2>&1 || true
    db2 -x \"GRANT SELECT ON MY_\$u TO USER \$id\" >/dev/null 2>&1 || true
  done
done

echo
echo '    nicknames now defined:'
db2 -x \"SELECT TABNAME FROM SYSCAT.NICKNAMES ORDER BY TABNAME\"
"

echo
echo "Nicknames are created over whatever tables exist right now. PortProof"
echo "reloads the fixture tables on every run, so if a nickname is missing,"
echo "run one proof first and then run this script again."
echo
echo "Check it from Python with:  python -m src.main --federation"
