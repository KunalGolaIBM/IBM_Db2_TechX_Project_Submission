#!/usr/bin/env bash
# NEEDLE: create the Db2 database and apply the SQL files in sql/ in order.
#
# Runs on the Docker host (Linux/macOS, or Git Bash). It talks to the Db2 container with `docker exec`
# as the instance owner, so it needs no Db2 password. It never prints a password.
#
# Usage:
#   bash scripts/setup_db.sh                  # wait for Db2, create VECDB (32K pages), apply PRE-load SQL
#   bash scripts/setup_db.sh --with-users     # also create the NEEDLE analyst Linux users (passwords from .env)
#   bash scripts/setup_db.sh --phase post     # after the bulk load: vector index + RUNSTATS (POST-load SQL)
#   bash scripts/setup_db.sh --validate       # run sql/99_*.sql (validation queries) and print the output
#
# Environment (optional):
#   DB2_CONTAINER   container name (environment, else .env, else needle-db2; the NEEDLE Codespace container is "db2")
#   DB2_DATABASE    database name  (default: VECDB)
#   DB2INSTANCE     instance owner (default: db2inst1)
#   WAIT_MINUTES    how long to wait for the image setup to finish (default: 30)
#
# SQL file conventions (sql/NN_name.sql, applied in file-name order):
#   - Statements end with ';'. A SQL PL file starts with the CLP directive  --#SET TERMINATOR @
#   - A line  -- @POST_LOAD  splits a file: the part before runs in phase "pre", the part after in phase "post".
#   - Files named 99_*.sql run only with --validate.
#   - Re-runs are allowed: SQL0601N (object exists), SQL0623N, SQL0624N, SQL0605W, SQL0556N are reported as
#     "already applied".

set -euo pipefail
export MSYS_NO_PATHCONV=1   # Git Bash on Windows: do not rewrite container paths such as /tmp/...

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SQL_DIR="$ROOT/sql"
ENV_FILE="$ROOT/.env"
LOG_DIR="$ROOT/data/logs"

CONTAINER=""   # set below: DB2_CONTAINER from the environment, else from .env, else needle-db2
DB="${DB2_DATABASE:-VECDB}"
INST="${DB2INSTANCE:-db2inst1}"
WAIT_MINUTES="${WAIT_MINUTES:-30}"
MARKER="/database/config/.shared-data/setup_complete"
# SQL0623N: clustering index already exists. SQL0556N: REVOKE of a privilege the user does not hold (04_rcac.sql
# revokes grants of earlier runs; on a new database nothing is held, so the end state is already reached).
ALLOWED_CODES_RE='^(SQL0601N|SQL0623N|SQL0624N|SQL0605W|SQL0556N)$'

PHASE="pre"
WITH_USERS=0
VALIDATE=0

usage() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase) PHASE="${2:-}"; shift 2 ;;
    --with-users) WITH_USERS=1; shift ;;
    --validate) VALIDATE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done
if [[ "$PHASE" != "pre" && "$PHASE" != "post" ]]; then
  echo "--phase must be 'pre' or 'post'" >&2; exit 2
fi
if [[ ! "$DB" =~ ^[A-Za-z][A-Za-z0-9]{0,7}$ ]]; then
  echo "DB2_DATABASE must be 1-8 letters/digits" >&2; exit 2
fi

log() { printf '[setup_db %s] %s\n' "$(date +%H:%M:%S)" "$*"; }

# Run a command as the instance owner inside the container.
db2x() { docker exec -i "$CONTAINER" su - "$INST" -c "$1"; }

# Read one key from the environment, else from .env, without printing it.
env_get() {
  local key="$1" val=""
  val="${!key:-}"
  if [[ -z "$val" && -f "$ENV_FILE" ]]; then
    val="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | tr -d '\r')"
    val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
  fi
  printf '%s' "$val"
}

CONTAINER="$(env_get DB2_CONTAINER)"; CONTAINER="${CONTAINER:-needle-db2}"

# ---------------------------------------------------------------------------------------------
# 1. Container and image setup
# ---------------------------------------------------------------------------------------------
if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "Container '$CONTAINER' not found. Start it with 'docker compose up -d' or set DB2_CONTAINER." >&2
  exit 1
fi

