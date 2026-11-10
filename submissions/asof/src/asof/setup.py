"""One-command setup: users, schema, seed data, grants, and a check that it all works.

    python -m asof.setup            # safe to re-run; creates only what is missing
    python -m asof.setup --reset         # drop the ASOF schema first (asks for confirmation)
    python -m asof.setup --reset-ledger  # DEMO ONLY: empty the ledger, keep the policy data

Steps:
 1. Generate passwords for the five least-privilege users and the chain-head anchor key if .env has
    none (never printed).
 2. Wait until Db2 accepts connections as the owner.
 3. Create the OS users inside the Db2 container (Db2 authenticates against the OS).
 4. Create tables, history table, indexes, triggers and procedures in schema ASOF.
 5. Seed the fictional Aurelia Air and Fernhollow Bank policies, help-centre answers and FAQ knowledge base.
 6. Revoke Db2's PUBLIC defaults and grant each user only what it needs.
 7. Verify as the runtime user: the as-of query works and a ledger UPDATE is refused.
"""

from __future__ import annotations

import argparse
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import ibm_db_dbi
from langchain_core.embeddings import Embeddings

from . import db, indb, schema, seed
from .anchor import AnchorLog
from .config import DEFAULT_ENV_FILE, PROJECT_ROOT, ConfigError, Settings, get_settings
from .embeddings import get_embeddings
from .retriever import clauses_as_of

GENERATED_KEYS = ("ASOF_APP_PASSWORD", "ASOF_EDITOR_PASSWORD", "ASOF_REVIEW_PASSWORD", "ASOF_ANALYST_PASSWORD",
                  "ASOF_MART_PASSWORD")
DOCKER_TIMEOUT_S = 60


class SetupError(RuntimeError):
    pass


def say(msg: str) -> None:
    print(msg, flush=True)


def ensure_generated_passwords(env_path: Path = DEFAULT_ENV_FILE) -> list[str]:
    """Fill empty ASOF_*_PASSWORD keys in .env with strong random values. Returns the keys filled."""
    if not env_path.is_file():
        raise SetupError(f"{env_path} not found. Run: cp .env.example .env  (then set DB2_PASSWORD)")
    lines = env_path.read_text(encoding="utf-8").splitlines()
    filled: list[str] = []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in GENERATED_KEYS:
            seen.add(key)
            if not line.split("=", 1)[1].strip():
                line = f"{key}={secrets.token_urlsafe(24)}"
                filled.append(key)
        out.append(line)
    for key in GENERATED_KEYS:
        if key not in seen:
            out.append(f"{key}={secrets.token_urlsafe(24)}")
            filled.append(key)
    if filled:
        fd, tmp = tempfile.mkstemp(dir=env_path.parent, prefix=".env.")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, env_path)
    return filled


def ensure_anchor_key(settings: Settings, env_path: Path = DEFAULT_ENV_FILE) -> str:
    """The chain-head anchor key lives in its own file outside the project folder, never in .env (which holds
    the owner's password) and never where git could pick it up. Creates it (mode 600, directory 700) if
    missing. A key an earlier version wrote into .env is moved there unchanged, so existing anchors still
    verify. Returns what happened, for the setup log; never the key."""
    if settings.asof_anchor_key and os.environ.get("ASOF_ANCHOR_KEY"):
        return "from the ASOF_ANCHOR_KEY environment variable (override)"
    path = settings.anchor_key_path
    if path.resolve().is_relative_to(PROJECT_ROOT.resolve()):
        raise SetupError(f"ASOF_ANCHOR_KEY_FILE ({path}) is inside the project folder; choose a path outside it")
    legacy = _env_value(env_path, "ASOF_ANCHOR_KEY")
    if path.is_file():
        if legacy:
            _blank_env_value(env_path, "ASOF_ANCHOR_KEY")
        return f"in {path}"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write((legacy or secrets.token_urlsafe(32)) + "\n")
    if legacy:
        _blank_env_value(env_path, "ASOF_ANCHOR_KEY")
        return f"moved from .env to {path} (same key, so existing anchors still verify)"
    return f"generated in {path} (mode 600, not shown)"


