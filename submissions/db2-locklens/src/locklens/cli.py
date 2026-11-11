"""Command line entry point: ``python -m locklens.cli <command>``.

Commands: test-connection | init-db | snapshot [--json] [--no-record]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Callable

from .config import Settings, load_env_file
from .errors import ConfigError
from .logging_setup import configure_logging
from .services.runtime import LockLensRuntime


def _runtime() -> LockLensRuntime:
    load_env_file(".env")
    settings = Settings.from_env()
    configure_logging(settings.log_level, [settings.db_password])
    return LockLensRuntime(settings)


_NO_RETRY = {"invalid_credentials", "driver_missing"}


def wait_for_db2(rt: Any, timeout: int, interval: int = 10, *,
                 sleep: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic, out: Callable[[str], None] = print):
    """Poll test_connection() until it succeeds or ``timeout`` seconds pass.

    Db2's container needs several minutes on first start. Wrong credentials and a missing driver
    can never fix themselves, so they stop the wait immediately.
    """
    deadline = clock() + timeout
    status = rt.test_connection()
    while not status.ok and status.kind not in _NO_RETRY and clock() < deadline:
        out(f"Db2 not ready yet ({status.kind or 'unknown'}); retrying in {interval}s ...")
        sleep(interval)
        status = rt.test_connection()
    return status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="locklens", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    tc = sub.add_parser("test-connection", help="check that Db2 is reachable with the configured user")
    tc.add_argument("--wait", type=int, default=0, metavar="SECONDS",
                    help="keep retrying for up to SECONDS (use ~900 after the first 'docker compose up')")
    sub.add_parser("init-db", help="create the LockLens incident tables (idempotent)")
    snap = sub.add_parser("snapshot", help="take one monitoring snapshot and print the diagnosis")
    snap.add_argument("--json", action="store_true", help="machine-readable output")
    snap.add_argument("--no-record", action="store_true", help="do not write incidents to Db2")
    args = parser.parse_args(argv)

    try:
        rt = _runtime()
    except ConfigError as exc:
        print("Configuration problem(s):", file=sys.stderr)
        for p in exc.problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    try:
        if args.command == "test-connection":
            status = wait_for_db2(rt, args.wait) if args.wait else rt.test_connection()
            print(("OK: " if status.ok else "FAILED: ") + status.message
                  + (f" (server {status.server})" if status.server else ""))
            return 0 if status.ok else 1
        if args.command == "init-db":
            for line in rt.init_schema():
                print(line)
            return 0
        result = rt.refresh(record=not args.no_record)
        if result.error:
            print(f"ERROR: {result.error}", file=sys.stderr)
            return 1
        diag, snapshot = result.diagnosis, result.snapshot
        assert diag is not None and snapshot is not None
        if args.json:
            print(json.dumps({
                "captured_at": snapshot.captured_at, "locks": len(snapshot.locks),
                "waits": len(snapshot.waits), "pipeline": diag.pipeline,
                "narrative_source": diag.narrative_source,
                "findings": [f.to_dict() for f in diag.findings],
                "notes": [n.__dict__ for n in snapshot.notes + result.notes],
            }, indent=2))
        else:
            print(f"Snapshot {snapshot.captured_at}: {len(snapshot.locks)} lock(s), "
                  f"{len(snapshot.waits)} wait(s)  [pipeline: {diag.pipeline}]")
            for n in snapshot.notes + result.notes:
                print(f"  note [{n.level}] {n.message}")
            for f in diag.findings:
                print(f"\n[{f.severity.name}] {f.finding_type}: {f.title}")
                print(f"  {f.explanation}")
                for e in f.evidence:
                    print(f"  evidence: {e}")
                for r in f.recommendations:
                    print(f"  next: {r}")
            if result.recorded:
                r = result.recorded
                print(f"\nIncidents: {r.created} created, {r.updated} updated, {r.resolved} resolved")
        return 0
    finally:
        rt.close()


if __name__ == "__main__":
    raise SystemExit(main())
