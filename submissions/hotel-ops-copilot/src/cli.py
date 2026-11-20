"""Command-line interface.

    python src/cli.py ask "Which nights next week are weakest?"
    python src/cli.py actions            # list the approval queue
    python src/cli.py preview 3          # dry-run action #3 inside a Db2 transaction, then roll back
    python src/cli.py approve 3          # apply action #3 (manager identity)
    python src/cli.py rollback 3         # undo it with Db2 time travel
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hotelops import manager  # noqa: E402
from hotelops.agents import ask  # noqa: E402
from hotelops.config import load_settings  # noqa: E402


def _print_event(ev: dict) -> None:
    kind = ev.get("type")
    if kind == "route":
        print(f"  [router] -> {ev['route']} ({ev['reason']})")
    elif kind == "agent_start":
        print(f"  [{ev['agent']}] started")
    elif kind == "tool":
        mark = "ok" if ev["ok"] else "ERR"
        args = json.dumps(ev["input"], default=str)[:160]
        print(f"  [{ev['agent']}] {ev['tool']} {mark} {ev['latency_ms']}ms {args}")
    elif kind == "model_switch":
        print(f"  [llm] daily quota used up on {ev['old']} -> continuing on {ev['new']}")
    elif kind == "proposal":
        tag = f"#{ev['action_id']}" if ev["action_id"] else "REJECTED BY DB2"
        print(f"  [proposal] {tag} {ev['action_type']} {json.dumps(ev['payload'])}: {ev['message']}")


def main() -> None:
    p = argparse.ArgumentParser(description="Hotel Ops Copilot CLI")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ask")
    a.add_argument("question")
    sub.add_parser("actions")
    for name in ("preview", "approve", "reject", "rollback"):
        sp = sub.add_parser(name)
        sp.add_argument("action_id", type=int)
    args = p.parse_args()
    who = os.getenv("MANAGER_NAME", "duty.manager")

    if args.cmd == "ask":
        reason = load_settings().llm.missing_credentials()
        if reason:
            sys.exit(f"No LLM configured: {reason}. The actions/approve/reject/rollback commands work without it.")
        try:
            result = ask(args.question, on_event=_print_event)
        except Exception as exc:
            from hotelops.llm import friendly_llm_error

            if friendly_llm_error(exc):
                sys.exit(friendly_llm_error(exc))
            raise
        print(f"\n=== {result['route']} | run {result['run_id']} | {result['llm_calls']} LLM calls on "
              f"{result['model']} ===\n{result['answer']}")
    elif args.cmd == "actions":
        for row in manager.list_actions():
            print(f"#{row['ACTION_ID']:<4} {row['ACTION_TYPE']:<13} {row['STATUS']:<11} {row['PAYLOAD']}")
    elif args.cmd == "preview":
        from hotelops.preview import preview_action

        pv = preview_action(args.action_id)
        print(f"[dry run, rolled back] would be {pv['status']}: {pv['summary']}")
        for w in pv["warnings"]:
            print(f"  WARNING: {w}")
        for row in pv["rows"]:
            print(f"  {json.dumps(row, default=str)}")
    elif args.cmd == "approve":
        print(manager.approve(args.action_id, who))
    elif args.cmd == "reject":
        manager.reject(args.action_id, who)
        print("rejected")
    elif args.cmd == "rollback":
        print(manager.rollback(args.action_id, who))


if __name__ == "__main__":
    main()
