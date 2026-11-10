#!/usr/bin/env bash
# NEEDLE: one-command Db2 setup in a fresh GitHub Codespace (or any Linux x86-64 Docker host).
# Run from the needle/ folder. Re-runnable: finished steps are detected and skipped or repeated safely.
#
#   bash scripts/bootstrap_codespace.sh            # sample mode (default): 2,000 advisories from eval/fixtures, no Ollama
#   bash scripts/bootstrap_codespace.sh --full     # full corpus: GitHub release assets -> data/load (needs `gh` auth)
#
# Options:
#   --sample | --full     data to load (default --sample)
#   --data-dir DIR        keep the Db2 data in DIR (bind mount) instead of the named Docker volume. In a Codespace,
#                         /tmp is a separate large disk but may not survive a Codespace stop.
#   --reload              load the data even if NEEDLE.ADV_DOC and NEEDLE.POSTING already hold it
# Environment (optional): DB2_CONTAINER, DB2_PORT (written into .env), WAIT_MINUTES (default 30),
#   COMPOSE_PROJECT_NAME / COMPOSE_FILE (passed through to docker compose).
#
# Steps: 1 .env (random passwords, never printed, mode 600)  2 docker compose up + wait for Db2 setup
#        3 scripts/setup_db.sh --with-users  4 .venv + requirements  5 data load  6 fleet + post-load SQL
#        7 db2 activate database  8 smoke check  9 next steps for a laptop (copy .env, SSH tunnel)
set -euo pipefail

RELEASE_TAG="needle-data-2026-11-09"
RELEASE_REPO="wiiqz/IBM2026"
RELEASE_FILES=(docs.jsonl.gz emb.jsonl.gz raw.jsonl.gz postings.jsonl.gz corpus_stats.json eval_qvecs.json.gz)

MODE="sample"; DATA_DIR=""; RELOAD=0
usage() { sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; }
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sample) MODE="sample"; shift ;;
    --full) MODE="full"; shift ;;
    --data-dir) DATA_DIR="${2:?--data-dir needs a directory}"; shift 2 ;;
    --reload) RELOAD=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ -f docker-compose.yml && -f .env.example && -d sql ]] || { echo "Run from the needle/ folder." >&2; exit 2; }
mkdir -p data/logs
LOG="data/logs/bootstrap_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1
T0=$(date +%s)
step() { printf '\n=== [%s, t+%ss] %s\n' "$(date +%H:%M:%S)" "$(( $(date +%s) - T0 ))" "$*"; }
die() { printf '\nBOOTSTRAP FAILED: %s\nLog: %s/%s\n' "$*" "$ROOT" "$LOG" >&2; exit 1; }

# Read one key from .env without printing it.
env_get() { grep -E "^$1=" .env 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d '\r' || true; }
# Read one key of the Codespace's own environment file (set in the browser terminal, missing over `gh codespace ssh`).
CS_ENV_FILE=/workspaces/.codespaces/shared/.env
cs_env() { grep -E "^$1=" "$CS_ENV_FILE" 2>/dev/null | tail -n 1 | cut -d= -f2- | tr -d '\r"' || true; }

step "0. Checks (mode: $MODE)"
for c in docker python3; do command -v "$c" >/dev/null || die "'$c' not found"; done
docker info >/dev/null 2>&1 || die "Docker is not running"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' || die "Python 3.11 or newer is needed"
[[ "$(uname -m)" == "x86_64" ]] || echo "WARNING: $(uname -m): Db2 vector indexes need Linux x86-64."
df -h / | tail -1 | awk '{print "root disk free: " $4}'

# ---------------------------------------------------------------------------------------------------------------
step "1. .env"
if [[ ! -f .env ]]; then
  ( umask 077; cp .env.example .env )
  echo "created .env from .env.example"
