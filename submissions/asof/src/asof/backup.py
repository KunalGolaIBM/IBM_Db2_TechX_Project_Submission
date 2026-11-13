"""Backup and restore drill: Db2's own online BACKUP and RESTORE, judged by the ledger's own checks.

    python -m asof.backup drill [--rows 40] [--keep]

A backup is only as good as the restore, so the drill restores into a database that did not exist and
checks it the way an auditor would. It works in scratch databases, so the application's database
(DB2_DATABASE) and its logging mode are never touched:

 1. CREATE DATABASE ASOFSRC, switch it to archive logging (LOGARCHMETH1), and take the one offline backup
    Db2 then requires before the database can be used.
 2. Install AsOf into it with the normal setup (schema, procedures, triggers, seed data, users, grants), then
    append decisions through APPEND_LEDGER as the runtime user, anchoring each new chain head the way the
    app does (in a drill anchor log, never the app's).
 3. BACKUP DATABASE ... ONLINE ... INCLUDE LOGS while a writer keeps appending: the application is not
    stopped, and its appends during the backup succeed.
 4. RESTORE DATABASE ASOFSRC ... INTO a database that does not exist yet (ASOFRxxx), then ROLLFORWARD ...
    TO END OF BACKUP AND STOP from the logs in the image: a consistent copy as of the moment the backup finished.
 5. On the copy, as the runtime user: VERIFY_CHAIN is OK; every anchor up to the restored head matches; the
    restored head has the same hash in the source (so it is a copy of that ledger, not just a consistent one);
    the triggers still refuse an UPDATE, even from the owner.
 6. Drop both databases and delete the images and archived logs (unless --keep).

It needs the Db2 command line processor inside the Db2 container (docker exec), as RUNSTATS in setup does.
Writes docs/backup/db2-<machine>-on-<host>__<commit>.json and exits 1 if any check fails.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from . import db, ledger
from .anchor import AnchorLog
from .anchor import verify as verify_anchors
from .config import PROJECT_ROOT, ConfigError, Settings, get_settings
from .setup import find_db2_container

SOURCE_DB = "ASOFSRC"
# The restored copy gets a new name every run (ASOFR + 3 random characters). With the instance's directory cache on
# (DIR_CACHE=YES, the default), RESTORE ... INTO a name that was dropped earlier in the instance's life failed with
# SQL30061N here, most likely because the cache still held the old entry; a name never used before always worked.
RESTORED_PREFIX = "ASOFR"
RESTORED_RE = re.compile(r"^ASOFR[A-Z0-9]{3}$")
WORK = "/database/data/asof-drill"  # inside the container, on the Db2 data volume
SCHEMA = db.SCHEMA
REPORT_DIR = PROJECT_ROOT / "docs" / "backup"
DRILL_ANCHORS = PROJECT_ROOT / "var" / "backup-drill"
TIMESTAMP_RE = re.compile(r"timestamp for this backup image is\s*:\s*(\d{14})", re.I)
SQL_HEAD = "SELECT LEDGER_ID, ROW_HASH FROM ANSWER_LEDGER ORDER BY LEDGER_ID DESC FETCH FIRST 1 ROW ONLY"
SQL_COUNT = "SELECT COUNT(*) FROM ANSWER_LEDGER"
SQL_TAMPER = "UPDATE ANSWER_LEDGER SET FINAL_ANSWER = 'edited after the fact' WHERE LEDGER_ID = ?"


class DrillError(RuntimeError):
    """A step of the drill failed; the message names the step and Db2's own message."""


@dataclass
class Step:
    name: str
    seconds: float
    detail: str = ""


