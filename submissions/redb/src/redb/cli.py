"""Command line: python -m redb setup|workload|analyze|ui"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import uuid
from pathlib import Path


def _db():
    from .db import Db
    return Db()


def cmd_setup(a) -> None:
    from . import seed
    from .config import get_settings
    db = _db()
    for m in seed.setup(db, scale=a.scale, reset=a.reset, embed_dim=get_settings().embed_dim, reseed=a.reseed):
        print(" -", m)
    print("setup complete")


def cmd_workload(a) -> None:
    from . import workload
    for k, ms in workload.run(_db(), repeat=a.repeat, flush=not a.no_flush).items():
        print(f" {k}: {ms:8.1f} ms avg")


def print_report(state: dict) -> None:
    rep = state.get("report") or {}
    print("\n=== Proposals ===")
    for p in state.get("proposals", []):
        print(f" [{p['id']}] {p['kind']:8} verified={p['verified']!s:5} {p['title']}\n      {p['evidence']}")
    if rep:
        print("\n=== Measured results (median ms) ===")
        for r in rep["per_statement"]:
            after = f"{r['ms_after']:9.1f}" if r.get("ms_after") is not None else "        -"
            print(f" {r['case_id']:4} before {r['ms_before']:9.1f}  after {after}  gain {r.get('gain_pct')}")
        if rep.get("reduction_pct") is not None:
            print(f" TOTAL {rep['ms_before']:.1f} ms → {rep['ms_after']:.1f} ms ({rep['reduction_pct']}% less)")
        print("\n" + rep["narrative"])
    print("\n=== Agent log ===")
    for line in state.get("log", []):
        print(" ", line)


def cmd_analyze(a) -> None:
    from .agent import build_graph, resume, run_until_approval
    from .llm import Brain
    from .toolkit import Toolkit
    brain = Brain()
    tk = Toolkit(embed=brain.embed)
    print(f"LLM: {brain.mode}")
    if tk.memory.warning:
        print("WARNING:", tk.memory.warning)
    graph = build_graph(tk, brain, approver="cli --approve-all" if a.approve_all else "cli")
    tid = str(uuid.uuid4())
    state = run_until_approval(graph, tid, a.limit)
    if not state.get("statements"):
        print("\nNo statements found in the package cache. Run `python -m redb workload` first. If you did, the "
              "database is probably not activated (Db2 then clears the cache when the last connection closes); run:\n"
              "  docker exec redb-db2 su - db2inst1 -c \"db2 activate db REDB\"")
    for c in state.get("cases", []):
        d = c["diagnosis"]
        print(f"\n[{c['case_id']}] {c['metrics']['avg_ms']:.1f} ms avg, {d['severity']}: {d['headline']}")
        for s in c.get("similar", [])[:1]:
            print(f"   similar past case #{s['case_id']} ({s['similarity']}): {s['fix_kind']} gave {s['gain_pct']}%")
    if a.approve_all:
        ids = [p["id"] for p in state.get("proposals", []) if p["verified"]]
        state = resume(graph, tid, ids)
    print_report(state)
    if a.report:
        from .report import to_markdown
        Path(a.report).write_text(to_markdown(state, brain.mode), encoding="utf-8")
        print(f"\nreport written to {a.report}")


def cmd_ui(_a) -> None:
    app = Path(__file__).resolve().parent.parent / "app.py"
    sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)]))


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(prog="redb", description="reDB: AI agent that tunes IBM Db2 and proves every fix")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup", help="create reDB objects and the RETAIL demo schema")
    s.add_argument("--scale", type=float, default=1.0)
    s.add_argument("--reset", action="store_true", help="drop REDB_IX_%% indexes so the demo can be replayed")
    s.add_argument("--reseed", action="store_true", help="drop and regenerate the RETAIL data (use with --scale)")
    w = sub.add_parser("workload", help="run the demo workload")
    w.add_argument("--repeat", type=int, default=5)
    w.add_argument("--no-flush", action="store_true", help="keep existing package cache")
    an = sub.add_parser("analyze", help="run the agent headless")
    an.add_argument("--approve-all", action="store_true", help="apply every proven proposal")
    an.add_argument("--limit", type=int, default=8)
    an.add_argument("--report", metavar="FILE", help="also write the run as a Markdown report")
    sub.add_parser("ui", help="launch the Streamlit app")
    a = p.parse_args(argv)
    if a.scale <= 0 if a.cmd == "setup" else False:
        p.error("--scale must be positive")
    {"setup": cmd_setup, "workload": cmd_workload, "analyze": cmd_analyze, "ui": cmd_ui}[a.cmd](a)