fi
chmod 600 .env
# Fill every empty or change_me* password with a random one; apply DB2_PORT / DB2_CONTAINER from the environment.
python3 - <<'EOF'
import os, re, secrets
p = ".env"
lines = open(p, encoding="utf-8").read().splitlines()
pw_key = re.compile(r"^(DB2_PASSWORD|NDL_[A-Z0-9]+_PASSWORD)=(.*)$")
generated, out, seen = 0, [], set()
for ln in lines:
    m = pw_key.match(ln)
    if m and (not m.group(2).strip() or m.group(2).strip().startswith("change_me")):
        ln = f"{m.group(1)}={secrets.token_hex(16)}"
        generated += 1
    out.append(ln)
for key in ("DB2_PORT", "DB2_CONTAINER"):
    val = os.environ.get(key)
    if not val:
        continue
    idx = [i for i, ln in enumerate(out) if ln.startswith(key + "=")]
    if idx:
        out[idx[-1]] = f"{key}={val}"
    else:
        out.append(f"{key}={val}")
fd = os.open(p, os.O_WRONLY | os.O_TRUNC | os.O_CREAT, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print(f"passwords generated now: {generated} (values not shown); .env mode 600")
EOF
CONTAINER="$(env_get DB2_CONTAINER)"; CONTAINER="${CONTAINER:-needle-db2}"
PORT="$(env_get DB2_PORT)"; PORT="${PORT:-50000}"
DBNAME="$(env_get DB2_DATABASE)"; DBNAME="${DBNAME:-VECDB}"
echo "container=$CONTAINER host_port=$PORT database=$DBNAME"
if [[ "$(env_get DB2_HOST)" != "localhost" && "$(env_get DB2_HOST)" != "127.0.0.1" ]]; then
  echo "WARNING: DB2_HOST in .env is '$(env_get DB2_HOST)'; the loaders and the tunnel below expect localhost."
fi

# ---------------------------------------------------------------------------------------------------------------
step "2. Db2 container"
if [[ -n "$DATA_DIR" ]]; then
  mkdir -p "$DATA_DIR"
  DATA_DIR="$(cd "$DATA_DIR" && pwd)"
  # A default POSIX ACL on the parent (for example /tmp in a Codespace: other::rw-) is inherited by Db2's
  # directories and locks db2inst1 out of its home. Remove ACLs from the bind directory (no setfacl needed).
  python3 -c "import os,sys; p=sys.argv[1]; [os.removexattr(p, a) for a in os.listxattr(p) if a.startswith('system.posix_acl')]" "$DATA_DIR" 2>/dev/null || true
  chmod 755 "$DATA_DIR" 2>/dev/null || true
  printf 'services:\n  db2:\n    volumes:\n      - %s:/database\n' "$DATA_DIR" > data/compose.datadir.yml
  export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}:data/compose.datadir.yml"
  echo "Db2 data directory: $DATA_DIR (bind mount; data/compose.datadir.yml)"
fi
echo "compose files: ${COMPOSE_FILE:-docker-compose.yml}  project: ${COMPOSE_PROJECT_NAME:-$(basename "$ROOT")}"
if ! docker image inspect icr.io/db2_community/db2:12.1.5.0 >/dev/null 2>&1; then
  echo "Pulling the Db2 image (about 2.6 GB compressed, 7.3 GB on disk; several minutes)..."
fi
docker compose up -d
WAIT_MINUTES="${WAIT_MINUTES:-30}"
deadline=$(( $(date +%s) + WAIT_MINUTES * 60 ))
echo "waiting for Db2 setup (health=healthy and a 'Setup has completed.' line since the last container start)..."
while :; do
  health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$CONTAINER" 2>/dev/null || echo missing)"
  started="$(docker inspect -f '{{.State.StartedAt}}' "$CONTAINER" 2>/dev/null || echo '')"
  logs="$(docker logs --since "$started" "$CONTAINER" 2>&1 || true)"
  if [[ "$health" == "healthy" ]] && grep -q "Setup has completed" <<<"$logs"; then break; fi
  [[ "$health" == "missing" || "$health" == "unhealthy" ]] && die "container $CONTAINER is $health (docker logs $CONTAINER)"
  (( $(date +%s) > deadline )) && die "Db2 setup did not finish in $WAIT_MINUTES min (docker logs $CONTAINER)"
  printf '  [%s] health=%s\n' "$(date +%H:%M:%S)" "${health:-none}"
  sleep 15