@dataclass
class Drill:
    container: str
    admin_user: str
    steps: list[Step] = field(default_factory=list)

    def clp(self, script: str, step: str, timeout_s: int = 1800, ok_codes: tuple[int, ...] = (0, 1, 2)) -> str:
        """Run Db2 command line processor commands as the instance owner. CLP exit codes: 0 done, 1 no rows,
        2 warning, 4 and above an error."""
        started = time.monotonic()
        try:
            done = subprocess.run(["docker", "exec", "-u", self.admin_user, self.container, "bash", "-lc", script],
                                  capture_output=True, text=True, timeout=timeout_s, check=False)
        except subprocess.TimeoutExpired:
            raise DrillError(f"{step}: no result within {timeout_s} s") from None
        out = (done.stdout + done.stderr).strip()
        if done.returncode not in ok_codes:
            raise DrillError(f"{step} failed (exit {done.returncode}): {_last_lines(out, 12)}")
        self.steps.append(Step(step, round(time.monotonic() - started, 1), _last_lines(out, 2)))
        return out

    def timed(self, step: str, detail: str, started: float) -> None:
        self.steps.append(Step(step, round(time.monotonic() - started, 1), detail))


def _last_lines(text: str, n: int = 4) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return " | ".join(lines[-n:])[:600]


def _entry(n: int, phase: str) -> ledger.LedgerEntry:
    """A synthetic decision: same procedure, columns and hashing as a real one; no model is called."""
    return ledger.LedgerEntry(
        request_id=str(uuid.uuid4()), channel="api", doc_id="AURELIA-CSP", as_of=date(2026, 3, 10),
        question_redacted=f"Backup drill question {n} ({phase})", draft_redacted="Bereavement fares can be claimed "
        "after travel.", final_answer="A specialist will confirm this for you.", decision="ESCALATED",
        reason_code="NOT_COVERED", model_info="backup-drill (no model)", prompt_version="drill", latency_ms=1,
        verdicts={"drill": True, "n": n, "phase": phase})


def _append(settings: Settings, anchors: AnchorLog, n: int, phase: str) -> ledger.Appended:
    with db.connection(settings, "app") as conn:
        appended = ledger.append(conn, _entry(n, phase), SCHEMA)
    anchors.append(appended.ledger_id, appended.row_hash)
    return appended


def _head(settings: Settings, role: str = "app") -> tuple[int, str, int]:
    with db.connection(settings, role) as conn:  # type: ignore[arg-type]
        db.use_schema(conn, SCHEMA)
        row = db.query(conn, SQL_HEAD)
        count = int(db.query(conn, SQL_COUNT)[0][0])
    return (int(row[0][0]), str(row[0][1]).strip(), count) if row else (0, "", count)


def _hash_at(settings: Settings, ledger_id: int) -> str | None:
    with db.connection(settings, "app") as conn:
        db.use_schema(conn, SCHEMA)
        rows = db.query(conn, ledger.SQL_ROW_HASH, (ledger_id,))
    return str(rows[0][0]).strip() if rows else None


def _existing_databases(d: Drill) -> set[str]:
    out = d.clp("db2 list database directory", "list databases")
    return {m.upper() for m in re.findall(r"Database name\s*=\s*(\S+)", out)}


def _drop_scratch(d: Drill, present: set[str]) -> None:
    """Drop the drill's own databases (the source, and any restored copy). Never FORCE APPLICATION ALL: that would
    also cut off every user of the application's database. The drill closes its own connections first."""
    for name in sorted(present):
        if name == SOURCE_DB or RESTORED_RE.match(name):
            d.clp(f"db2 deactivate database {name} > /dev/null; db2 drop database {name}", f"drop {name}")


def _new_restored_name(present: set[str]) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    while True:
        name = RESTORED_PREFIX + "".join(secrets.choice(alphabet) for _ in range(3))
        if name not in present and name != SOURCE_DB:
            return name


