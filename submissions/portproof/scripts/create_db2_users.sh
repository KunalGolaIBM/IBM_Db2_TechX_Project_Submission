#!/usr/bin/env bash
# Create PortProof's two Db2 identities inside a Db2 Community Edition container.
#
#   bash scripts/create_db2_users.sh [container] [database]
#
# Db2 LUW authenticates against operating-system users, so the accounts are
# created in the container and then granted database authorities. Run this once,
# then put the same passwords in your .env.
#
# Why two users (this is the point of the exercise):
#   ppown  -- owns the schema. CREATETAB + IMPLICIT_SCHEMA, so it can build the
#             ledger and the throwaway adversarial fixtures. Deliberately NOT
#             DBADM.
#   ppapp  -- what the application actually runs as. It may SELECT the ledger
#             and CALL three procedures. It cannot INSERT, UPDATE or DELETE any
#             table directly, and it cannot create anything.
set -euo pipefail

CONTAINER="${1:-db2spike}"
DATABASE="${2:-testdb}"

# Passwords are supplied by the environment and have no defaults on purpose.
# A default here would be a credential committed to the repository, and it would
# be a *working* one for anyone who ran the script unchanged.
#
#   PORTPROOF_APP_PASSWORD=... PORTPROOF_OWN_PASSWORD=... bash scripts/create_db2_users.sh
#
# Or let the script generate two strong ones and print them once, below.
APP_PASSWORD="${PORTPROOF_APP_PASSWORD:-}"
OWN_PASSWORD="${PORTPROOF_OWN_PASSWORD:-}"

generate() {
  # Db2 on Linux authenticates against OS users, so keep to characters that are
  # safe in a shell, in chpasswd and in a CLI connection string.
  LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 20
}

if [ -z "${APP_PASSWORD}" ] || [ -z "${OWN_PASSWORD}" ]; then
  echo "==> no passwords supplied; generating two strong ones"
  APP_PASSWORD="$(generate)"
  OWN_PASSWORD="$(generate)"
  GENERATED=1
fi

echo "==> creating OS users in container '${CONTAINER}'"
docker exec -u root "${CONTAINER}" bash -c "
  id ppapp >/dev/null 2>&1 || useradd ppapp
  id ppown >/dev/null 2>&1 || useradd ppown
  echo 'ppapp:${APP_PASSWORD}' | chpasswd
  echo 'ppown:${OWN_PASSWORD}' | chpasswd
"

echo "==> granting database authorities in '${DATABASE}'"
docker exec -u db2inst1 "${CONTAINER}" bash -lc "
  db2 connect to ${DATABASE} >/dev/null

  # The owner: enough to build the schema, and no more.
  db2 -x \"GRANT CONNECT, CREATETAB, IMPLICIT_SCHEMA ON DATABASE TO USER PPOWN\"
  db2 -x \"GRANT USE OF TABLESPACE USERSPACE1 TO USER PPOWN\"

  # Optional: lets setup_db.py install the WLM leash on the prover's queries.
  # Without it PortProof still works; the leash is simply skipped.
  db2 -x \"GRANT WLMADM ON DATABASE TO USER PPOWN\" || true

  # The two monitoring routines behind 'measured, not guessed' physical advice.
  # Granting EXECUTE on exactly these two is far narrower than the DBADM that
  # most tutorials reach for, and without them --physical degrades honestly to
  # 'not measurable (SQLCODE=-551)' rather than inventing a number.
  # ADMIN_GET_TAB_COMPRESS_INFO is overloaded, so an unqualified GRANT fails with
  # SQL0476N; SPECIFIC FUNCTION names each signature instead.
  db2 -x \"GRANT EXECUTE ON SPECIFIC FUNCTION SYSPROC.ADMIN_GET_TAB_COMPRESS_INFO TO USER PPOWN\" || true
  db2 -x \"GRANT EXECUTE ON SPECIFIC FUNCTION SYSPROC.ADMIN_GET_TAB_COMPRESS_INFO_V10 TO USER PPOWN\" || true
  db2 -x \"GRANT EXECUTE ON FUNCTION SYSPROC.MON_GET_PKG_CACHE_STMT TO USER PPOWN\" || true

  # The runtime user: connect only. Table and procedure rights are granted by
  # sql/03_grants.sql, object by object.
  db2 -x \"GRANT CONNECT ON DATABASE TO USER PPAPP\"

  db2 -x \"CREATE SCHEMA PORTPROOF AUTHORIZATION PPOWN\" || true
  db2 -x \"GRANT CREATEIN, ALTERIN, DROPIN ON SCHEMA PORTPROOF TO USER PPOWN\"

  # A 32K-page tablespace, so the fix memory can carry a vector INDEX and not
  # only a vector column.
  #
  # Measured on CE 12.1.5: 'CREATE VECTOR INDEX ... WITH DISTANCE COSINE' on a
  # VECTOR(384, FLOAT32) column fails with SQL0614N -- 'the combined length of
  # the specified columns is too long' -- in USERSPACE1, because that has 4K
  # pages and therefore a 1024-byte index key limit, while 384 FLOAT32 values
  # are 1536 bytes. In a 32K-page tablespace the limit is 8192 and the index
  # builds (SYSCAT.INDEXES.INDEXTYPE = 'VANN').
  #
  # CREATE BUFFERPOOL needs an authority the least-privilege users deliberately
  # do not have, which is why it is here, run by the instance owner, and why
  # PortProof degrades to exact vector search rather than requiring it.
  db2 -x \"CREATE BUFFERPOOL BP32K IMMEDIATE SIZE 1000 PAGESIZE 32K\" || true
  db2 -x \"CREATE LARGE TABLESPACE PPVEC PAGESIZE 32K MANAGED BY AUTOMATIC STORAGE BUFFERPOOL BP32K\" || true
  db2 -x \"GRANT USE OF TABLESPACE PPVEC TO USER PPOWN\" || true

  db2 -x \"SELECT GRANTEE, CREATETABAUTH, IMPLSCHEMAAUTH FROM SYSCAT.DBAUTH WHERE GRANTEE IN ('PPOWN','PPAPP')\"
"

cat <<EOF

==> done. Put these in your .env (which is git-ignored -- never commit it):

  DB2_USER=ppapp
  DB2_PASSWORD=${APP_PASSWORD}
  DB2_SETUP_USER=ppown
  DB2_SETUP_PASSWORD=${OWN_PASSWORD}

EOF

if [ "${GENERATED:-0}" = "1" ]; then
  cat <<'EOF'
These were generated just now and are printed only this once. Copy them into
.env before you close this terminal; the script keeps no record of them.

EOF
fi

echo "Next:  python -m src.setup_db"