done
echo "Db2 is up: $(docker ps --filter "name=^${CONTAINER}$" --format '{{.Names}} {{.Status}} {{.Ports}}')"

# ---------------------------------------------------------------------------------------------------------------
step "3. Database, users, pre-load SQL"
export DB2_CONTAINER="$CONTAINER"
bash scripts/setup_db.sh --with-users || die "scripts/setup_db.sh --with-users"

# ---------------------------------------------------------------------------------------------------------------
step "4. Python environment"
[[ -x .venv/bin/python ]] || python3 -m venv .venv
set +u   # the venv activate script is not written for nounset
# shellcheck disable=SC1091
. .venv/bin/activate
set -u
python --version
pip install -q --disable-pip-version-check -r requirements.txt || die "pip install -r requirements.txt"
export PYTHONPATH=src

# Environment for the loaders (they read DB2_* from the environment). Values are never printed.
set -a; . ./.env; set +a

db2count() {  # row count of a NEEDLE table as the instance owner; 0 if the table is missing
  local out
  out="$(docker exec -i "$CONTAINER" su - db2inst1 -c "db2 connect to $DBNAME >/dev/null && db2 -x \"SELECT COUNT(*) FROM $1\"; db2 connect reset >/dev/null" 2>/dev/null || true)"
  out="$(tr -d '[:space:]' <<<"$out")"
  [[ "$out" =~ ^[0-9]+$ ]] && echo "$out" || echo 0
}

# ---------------------------------------------------------------------------------------------------------------
step "5. Data ($MODE)"
if [[ "$MODE" == "full" ]]; then want_docs=26000; else want_docs=2000; fi
have_docs="$(db2count NEEDLE.ADV_DOC)"; have_post="$(db2count NEEDLE.POSTING)"
echo "NEEDLE.ADV_DOC rows=$have_docs  NEEDLE.POSTING rows=$have_post"
if (( RELOAD == 0 && have_docs >= want_docs && have_post > 0 )); then
  echo "data already loaded; skipping the load (use --reload to force)"
elif [[ "$MODE" == "sample" ]]; then
  python scripts/load_in_codespace.py --sample || die "load_in_codespace.py --sample"
  python scripts/load_postings_in_codespace.py --sample || die "load_postings_in_codespace.py --sample"
else
  command -v gh >/dev/null || die "'gh' (GitHub CLI) is needed for --full"
  if ! gh auth status >/dev/null 2>&1 && [[ -z "${GH_TOKEN:-}${GITHUB_TOKEN:-}" ]] && [[ -n "$(cs_env GITHUB_TOKEN)" ]]; then
    GH_TOKEN="$(cs_env GITHUB_TOKEN)"; export GH_TOKEN   # the Codespace's own repo token; never printed
    echo "gh: using the Codespace token from $CS_ENV_FILE"
  fi
  mkdir -p data/load
  gh release download "$RELEASE_TAG" -R "$RELEASE_REPO" -D data/load --skip-existing \
    $(printf -- '-p %s ' "${RELEASE_FILES[@]}" SHA256SUMS.txt) || die "gh release download $RELEASE_TAG -R $RELEASE_REPO"
  ( cd data/load && sha256sum -c SHA256SUMS.txt ) || die "checksum mismatch in data/load (delete data/load and re-run)"
  cp sql/01_schema.sql sql/02_bm25.sql data/load/
  [[ -f data/eval_qvecs.json.gz ]] || cp data/load/eval_qvecs.json.gz data/   # eval/run_eval.py reads data/
  python scripts/load_in_codespace.py --dir data/load || die "load_in_codespace.py --dir data/load"
  python scripts/load_postings_in_codespace.py --dir data/load || die "load_postings_in_codespace.py --dir data/load"