def _env_value(env_path: Path, key: str) -> str:
    if not env_path.is_file():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.split("=", 1)[0].strip() == key and "=" in line:
            return line.split("=", 1)[1].strip()
    return ""


def _blank_env_value(env_path: Path, key: str) -> None:
    lines = [f"{key}=" if line.split("=", 1)[0].strip() == key else line
             for line in env_path.read_text(encoding="utf-8").splitlines()]
    fd, tmp = tempfile.mkstemp(dir=env_path.parent, prefix=".env.")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, env_path)


def wait_for_db2(settings: Settings, timeout_s: int = 300) -> None:
    deadline = time.monotonic() + timeout_s
    delay = 2.0
    while True:
        try:
            with db.connection(settings, "admin") as conn:
                say(f"  Db2 is up: {db.server_version(conn)}")
                return
        except db.DatabaseError as exc:
            if exc.sqlstate == "08001" and "SQL30082N" in str(exc):
                raise SetupError(f"{exc}\n  DB2_USER / DB2_PASSWORD in .env do not match the Db2 instance.") from None
            if time.monotonic() > deadline:
                raise SetupError(f"Db2 not reachable after {timeout_s}s: {exc}") from None
            say(f"  waiting for Db2 ({exc.sqlstate or 'no answer'}), retrying in {delay:.0f}s")
            time.sleep(delay)
            delay = min(delay * 1.5, 15)


def _docker(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], input=stdin, capture_output=True, text=True, timeout=DOCKER_TIMEOUT_S)


def ensure_os_users(settings: Settings) -> bool:
    """Create the five users inside the Db2 container and set their passwords from .env.

    Passwords go to chpasswd on stdin, so they never show up in a process list.
    Returns False (with instructions) when the container cannot be reached.
    """
    if shutil.which("docker") is None:
        say("  WARNING: docker not found, so the Db2 users were not created automatically.")
        return _manual_user_help(settings)
    container = find_db2_container(settings.db2_container)
    if container is None:
        say(f"  WARNING: no running Db2 container found (tried DB2_CONTAINER='{settings.db2_container}', "
            f"then {', '.join(FALLBACK_CONTAINERS)}, then any single container running a Db2 image).")
        return _manual_user_help(settings)
    if container != settings.db2_container:
        say(f"  DB2_CONTAINER '{settings.db2_container}' is not running; using the Db2 container '{container}' instead")
    for user, secret in ((settings.asof_app_user, settings.asof_app_password),
                         (settings.asof_editor_user, settings.asof_editor_password),
                         (settings.asof_review_user, settings.asof_review_password),
                         (settings.asof_analyst_user, settings.asof_analyst_password),
                         (settings.asof_mart_user, settings.asof_mart_password)):
        if _docker(["exec", container, "id", "-u", user]).returncode != 0:
            made = _docker(["exec", container, "useradd", "--no-create-home", "--shell", "/sbin/nologin", user])
            if made.returncode != 0:
                raise SetupError(f"useradd {user} failed in {container}: {made.stderr.strip()}")
            say(f"  created OS user {user} in {container}")
        pw = _docker(["exec", "-i", container, "chpasswd"], stdin=f"{user}:{secret.get_secret_value()}\n")  # type: ignore[union-attr]
        if pw.returncode != 0:
            raise SetupError(f"setting the password for {user} failed: {pw.stderr.strip()}")
    say(f"  OS users {settings.asof_app_user}, {settings.asof_editor_user}, {settings.asof_review_user}, "
        f"{settings.asof_analyst_user} and {settings.asof_mart_user} ready (passwords from .env)")
    return True


# The organizers' guide and the IBM Db2 VS Code extension both name the container db2server;
# AsOf's compose file names it asof-db2.
FALLBACK_CONTAINERS = ("db2server", "asof-db2")


def _running(container: str) -> bool:
    state = _docker(["inspect", "-f", "{{.State.Running}}", container])
    return state.returncode == 0 and state.stdout.strip() == "true"