log "Waiting for the Db2 image setup to finish (marker $MARKER, up to ${WAIT_MINUTES} min)..."
deadline=$(( $(date +%s) + WAIT_MINUTES * 60 ))
until docker exec "$CONTAINER" test -f "$MARKER"; do
  if (( $(date +%s) > deadline )); then
    echo "Db2 setup did not finish in ${WAIT_MINUTES} min. Check: docker logs $CONTAINER" >&2
    exit 1
  fi
  sleep 15
done
log "Db2 image setup is complete."
db2x "db2level" | grep -E "DB2 v|Informational tokens" || true

# ---------------------------------------------------------------------------------------------
# 2. Database with 32K pages (a 768-dim FLOAT32 vector index key needs a 16K or 32K page)
# ---------------------------------------------------------------------------------------------
# No "cmd | grep -q" under pipefail: grep -q exits at the first match, the writer can die of SIGPIPE (141)
# and the whole test reads as false. Capture first, then match.
dbdir="$(db2x "db2 list database directory" || true)"
if grep -qiE "Database name[[:space:]]*=[[:space:]]*${DB}[[:space:]]*$" <<<"$dbdir"; then
  log "Database $DB already exists."
else
  log "Creating database $DB with PAGESIZE 32 K (this can take several minutes)..."
  db2x "db2 create database $DB pagesize 32 K"
  # Larger transaction log, set only on a new (not yet active) database. With the default 25 x 4 MB, a reload of
  # NEEDLE.POSTING with its indexes in place stopped at 1.4M rows: SQL1476N / -964, db2diag ADM1822W "active
  # transaction log is being held by dirty pages" (docs/evidence/bootstrap_test.md).
  db2x "db2 update db cfg for $DB using LOGFILSIZ 16384 LOGPRIMARY 10 LOGSECOND 30"
fi

pagesize="$(db2x "db2 connect to $DB >/dev/null && db2 -x \"SELECT PAGESIZE FROM SYSCAT.TABLESPACES WHERE TBSPACE = 'USERSPACE1'\"; db2 connect reset >/dev/null" | tr -d '[:space:]')"
if [[ "$pagesize" != "32768" ]]; then
  echo "USERSPACE1 page size is '$pagesize', expected 32768. Recreate $DB with PAGESIZE 32 K." >&2
  exit 1
fi
log "USERSPACE1 page size = 32768."

# EXPLAIN tables (needed for the access-path evidence). Existing tables are left as they are.
db2x "db2 connect to $DB >/dev/null && db2 \"CALL SYSPROC.SYSINSTALLOBJECTS('EXPLAIN', 'C', CAST(NULL AS VARCHAR(128)), CAST(NULL AS VARCHAR(128)))\" >/dev/null; db2 connect reset >/dev/null" \
  && log "EXPLAIN tables present." || log "EXPLAIN tables: create call returned non-zero (they may already exist)."

# ---------------------------------------------------------------------------------------------
# 3. Optional: analyst users (Linux users in the container; Db2 AUTHENTICATION = SERVER)
# ---------------------------------------------------------------------------------------------
if (( WITH_USERS )); then
  # Same convention as scripts/rcac_users.sh: key NDL_<ROLE>_PASSWORD -> Linux user ndl_<role>.
  for role in SENIOR JUNIOR P10 P25 P50 P75; do
    u="ndl_$(printf '%s' "$role" | tr '[:upper:]' '[:lower:]')"
    key="NDL_${role}_PASSWORD"
    pw="$(env_get "$key")"
    if [[ -z "$pw" || "$pw" == change_me* ]]; then
      echo "Set $key in .env (not a change_me placeholder) before --with-users." >&2
      exit 1
    fi
    docker exec "$CONTAINER" bash -c "id -u $u >/dev/null 2>&1 || useradd -M $u"
    # The password goes through stdin (printf is a shell builtin), never through a process argument.
    printf '%s:%s\n' "$u" "$pw" | docker exec -i "$CONTAINER" chpasswd
    unset pw
    log "User $u ready (Db2 authorization ID $(printf '%s' "$u" | tr '[:lower:]' '[:upper:]'))."
  done
fi