def run(settings: Settings, rows: int = 40, keep: bool = False, anchor_dir: Path = DRILL_ANCHORS) -> dict[str, Any]:
    if shutil.which("docker") is None:
        raise ConfigError("the drill runs Db2's BACKUP and RESTORE commands inside the Db2 container: docker is needed")
    container = find_db2_container(settings.db2_container)
    if container is None:
        raise ConfigError(f"no running Db2 container found (DB2_CONTAINER={settings.db2_container})")
    if settings.db2_database.upper() == SOURCE_DB or RESTORED_RE.match(settings.db2_database.upper()):
        raise ConfigError(f"DB2_DATABASE must not be one of the drill's scratch names ({SOURCE_DB}, {RESTORED_PREFIX}xxx)")
    d = Drill(container, settings.db2_admin_user)
    source = settings.model_copy(update={"db2_database": SOURCE_DB})
    machine = d.clp("uname -m", "machine").strip().splitlines()[-1]
    level = _last_lines(d.clp("db2level | grep -i 'Informational tokens'", "db2level"), 1)

    present = _existing_databases(d)
    _drop_scratch(d, present)  # leftovers of an interrupted run
    restored_db = _new_restored_name(present)
    restored = settings.model_copy(update={"db2_database": restored_db})
    d.clp(f"rm -rf {WORK} && mkdir -p {WORK}/archive {WORK}/images {WORK}/restore-logs", "work directories")

    # 1. A database in archive-logging mode, which an online backup requires.
    d.clp(f"db2 create database {SOURCE_DB} using codeset UTF-8 territory US", f"CREATE DATABASE {SOURCE_DB}")
    d.clp(f"db2 update db cfg for {SOURCE_DB} using LOGARCHMETH1 DISK:{WORK}/archive/", "LOGARCHMETH1 to disk")
    d.clp(f"db2 backup database {SOURCE_DB} to {WORK}/images", "offline backup (ends backup-pending)")

    # 2. AsOf installed the normal way, then decisions appended and anchored as the app does.
    started = time.monotonic()
    env = {**os.environ, "DB2_DATABASE": SOURCE_DB, "ASOF_INDB_EMBEDDINGS": "off"}  # no external calls
    done = subprocess.run([sys.executable, "-m", "asof.setup"], env=env, capture_output=True, text=True, timeout=1800,
                          check=False, cwd=PROJECT_ROOT)
    if done.returncode != 0 or "Setup complete." not in done.stdout:
        raise DrillError(f"python -m asof.setup on {SOURCE_DB} failed: {_last_lines(done.stdout + done.stderr)}")
    d.timed(f"python -m asof.setup on {SOURCE_DB}", _last_lines(done.stdout, 1), started)

    anchor_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = settings.anchor_key or secrets.token_bytes(32)
    anchors = AnchorLog(anchor_dir, key, SCHEMA)  # the drill's own log: the app's anchors are never touched
    anchors.rotate()  # a log from an earlier drill describes a database that no longer exists
    started = time.monotonic()
    for n in range(1, rows + 1):
        _append(source, anchors, n, "before backup")
    d.timed(f"append {rows} decisions (APPEND_LEDGER as {settings.asof_app_user}, each anchored)", "", started)
    before = _head(source)

    # 3. Online backup while the application keeps writing.
    stop, during, errors = threading.Event(), [], []

    def writer() -> None:
        n = rows
        while not stop.is_set():
            n += 1
            try:
                during.append(_append(source, anchors, n, "during backup").ledger_id)
            except Exception as exc:  # noqa: BLE001 - reported below; the drill then fails
                errors.append(f"{type(exc).__name__}: {exc}"[:300])
                return
            stop.wait(0.2)

    thread = threading.Thread(target=writer, name="drill-writer", daemon=True)
    thread.start()
    try:
        out = d.clp(f"db2 backup database {SOURCE_DB} online to {WORK}/images compress include logs",
                    "BACKUP DATABASE ONLINE COMPRESS INCLUDE LOGS")
    finally:
        stop.set()
        thread.join(30)
    m = TIMESTAMP_RE.search(out)
    if not m:
        raise DrillError(f"the online backup printed no image timestamp: {_last_lines(out)}")
    image_ts = m.group(1)
    after = _head(source)
    sizes = d.clp(f"ls -l {WORK}/images", "image sizes")
    image_bytes = {ts: int(sz) for sz, ts in re.findall(r"\s(\d+)\s+\w+\s+\d+\s+[\d:]+\s+\S*\.(\d{14})\.", sizes)}

    # 4. Restore into a database that does not exist yet, then roll forward to the end of the backup.
    d.clp(f"db2 restore database {SOURCE_DB} from {WORK}/images taken at {image_ts} into {restored_db} "
          f"logtarget {WORK}/restore-logs without prompting", "RESTORE DATABASE ... INTO a new database")
    d.clp(f'db2 "rollforward database {restored_db} to end of backup and stop overflow log path ({WORK}/restore-logs)"',
          "ROLLFORWARD TO END OF BACKUP AND STOP")

    # 5. Judge the restored copy with the ledger's own checks.
    started = time.monotonic()
    r_id, r_hash, r_count = _head(restored)
    with db.connection(restored, "app") as conn:
        chain = ledger.verify_chain(conn, SCHEMA)
        anchor_status = verify_anchors(anchors, conn, SCHEMA, through=r_id)
    same_in_source = _hash_at(source, r_id) == r_hash
    refused = None
    with db.connection(restored, "admin") as conn:
        db.use_schema(conn, SCHEMA)
        try:
            db.execute(conn, SQL_TAMPER, (1,))
            conn.rollback()
        except db.DatabaseError as exc:
            conn.rollback()
            refused = exc.sqlstate
    d.timed("checks on the restored database", "", started)

    checks = {
        "online backup did not block the app: appends during the backup succeeded": bool(during) and not errors,
        "restored ledger holds every decision committed before the backup started": r_id >= before[0],
        "restored ledger holds nothing after the source's head when the backup ended": r_id <= after[0],
        "VERIFY_CHAIN on the restored database is OK": chain.status == "OK",
        "every anchor up to the restored head matches the restored ledger": anchor_status.status == "OK",
        "the restored head has the same hash in the source ledger": same_in_source,
        "the triggers still refuse UPDATE on the restored ledger, even from the owner": refused == "75001",
    }
    report: dict[str, Any] = {
        "ran_at": datetime.now(UTC).isoformat(timespec="seconds"), "git_commit": _commit(), "machine": machine,
        "host_machine": platform.machine(),  # arm64 with an x86_64 Db2: the container runs under Rosetta
        "db2level": level, "container": container, "source_db": SOURCE_DB, "restored_db": restored_db,
        "image_timestamp": image_ts, "image_bytes": image_bytes,
        "source_head_before_backup": {"ledger_id": before[0], "rows": before[2]},
        "appended_during_backup": len(during), "writer_errors": errors,
        "source_head_after_backup": {"ledger_id": after[0], "rows": after[2]},
        "restored_head": {"ledger_id": r_id, "rows": r_count},
        "verify_chain": {"status": chain.status, "checked": chain.checked},
        "anchors": anchor_status.as_dict(), "update_refused_sqlstate": refused,
        "checks": checks, "passed": all(checks.values()),
        "steps": [s.__dict__ for s in d.steps],
    }

    # 6. Clean up, unless asked to keep everything for inspection.
    if not keep:
        _drop_scratch(d, {SOURCE_DB, restored_db})
        d.clp(f"rm -rf {WORK}", "remove images and archived logs")
    return report


def _commit() -> str:
    done = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=PROJECT_ROOT,
                          check=False)
    return done.stdout.strip() or "unknown"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.backup", description=(__doc__ or "").split("\n\n")[0])
    p.add_argument("command", choices=["drill"])
    p.add_argument("--rows", type=int, default=40, help="decisions appended before the backup (1 to 5000)")
    p.add_argument("--keep", action="store_true", help="keep both databases and the images for inspection")
    args = p.parse_args(argv)
    if not 1 <= args.rows <= 5000:
        p.error("--rows must be between 1 and 5000")
    settings = get_settings()
    settings.require("db2_admin_password")
    try:
        report = run(settings, args.rows, args.keep)
    except (DrillError, ConfigError, db.DatabaseError) as exc:
        print(f"backup drill failed: {exc}", file=sys.stderr)
        return 1
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"db2-{report['machine']}-on-{report['host_machine']}__{report['git_commit']}.json"
    out.write_text(json.dumps(report, indent=1, default=str) + "\n", encoding="utf-8")
    for step in report["steps"]:
        print(f"  {step['seconds']:>7.1f} s  {step['name']}")
    for name, ok in report["checks"].items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"report: {out.relative_to(PROJECT_ROOT)}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
