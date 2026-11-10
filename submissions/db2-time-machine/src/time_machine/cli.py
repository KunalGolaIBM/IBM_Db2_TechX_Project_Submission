"""Command line interface: ``python -m time_machine <command>``."""
from __future__ import annotations

import argparse
import json
import sys

from .config import Settings

BOLD, DIM, GREEN, RED, YELLOW, CYAN, RESET = "\033[1m", "\033[2m", "\033[32m", "\033[31m", "\033[33m", "\033[36m", "\033[0m"


def _gateway(settings: Settings):
    from .db import Db2Gateway
    return Db2Gateway(settings)


def cmd_doctor(args, settings: Settings) -> int:
    from .llm import LLM
    print(f"{BOLD}Db2 Time Machine - environment check{RESET}")
    ok = True
    try:
        import ibm_db_dbi  # noqa: F401
        print(f"{GREEN}ok{RESET}   ibm_db driver importable")
    except Exception as exc:
        print(f"{RED}FAIL{RESET} ibm_db driver: {exc}")
        return 1
    gw = _gateway(settings)
    try:
        info = gw.ping()
        print(f"{GREEN}ok{RESET}   connected to {info['server']} (schema {info['schema']}, {info['latency_ms']} ms)")
    except Exception as exc:
        print(f"{RED}FAIL{RESET} cannot connect to Db2 at {settings.db_host}:{settings.db_port}/{settings.db_name}: {exc}")
        return 1
    try:
        rows = gw.read("SELECT TABNAME, TEMPORALTYPE FROM SYSCAT.TABLES WHERE TABSCHEMA = :s AND TEMPORALTYPE <> 'N'",
                       {"s": settings.db_schema})
        names = [r["tabname"] for r in rows]
        if "ORDER_ITEMS" in names:
            print(f"{GREEN}ok{RESET}   system-period temporal table ORDER_ITEMS found")
        else:
            print(f"{YELLOW}warn{RESET} temporal table ORDER_ITEMS not found; run: python -m time_machine reset-demo")
            ok = False
    except Exception as exc:
        print(f"{YELLOW}warn{RESET} could not read the catalog: {exc}")
        ok = False
    llm = LLM.from_settings(settings)
    print(f"{GREEN}ok{RESET}   LLM: {llm.label}")
    return 0 if ok else 2


def cmd_init_db(args, settings: Settings) -> int:
    from .demo import init_schema
    init_schema(_gateway(settings), reset=args.reset)
    print(f"{GREEN}Schema {settings.db_schema} ready (temporal tables, triggers, audit and report tables).{RESET}")
    return 0


def cmd_seed(args, settings: Settings) -> int:
    from .demo import seed_baseline
    stats = seed_baseline(_gateway(settings))
    print(f"{GREEN}Baseline loaded:{RESET} {stats}. KPI snapshot taken.")
    return 0


def cmd_reset_demo(args, settings: Settings) -> int:
    from .demo import init_schema, seed_baseline
    gw = _gateway(settings)
    init_schema(gw, reset=True)
    stats = seed_baseline(gw)
    print(f"{GREEN}Demo reset.{RESET} {stats}")
    return 0


def cmd_inject(args, settings: Settings) -> int:
    from .demo import inject
    print(f"{YELLOW}Injected:{RESET} {inject(_gateway(settings), args.fault)}")
    return 0


def _print_report(r: dict) -> None:
    v, m = r["verdict"], r["metric"]
    colour = GREEN if v["status"] == "confirmed" else YELLOW
    print(f"\n{BOLD}INCIDENT REPORT{RESET}  {DIM}run {r['run_id']} | {r['llm']}{RESET}")
    print(f"{BOLD}Question:{RESET} {r['question']}")
    print(f"{BOLD}Window:{RESET}   {r['window']['label']}")
    print(f"{BOLD}Revenue:{RESET}  {m['start']} -> {m['end']}  ({m['delta']}, {m['pct']}%)")
    print(f"{BOLD}Verdict:{RESET}  {colour}{v['status'].upper()}{RESET} (confidence: {v['confidence']})")
    rc = r.get("root_cause")
    if rc:
        print(f"{BOLD}Root cause:{RESET} {rc['title']} | {rc['rows_affected']} rows | by {rc['actor'] or 'unknown'} "
              f"| at {str(rc['when'])[:19]} | txn {rc['transaction']} | impact {rc['impact']}")
    print(f"\n{BOLD}Hypotheses tested:{RESET}")
    for t in r["hypotheses_tested"]:
        mark = f"{GREEN}CONFIRMED{RESET}" if t["confirmed"] else f"{RED}rejected{RESET}"
        print(f"  - {t['title']}: {mark}  {DIM}{t['reason']}{RESET}")
    print(f"\n{BOLD}Summary:{RESET} {r['narrative']}")
    for w in r["warnings"]:
        print(f"{YELLOW}Warning:{RESET} {w}")
    print(f"\n{BOLD}Evidence SQL:{RESET}")
    for e in r["evidence_sql"]:
        print(f"  {CYAN}-- {e['label']}{RESET}\n  {e['sql']}\n")


def cmd_investigate(args, settings: Settings) -> int:
    from .graph import investigate
    from .repository import Db2Repository
    repo = Db2Repository(_gateway(settings))

    def live(ev: dict) -> None:
        if ev["type"] == "agent" and ev["status"] == "running" and not args.json:
            print(f"{DIM}[{ev['agent']}] {ev['message']}...{RESET}", file=sys.stderr)

    report = investigate(repo, args.question, settings=settings, hours=args.hours, since=args.since,
                         until=args.until, emit=live)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_report(report)
    return 0


def cmd_serve(args, settings: Settings) -> int:
    import uvicorn
    from .api import create_app
    uvicorn.run(create_app(settings=settings), host=args.host, port=args.port, log_level="info")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="time_machine", description="Db2 Time Machine - root-cause analyst for data changes")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="check driver, Db2 connection, temporal tables and LLM mode").set_defaults(fn=cmd_doctor)
    s = sub.add_parser("init-db", help="create the schema (temporal tables, triggers, audit tables)")
    s.add_argument("--reset", action="store_true", help="drop existing objects first")
    s.set_defaults(fn=cmd_init_db)
    sub.add_parser("seed", help="load the baseline dataset and take a KPI snapshot").set_defaults(fn=cmd_seed)
    sub.add_parser("reset-demo", help="init-db --reset followed by seed").set_defaults(fn=cmd_reset_demo)
    s = sub.add_parser("inject", help="inject a data fault (one SQL transaction)")
    s.add_argument("fault", choices=["price", "duplicate", "quantity", "deleted"])
    s.set_defaults(fn=cmd_inject)
    s = sub.add_parser("investigate", help="ask why a number changed")
    s.add_argument("question")
    s.add_argument("--hours", type=float, help="look back this many hours instead of since the last KPI snapshot")
    s.add_argument("--since")
    s.add_argument("--until")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_investigate)
    s = sub.add_parser("serve", help="start the web UI and API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(fn=cmd_serve)
    args = p.parse_args(argv)
    return args.fn(args, Settings.from_env())