def find_db2_container(preferred: str) -> str | None:
    """The configured container if it runs, else a known name, else the only running Db2 container."""
    for name in (preferred, *[c for c in FALLBACK_CONTAINERS if c != preferred]):
        if _running(name):
            return name
    listed = _docker(["ps", "--format", "{{.Names}}\t{{.Image}}"])
    if listed.returncode != 0:
        return None
    db2 = [line.split("\t")[0] for line in listed.stdout.splitlines()
           if "\t" in line and ("db2_community/db2" in line.split("\t")[1] or "asof-db2" in line.split("\t")[1])]
    return db2[0] if len(db2) == 1 else None


def _manual_user_help(settings: Settings) -> bool:
    say("  Db2 authenticates against operating-system users on the Db2 server. Create them there:")
    for user, key in ((settings.asof_app_user, "ASOF_APP_PASSWORD"), (settings.asof_editor_user, "ASOF_EDITOR_PASSWORD"),
                      (settings.asof_review_user, "ASOF_REVIEW_PASSWORD"),
                      (settings.asof_analyst_user, "ASOF_ANALYST_PASSWORD"), (settings.asof_mart_user, "ASOF_MART_PASSWORD")):
        say(f"    useradd --no-create-home --shell /sbin/nologin {user} && passwd {user}   # password = {key} in .env")
    say("  Setup continues; the grants work without the OS users, but the app cannot log in until they exist.")
    return False


def register_embedder(conn: ibm_db_dbi.Connection, settings: Settings, embeddings: Embeddings, target: str) -> bool:
    """Register Db2's own embedding model if wanted, and use it only if it agrees with the local one."""
    if not settings.indb_embeddings_wanted:
        say("  off (no API key, or ASOF_INDB_EMBEDDINGS=off): the app embeds clauses itself")
        return False
    try:
        endpoint = indb.register(conn, settings, target)
        result = indb.probe(conn, embeddings, target)
    except indb.InDbError as exc:
        if indb.model_exists(conn, target):  # registered but untrusted: never let APPLY_POLICY_CHANGE use it
            db.execute(conn, f"DROP EXTERNAL MODEL {db.ident(target)}.{db.ident(indb.MODEL_NAME)}")
            conn.commit()
        say(f"  WARNING: {exc}. The app embeds clauses itself instead.")
        return False
    host = urlparse(endpoint.url).hostname
    model = settings.watsonx_embedding_model if settings.asof_indb_provider == "watsonx" else settings.embedding_api_model
    say(f"  {target}.{indb.MODEL_NAME}: {model} at {host}; Db2's vector matches the local one "
        f"(cosine {result.agreement}), {result.latency_ms} ms per call")
    if not endpoint.documented:
        say("  note: plain HTTP to a local endpoint works but is undocumented by IBM (HTTPS is); development use only")
    return True


STATS_TABLES = ("POLICY_CLAUSE", "POLICY_CLAUSE_HIST", "PUBLISHED_ANSWER", "ANSWER_LEDGER", "CLAIM_CITATION")


def collect_statistics(settings: Settings, target: str) -> str:
    """RUNSTATS on the tables the hot queries read, so the optimizer costs plans from real counts.

    SYSPROC.ADMIN_CMD would do this over SQL, but it runs as a fenced routine, which crashes
    under Rosetta on Apple Silicon (SQL1646N). So the command line processor inside the Db2
    container is tried first, and ADMIN_CMD (with the command as a bound parameter) second.
    Db2's automatic statistics collection catches up later in any case, so a failure here warns
    instead of stopping setup.
    """
    tables = [f"{db.ident(target)}.{db.ident(t)}" for t in STATS_TABLES]
    commands = [f"RUNSTATS ON TABLE {t} WITH DISTRIBUTION AND SAMPLED DETAILED INDEXES ALL" for t in tables]
    container = find_db2_container(settings.db2_container) if shutil.which("docker") else None
    if container is not None:
        script = f"db2 connect to {db.ident(settings.db2_database)} > /dev/null && " + " && ".join(
            f'db2 "{cmd}" > /dev/null' for cmd in commands)
        done = subprocess.run(["docker", "exec", "-u", settings.db2_admin_user, container, "bash", "-lc", script],
                              capture_output=True, text=True, timeout=600)
        if done.returncode == 0:
            return f"RUNSTATS on {len(tables)} tables (command line processor in {container})"
    try:
        with db.connection(settings, "admin") as conn:
            for cmd in commands:
                db.execute(conn, "CALL SYSPROC.ADMIN_CMD(?)", (cmd,))
            conn.commit()
        return f"RUNSTATS on {len(tables)} tables (SYSPROC.ADMIN_CMD)"
    except db.DatabaseError as exc:
        return f"WARNING: statistics not collected ({exc.sqlstate}); Db2's automatic statistics will catch up"