fi

# ---------------------------------------------------------------------------------------------------------------
step "6. Synthetic fleet and post-load SQL (embargo marks, RCAC, grants)"
python -m needle.sbom --load || die "python -m needle.sbom --load"
bash scripts/setup_db.sh --phase post || die "scripts/setup_db.sh --phase post"

# ---------------------------------------------------------------------------------------------------------------
step "7. Activate the database"
act="$(docker exec -i "$CONTAINER" su - db2inst1 -c "db2 activate database $DBNAME" 2>&1 || true)"
echo "$act" | grep -E "DB20000I|SQL1490W|SQL[0-9]+[NW]" || echo "$act"
grep -qE "DB20000I|SQL1490W" <<<"$act" || die "db2 activate database $DBNAME"

# ---------------------------------------------------------------------------------------------------------------
step "8. Smoke check"
SMOKE="data/logs/bootstrap_smoke_$(date +%Y%m%d_%H%M%S).log"
if [[ "$MODE" == "sample" ]]; then
  python scripts/run_sample_queries.py > "$SMOKE" 2>&1 || { cat "$SMOKE"; die "scripts/run_sample_queries.py"; }
  grep -E "visible rows|exposure join|vector leg|SAMPLE MODE OK" "$SMOKE" | cut -c1-200 || true
  grep -q "SAMPLE MODE OK" "$SMOKE" || die "smoke check (see $SMOKE)"
else
  python - > "$SMOKE" 2>&1 <<'EOF' || { cat "$SMOKE"; die "full-mode row counts"; }
from needle.sbom import _env, password_for
from needle.triage import connect
env = _env()
bad = 0
for u in (env.get("DB2_USER", "db2inst1").upper(), "NDL_SENIOR", "NDL_JUNIOR", "NDL_P10"):
    c = connect(u, password_for(u, env))
    try:
        cur = c.cursor(); cur.execute("SELECT COUNT(*) FROM NEEDLE.ADV_DOC"); n = int(cur.fetchone()[0]); cur.close()
    finally:
        c.close()
    print(f"visible rows in NEEDLE.ADV_DOC as {u}: {n}")
    bad += n == 0
print("FULL MODE COUNTS OK" if not bad else "FULL MODE COUNTS FAILED")
EOF
  cat "$SMOKE"
  grep -q "FULL MODE COUNTS OK" "$SMOKE" || die "smoke check (see $SMOKE)"
fi

# ---------------------------------------------------------------------------------------------------------------
step "9. Done"
CS_NAME="${CODESPACE_NAME:-$(cs_env CODESPACE_NAME)}"; CS_NAME="${CS_NAME:-<codespace-name, see: gh codespace list>}"
cat <<EOF

BOOTSTRAP OK: Db2 $DBNAME in container $CONTAINER on 127.0.0.1:$PORT ($MODE data) in $(( $(date +%s) - T0 )) s.
Log: $ROOT/$LOG

Next steps on your laptop (from the folder that contains needle/):
  1. Copy the credentials (the file holds the generated passwords; never commit it):
       gh codespace cp -c $CS_NAME -e 'remote:$ROOT/.env' needle/.env
  2. Open an SSH tunnel and keep it running in its own terminal:
       gh codespace ssh -c $CS_NAME -- -N -L $PORT:127.0.0.1:$PORT
     Do NOT use 'gh codespace ports forward': large transfers through it hung during development. Use the SSH tunnel.
  3. With the tunnel open, the laptop reaches Db2 at localhost:$PORT with the copied .env, for example:
       cd needle && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
       PYTHONPATH=src python scripts/run_sample_queries.py
       PYTHONPATH=src python -m streamlit run src/needle/app.py     # the app also needs Ollama for query embeddings
EOF
