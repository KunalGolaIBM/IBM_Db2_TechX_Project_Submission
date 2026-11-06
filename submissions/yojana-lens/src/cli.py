"""Command line entry point.

    python -m src.cli init     # create schema + stored procedure
    python -m src.cli seed     # load corpus and embeddings (idempotent)
    python -m src.cli ask "..."# run the agent end to end, print a summary
    python -m src.cli stats    # corpus counters straight from Db2
    python -m src.cli reset    # drop and rebuild everything (dev only)
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional, Sequence

from . import db


def _cmd_init(_args) -> int:
    db.init_db()
    return 0


def _cmd_reset(_args) -> int:
    db.reset_db()
    return 0


def _cmd_seed(args) -> int:
    from .ingest import seed

    db.init_db(verbose=False)
    if args.if_empty:
        with db.connect() as conn:
            row = db.fetch_one(conn, "SELECT COUNT(*) AS n FROM schemes")
        if row and int(row["n"]) > 0:
            print(f"[seed] corpus already loaded ({row['n']} schemes) - skipping")
            return 0
    seed()
    return 0


def _cmd_stats(_args) -> int:
    with db.connect() as conn:
        row = db.fetch_named_one(conn, "corpus_stats", {})
    print(json.dumps(row, indent=2, default=str))
    return 0


def _cmd_ask(args) -> int:
    from .agent import run

    text = " ".join(args.text)
    state = run(text)
    if args.json:
        print(json.dumps(state, indent=2, default=str))
        return 0

    print(f"\nrun {state['run_id']}  ({state.get('duration_ms', 0)} ms, "
          f"{state.get('engine')}, {'mock' if state.get('llm_mode') else ''} narration)")
    print("-" * 72)
    for item in state.get("results", []):
        print(f"[{item['label']:<12}] {item['name']}  ({item['readiness']}% readiness)")
        if item.get("narrative"):
            print(f"               {item['narrative']}")
    counts = state.get("counts", {})
    print("-" * 72)
    print("  ".join(f"{k}={v}" for k, v in counts.items()))
    if state.get("filtered_by_residency"):
        print(f"  filtered by residency: {state['filtered_by_residency']}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="yojana-lens")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create schema and stored procedure").set_defaults(func=_cmd_init)
    sub.add_parser("reset", help="drop and recreate all objects").set_defaults(func=_cmd_reset)
    sub.add_parser("stats", help="print corpus counters").set_defaults(func=_cmd_stats)

    seed_parser = sub.add_parser("seed", help="load the corpus")
    seed_parser.add_argument("--if-empty", action="store_true",
                             help="skip when schemes are already present")
    seed_parser.set_defaults(func=_cmd_seed)

    ask_parser = sub.add_parser("ask", help="run the agent for one description")
    ask_parser.add_argument("text", nargs="+")
    ask_parser.add_argument("--json", action="store_true", help="dump the full state")
    ask_parser.set_defaults(func=_cmd_ask)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except db.Db2Error as exc:
        print(f"[db2] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