def _must_refuse(conn: ibm_db_dbi.Connection, user: str, statements: tuple[tuple[str, str], ...]) -> str:
    """Run each literal statement as `user` and require Db2 to refuse it; return what was refused, with states."""
    refused = []
    for label, sql in statements:
        try:
            db.execute(conn, sql)
            conn.rollback()
            raise SetupError(f"{user} was allowed to run: {sql}")
        except db.DatabaseError as exc:
            conn.rollback()
            if exc.sqlstate not in ("42501", "42502"):
                raise SetupError(f"unexpected error for {user} running {sql}: {exc}") from None
            refused.append(f"{label} ({exc.sqlstate})")
    return ", ".join(refused)


def verify_least_privilege(settings: Settings, target: str) -> None:
    """Prove the runtime user can read policy as of a date and cannot write anything, and that dbt's user cannot
    change the ledger or build next to it."""
    embeddings = get_embeddings(settings.embedding_model)
    # The same claim, checked for two travel dates, must reach different versions of BRV-002.
    vec = embeddings.embed_query("You can apply for the bereavement fare retroactively after you travel.")
    with db.connection(settings, "app") as conn:
        for day, want in ((date(2026, 3, 10), "v1"), (date(2026, 6, 2), "v2")):
            found = {c.clause_id: c.version_label for c in clauses_as_of(conn, vec, day, "AURELIA-CSP", k=3, schema=target)}
            if found.get("BRV-002") != want:
                raise SetupError(f"as-of retrieval for {day} returned {found}, expected BRV-002 {want}")
        say(f"  as {settings.asof_app_user}: 2026-03-10 -> BRV-002 v1, 2026-06-02 -> BRV-002 v2")
        db.use_schema(conn, target)  # the statements below are literals with unqualified names
        refused = _must_refuse(conn, settings.asof_app_user, (
            ("UPDATE", "UPDATE POLICY_CLAUSE SET CLAUSE_TEXT = 'x'"),
            ("DELETE", "DELETE FROM ANSWER_LEDGER"),
            ("CREATE TABLE", "CREATE TABLE SHOULD_NOT_EXIST (X INT)")))
        say(f"  as {settings.asof_app_user}: refused {refused}")
    with db.connection(settings, "mart") as conn:
        db.use_schema(conn, target)
        refused = _must_refuse(conn, settings.asof_mart_user, (
            ("DELETE on the ledger", "DELETE FROM ANSWER_LEDGER"),
            ("CREATE TABLE beside the ledger", "CREATE TABLE SHOULD_NOT_EXIST (X INT)")))
        say(f"  as {settings.asof_mart_user}: refused {refused}")