# ---------------------------------------------------------------------------------------------
# 4. SQL files
# ---------------------------------------------------------------------------------------------
shopt -s nullglob
files=( "$SQL_DIR"/*.sql )
shopt -u nullglob
if (( ${#files[@]} == 0 )); then
  log "No SQL files in $SQL_DIR. Nothing to apply."
  exit 0
fi

mkdir -p "$LOG_DIR"
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT

if (( VALIDATE )); then
  mode="validate"
else
  mode="$PHASE"
fi

selected=()
for f in $(printf '%s\n' "${files[@]}" | sort); do
  base="$(basename "$f")"
  if [[ "$mode" == "validate" ]]; then
    [[ "$base" == 99_* ]] || continue
    cp "$f" "$stage/$base"
  else
    [[ "$base" == 99_* ]] && continue
    if [[ "$mode" == "pre" ]]; then
      awk '/^[[:space:]]*--[[:space:]]*@POST_LOAD/{exit} {print}' "$f" > "$stage/$base"
    else
      awk 'found{print} /^[[:space:]]*--[[:space:]]*@POST_LOAD/{found=1}' "$f" > "$stage/$base"
    fi
    # Keep a SQL PL terminator directive for the post part too.
    if [[ "$mode" == "post" ]] && grep -q '^--#SET TERMINATOR' <(head -n 5 "$f"); then
      { head -n 5 "$f" | grep '^--#SET TERMINATOR'; cat "$stage/$base"; } > "$stage/$base.tmp" && mv "$stage/$base.tmp" "$stage/$base"
    fi
  fi
  # Skip files whose selected part holds no SQL (only comments and blank lines). One grep, no pipe: a
  # "grep -v ... | grep -q ." pipeline under pipefail returned 141 (SIGPIPE) and skipped 03_triage_proc.sql.
  if grep -qvE '^[[:space:]]*(--.*)?$' "$stage/$base"; then
    selected+=( "$base" )
  else
    rm -f "$stage/$base"
  fi
done

if (( ${#selected[@]} == 0 )); then
  log "No SQL to run for mode '$mode'."
  exit 0
fi

if [[ "$mode" == "post" ]]; then
  # Static SQL in SQL procedures (the MERGE in NEEDLE.SYNC_POSTING_ACL) is bound when the procedure is created in
  # the pre phase, on EMPTY tables. That plan read about 19 billion rows on the full corpus (docs/evidence/
  # bootstrap_test.md). Rebind after the load, so the optimizer uses the loaders' RUNSTATS statistics.
  docker exec -i "$CONTAINER" su - "$INST" -c "bash -s -- $DB" <<'EOS' || log "rebind of NEEDLE procedures returned non-zero"
db2 connect to "$1" >/dev/null || exit 1
for p in $(db2 -x "SELECT RTRIM(ROUTINESCHEMA) || '.' || RTRIM(ROUTINENAME) FROM SYSCAT.ROUTINES WHERE ROUTINESCHEMA = 'NEEDLE' AND ROUTINETYPE = 'P' AND ORIGIN = 'Q'"); do
  if db2 "CALL SYSPROC.REBIND_ROUTINE_PACKAGE('P', '$p', 'ANY')" >/dev/null; then echo "  rebound $p"; else echo "  rebind failed: $p"; fi
done
db2 connect reset >/dev/null
EOS
fi

remote="/tmp/needle_sql_${mode}"
docker exec "$CONTAINER" rm -rf "$remote"
docker cp "$stage" "$CONTAINER:$remote"
docker exec "$CONTAINER" chmod -R a+rX "$remote"

failed=0
for base in "${selected[@]}"; do
  logfile="$LOG_DIR/setup_${mode}_${base%.sql}_$(date +%Y%m%d_%H%M%S).log"
  log "Applying $base ($mode) -> $logfile"
  set +e
  db2x "db2 connect to $DB >/dev/null && db2 -tv -f $remote/$base; rc=\$?; db2 connect reset >/dev/null; exit \$rc" > "$logfile" 2>&1
  set -e
  codes="$(grep -oE 'SQL[0-9]{4,5}[NW]' "$logfile" | sort -u || true)"
  bad=""
  for c in $codes; do
    if [[ "$c" =~ $ALLOWED_CODES_RE ]]; then
      log "  $c reported (treated as already applied)."
    elif [[ "$c" == *W ]]; then
      log "  warning $c (see log)."
    else
      bad+="$c "
    fi
  done
  if [[ -n "$bad" ]]; then
    log "  ERROR in $base: $bad(see $logfile)"
    failed=1
  else
    log "  OK"
  fi
  if [[ "$mode" == "validate" ]]; then
    cat "$logfile"
  fi
done

docker exec "$CONTAINER" rm -rf "$remote"

if (( failed )); then
  log "Finished with errors."
  exit 1
fi
log "Finished: database $DB, mode $mode, ${#selected[@]} file(s)."
