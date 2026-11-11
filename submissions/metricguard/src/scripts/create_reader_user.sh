#!/usr/bin/env bash
# Create a least-privilege OS account that Db2 authenticates (local Community Edition container only;
# Db2 uses OS authentication there).
#   bash scripts/create_reader_user.sh          -> DB2_READER_USER (SELECT on analytical tables)
#   bash scripts/create_reader_user.sh audit    -> DB2_AUDIT_USER  (INSERT + SELECT on QUERY_AUDIT_LOG)
# Grants are applied by `metricguard db init` / `metricguard db migrate`, never by this script.
# For IBM Cloud Db2, create the users in the console instead and set DB2_READER_* / DB2_AUDIT_* in .env.
set -euo pipefail

cd "$(dirname "$0")/.."
CONTAINER="${DB2_CONTAINER:-metricguard-db2}"
ROLE="${1:-reader}"
case "${ROLE}" in
  reader) PREFIX="DB2_READER" ;;
  audit)  PREFIX="DB2_AUDIT" ;;
  *) echo "usage: $0 [reader|audit]" >&2; exit 2 ;;
esac
USER_NAME="$(grep -E "^${PREFIX}_USER=" .env | cut -d= -f2-)"
USER_PASS="$(grep -E "^${PREFIX}_PASSWORD=" .env | cut -d= -f2-)"

if [[ -z "${USER_NAME}" || -z "${USER_PASS}" ]]; then
  echo "${PREFIX}_USER / ${PREFIX}_PASSWORD must be set in .env" >&2
  exit 1
fi

if docker exec "${CONTAINER}" id "${USER_NAME}" >/dev/null 2>&1; then
  echo "OS user ${USER_NAME} already exists in ${CONTAINER}; updating password."
else
  docker exec "${CONTAINER}" useradd --no-create-home --shell /sbin/nologin "${USER_NAME}"
  echo "Created OS user ${USER_NAME} in ${CONTAINER}."
fi
# Password is passed on stdin, never on the command line.
printf '%s:%s\n' "${USER_NAME}" "${USER_PASS}" | docker exec -i "${CONTAINER}" chpasswd
echo "Done. Run 'make db-migrate' (existing database) or 'make db-init' to apply the grants."