def run(reset: bool = False, target: str = db.SCHEMA, reset_ledger: bool = False) -> None:
    schema.validate_schema(target)
    say("1/9 Passwords for the least-privilege users, and the chain-head anchor key")
    filled = ensure_generated_passwords()
    say(f"  generated {', '.join(filled)} and saved to .env (not shown)" if filled else "  already set in .env")
    get_settings.cache_clear()
    settings = get_settings()
    settings.require("db2_admin_password", "asof_app_password", "asof_editor_password", "asof_review_password",
                     "asof_analyst_password", "asof_mart_password")
    say(f"  chain-head anchor key: {ensure_anchor_key(settings)}")
    get_settings.cache_clear()
    settings = get_settings()

    say("2/9 Db2 connection")
    wait_for_db2(settings)

    say("3/9 Operating-system users in the Db2 container")
    users_ok = ensure_os_users(settings)

    with db.connection(settings, "admin") as conn:
        if reset:
            say(f"  --reset: dropping schema {target}")
            schema.drop(conn, target)
        elif reset_ledger and schema.table_exists(conn, target, "ANSWER_LEDGER"):
            removed = schema.reset_ledger(conn, target)
            say(f"  --reset-ledger (demo only): dropped and recreated the ledger tables, {removed} decisions removed")
        if reset or reset_ledger:  # the old anchors describe the ledger that was just thrown away: keep them aside
            anchors = AnchorLog.from_settings(settings, target)
            archived = anchors.rotate() if anchors else None
            if archived:
                say(f"  chain-head anchors of the old ledger kept as {archived.name}")
        say(f"4/9 Schema {target}")
        counts = schema.install(conn, target)
        say(f"  {counts['created']} objects created, {counts['skipped']} already present")

        embeddings = get_embeddings(settings.embedding_model)
        say("5/9 In-database embeddings (CREATE EXTERNAL MODEL, TO_EMBEDDING)")
        in_db = register_embedder(conn, settings, embeddings, target)

        say("6/9 Seed data (fictional Aurelia Air and Fernhollow Bank)")
        n_clauses = seed.seed_policy(conn, embeddings, target, in_db=in_db)
        n_head = seed.seed_chain_head(conn, target)
        n_pub = seed.seed_published_answers(conn, target)
        n_faq = seed.seed_faq(conn, embeddings, target)
        say(f"  inserted {n_clauses} clause versions, {n_pub} help-centre answers, {n_faq} FAQ entries"
            + (", chain head" if n_head else "")
            + (" (nothing new: already seeded)" if not any((n_clauses, n_pub, n_faq, n_head)) else ""))

        say("7/9 Least-privilege grants")
        g = schema.apply_grants(conn, settings.asof_app_user, settings.asof_editor_user, target,
                                analyst_user=settings.asof_analyst_user, mart_user=settings.asof_mart_user,
                                review_user=settings.asof_review_user)
        say(f"  {g['applied']} grants and revokes applied"
            + (f"; {g['already_revoked']} revokes found nothing to revoke (PUBLIC defaults already gone, or a "
               "fresh install)" if g["already_revoked"] else ""))

    say("8/9 Optimizer statistics (RUNSTATS)")
    say("  " + collect_statistics(settings, target))

    say("9/9 Verify as the runtime user")
    if users_ok:
        verify_least_privilege(settings, target)
    else:
        say("  skipped: create the OS users first (see above), then re-run setup")
    say("\nSetup complete.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m asof.setup", description=__doc__.split("\n\n")[0])
    parser.add_argument("--reset", action="store_true", help="drop the ASOF schema and rebuild it (deletes the ledger)")
    parser.add_argument("--reset-ledger", action="store_true",
                        help="DEMO ONLY: drop and recreate the ledger tables (deletes every recorded decision); "
                             "policy data is kept")
    parser.add_argument("--yes", action="store_true", help="do not ask before --reset or --reset-ledger")
    args = parser.parse_args(argv)
    if args.reset and args.reset_ledger:
        parser.error("use --reset or --reset-ledger, not both")
    if (args.reset or args.reset_ledger) and not args.yes:
        what = ("every ledger entry and policy change in schema ASOF" if args.reset
                else "every recorded decision in the ASOF ledger (demo only; policy data is kept)")
        answer = input(f"This deletes {what}. Type 'reset' to continue: ")
        if answer.strip() != "reset":
            say("Cancelled.")
            return 1
    try:
        run(reset=args.reset, reset_ledger=args.reset_ledger)
    except (SetupError, ConfigError, db.DatabaseError) as exc:
        say(f"\nSETUP FAILED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
