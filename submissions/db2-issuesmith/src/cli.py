"""IssueSmith command line.

    python src/cli.py check              # Db2 connectivity + VECTOR support + LLM status
    python src/cli.py init-db [--reset]  # create schema, tables, views, procedure
    python src/cli.py seed-kb            # load data/knowledge_base into Db2 (DB2VS)
    python src/cli.py analyze <log> [--steps "..."] [--out issue.md]
    python src/cli.py demo               # init + seed + analyze every sample log
    python src/cli.py stats              # print analytics views
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from issuesmith.agents.graph import run_pipeline  # noqa: E402
from issuesmith.config import KNOWLEDGE_DIR, SAMPLE_LOG_DIR, get_settings  # noqa: E402
from issuesmith.db import Db2Error  # noqa: E402
from issuesmith.wiring import build_app  # noqa: E402


def _print_table(rows: list[dict]) -> None:
    if not rows:
        print("  (no rows)")
        return
    cols = list(rows[0])
    print("  " + " | ".join(cols))
    for r in rows:
        print("  " + " | ".join(str(r[c])[:60] for c in cols))


def cmd_check(args) -> int:
    s = get_settings()
    app = build_app(s, with_kb=False)
    print(f"Connected to Db2 database {s.db2_database} at {s.db2_host}:{s.db2_port}")
    try:
        print(f"Db2 service level: {app.repo.db2_version()}")
    except Exception:
        pass
    try:
        d = app.repo.check_vector_support()
        print(f"VECTOR support OK (test cosine distance = {d:.3f})")
    except Exception as exc:
        print(f"VECTOR support NOT available (needs Db2 12.1.2+): {exc}")
        return 1
    print(f"Embeddings: {type(app.embeddings).__name__}")
    print(f"LLM provider: {app.llm.name}")
    return 0


def cmd_init(args) -> int:
    s = get_settings()
    app = build_app(s, with_kb=False)
    dim = len(app.embeddings.embed_query("dimension probe"))
    for msg in app.repo.init_schema(reset=args.reset, dim=dim):
        print("  " + msg)
    print(f"Schema {s.db2_schema} ready (embedding dimension {dim}).")
    return 0


def cmd_seed(args) -> int:
    app = build_app(get_settings(), with_kb=True)
    if app.kb is None:
        print("Knowledge base could not be initialised (see warnings above).")
        return 1
    n = app.kb.seed(KNOWLEDGE_DIR)
    print(f"Loaded {n} knowledge documents into {app.kb.table} (DB2VS, COSINE).")
    return 0


def _analyze_file(app, path: Path, steps: str = "", repro: str = "") -> dict:
    state = run_pipeline(app.services(), path.read_text(encoding="utf-8", errors="replace"), path.name, steps, repro)
    print(f"\n=== {path.name} -> incident #{state['incident_id']} ===")
    for t in state["trace"]:
        print(f"  [{t['agent']:<12}] {t['ms']:>6} ms  {t['detail']}")
    print(f"\nTITLE: {state['title']}\n")
    return state


def cmd_analyze(args) -> int:
    app = build_app(get_settings())
    state = _analyze_file(app, Path(args.log), args.steps, args.repro)
    print(state["body"])
    if args.out:
        Path(args.out).write_text(f"# {state['title']}\n\n{state['body']}", encoding="utf-8")
        print(f"Saved to {args.out}")
    return 0


def cmd_demo(args) -> int:
    s = get_settings()
    setup = build_app(s, with_kb=False)
    dim = len(setup.embeddings.embed_query("dimension probe"))
    setup.repo.init_schema(reset=args.reset, dim=dim)
    app = build_app(s)  # fresh connection; DB2VS (re)creates KB_DOCS after a reset
    if app.kb is not None:
        print(f"Knowledge docs loaded: {app.kb.seed(KNOWLEDGE_DIR)}")
    for path in sorted(SAMPLE_LOG_DIR.glob("*.log")):
        _analyze_file(app, path)
    print("\nRe-running the first log to show duplicate detection:")
    first = sorted(SAMPLE_LOG_DIR.glob("*.log"))[0]
    state = _analyze_file(app, first)
    print(f"duplicate_of = {state.get('duplicate_of')}")
    return 0


def cmd_stats(args) -> int:
    app = build_app(get_settings(), with_kb=False)
    for name, fn in [("Category stats", app.repo.category_stats), ("Top error signatures", app.repo.top_signatures),
                     ("Agent performance", app.repo.agent_performance), ("Environment breakdown", app.repo.env_breakdown)]:
        print(f"\n{name}:")
        _print_table(fn())
    return 0


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="issuesmith", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    ip = sub.add_parser("init-db")
    ip.add_argument("--reset", action="store_true", help="drop and recreate all IssueSmith tables")
    ip.set_defaults(fn=cmd_init)
    sub.add_parser("seed-kb").set_defaults(fn=cmd_seed)
    ap = sub.add_parser("analyze")
    ap.add_argument("log")
    ap.add_argument("--steps", default="", help="your reproduction steps, one per line")
    ap.add_argument("--repro", default="", help="Every time / Intermittently / Once")
    ap.add_argument("--out", default="")
    ap.set_defaults(fn=cmd_analyze)
    dp = sub.add_parser("demo")
    dp.add_argument("--reset", action="store_true")
    dp.set_defaults(fn=cmd_demo)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    args = p.parse_args()
    try:
        return args.fn(args)
    except Db2Error as exc:
        print(f"\nDb2 problem: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
