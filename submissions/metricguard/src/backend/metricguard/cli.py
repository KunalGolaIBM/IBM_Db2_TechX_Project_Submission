"""MetricGuard command line: `metricguard health | db init | db verify | openapi`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from metricguard.config import get_settings
from metricguard.db import Db2Client, Db2Error


def cmd_health(_: argparse.Namespace) -> int:
    settings = get_settings()
    try:
        with Db2Client(settings) as db:
            ident = db.server_identity()
            tables = db.scalar("SELECT COUNT(*) FROM SYSCAT.TABLES WHERE TABSCHEMA = 'METRICGUARD' AND TYPE = 'T'")
    except Db2Error as exc:
        print(json.dumps({"status": "error", "target": settings.redacted_target(), "sqlstate": exc.sqlstate,
                          "message": str(exc)}, indent=2))
        return 1
    print(json.dumps({
        "status": "ok", "target": settings.redacted_target(),
        **{k: str(v) if k == "server_timestamp" else v for k, v in ident.items()},
        "metricguard_tables": tables,
    }, indent=2))
    return 0


def cmd_db_init(args: argparse.Namespace) -> int:
    from metricguard.seed.loader import initialize

    try:
        summary = initialize(get_settings(), reset=args.reset)
    except Db2Error as exc:
        print(f"ERROR: {exc} (SQLSTATE {exc.sqlstate})", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    return 0


def cmd_db_migrate(_: argparse.Namespace) -> int:
    """Non-destructive Stage 2 migration: audit columns + least-privilege audit grants. No data is dropped."""
    from metricguard.seed.migrations import grant_audit_writer, migrate_audit_table, privileges

    settings = get_settings()
    try:
        with Db2Client(settings) as db:
            added = migrate_audit_table(db, print)
            granted = grant_audit_writer(db, settings, print)
            privs = privileges(db)
    except Db2Error as exc:
        print(f"ERROR: {exc} (SQLSTATE {exc.sqlstate})", file=sys.stderr)
        return 1
    print(json.dumps({"added": added, "audit_writer_granted": granted, "privileges": privs}, indent=2))
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from metricguard.evaluation import run_benchmark

    return run_benchmark(get_settings(), planner_mode=args.planner, out=args.out, suite=args.suite)


def cmd_db_verify(_: argparse.Namespace) -> int:
    from metricguard.verification import verify, write_evidence

    try:
        report = verify(get_settings())
    except Db2Error as exc:
        print(f"ERROR: {exc} (SQLSTATE {exc.sqlstate})", file=sys.stderr)
        return 1
    paths = write_evidence(report)
    print(f"\nRESULT: {report['result']} ({report['failures']} failures). Evidence: {', '.join(paths)}")
    return 0 if report["result"] == "PASS" else 2


def cmd_expected(args: argparse.Namespace) -> int:
    """Write the oracle's expected results for every example plan (no database needed)."""
    from metricguard.core.examples import EXAMPLES
    from metricguard.seed import oracle
    from metricguard.seed.generator import generate

    ds = generate()
    out = {"seed": ds.seed, "dataset": ds.summary(), "examples": []}
    for ex in EXAMPLES:
        if ex.reference_plan is None:
            continue
        p = ex.reference_plan
        rows = oracle.compute(ds, metrics=p.metric_names, dimensions=p.dimensions, start=p.date_range.start_date,
                              end=p.date_range.end_date, filters={f.field: f.values for f in p.filters})
        out["examples"].append({"id": ex.id, "question": ex.question, "plan": p.model_dump(mode="json"),
                                "expected_rows_before_order_limit": rows})
    Path(args.out).write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(f"wrote {args.out}")
    return 0


def cmd_openapi(args: argparse.Namespace) -> int:
    from metricguard.api.app import app

    Path(args.out).write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"wrote {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="metricguard")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("health", help="check Db2 connectivity").set_defaults(func=cmd_health)

    db = sub.add_parser("db", help="database lifecycle").add_subparsers(dest="db_command", required=True)
    init = db.add_parser("init", help="create schema and load deterministic seed data")
    init.add_argument("--reset", action="store_true", help="drop the METRICGUARD schema first")
    init.set_defaults(func=cmd_db_init)
    db.add_parser("verify", help="run verification suite and write evidence/").set_defaults(func=cmd_db_verify)
    db.add_parser("migrate", help="non-destructive Stage 2 migration (audit columns, audit grants)").set_defaults(
        func=cmd_db_migrate)
    exp = db.add_parser("expected", help="write oracle expected results (no Db2 needed)")
    exp.add_argument("--out", default="db/expected/expected_results.json")
    exp.set_defaults(func=cmd_expected)

    ev = sub.add_parser("eval", help="run the planner + pipeline benchmark against live Db2")
    ev.add_argument("--planner", choices=["demo", "llm"], default="demo",
                    help="llm = the real provider selected by AI_PROVIDER (meta | anthropic); never demo")
    ev.add_argument("--suite", choices=["core", "unseen", "all"], default="core",
                    help="core = the 25 Stage 2 cases; unseen = 12 new prompts (LLM only); all = both")
    ev.add_argument("--out", default="evaluation/benchmark-results.json")
    ev.set_defaults(func=cmd_eval)

    oa = sub.add_parser("openapi", help="export OpenAPI schema")
    oa.add_argument("--out", default="docs/openapi.json")
    oa.set_defaults(func=cmd_openapi)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
