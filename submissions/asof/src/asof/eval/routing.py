"""Routing evaluation: does the router send each question to the right policy document, and ask when it should?

    python -m asof.eval.routing --split routing-dev                      # with the routing agent (the configured model)
    python -m asof.eval.routing --split routing-test --provider ollama
    python -m asof.eval.routing --split routing-test --no-agent           # Db2's vote alone, no model

Scored per case against the label (asof/eval/routing_cases.py):
    correct      routed to the expected document, or asked when the case expects a person (or another acceptable answer)
    misrouted    a question about one document routed to the other: the dangerous error, the draft would be checked
                 against the wrong policy (which in practice mostly escalates, since that policy's clauses do not cover it)
    asked        a question about one document handed to a person: safe, costs a specialist's time
    guessed      a case that needs a person (ambiguous, out of scope, mixed) routed to a document anyway

Each run writes docs/routing/<split>__<label>__<commit>__<time>.json, and docs/routing_eval.md is rebuilt from every
run file: the newest run of each configuration in full, the others listed.
Runs in a scratch schema, ASOF_ROUTE, seeded from the corpus, so the dev database's policy changes never move a result.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings

from .. import db, schema, seed
from ..config import Settings, get_settings
from ..embeddings import get_embeddings
from ..llm import build_llm
from ..router import AGENT_MARGIN, CLEAR_MARGIN, FAR, NEAR, Router
from . import routing_cases as rc
from .__main__ import _git_commit

ROUTE_SCHEMA = "ASOF_ROUTE"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = PROJECT_ROOT / "docs" / "routing"
REPORT = PROJECT_ROOT / "docs" / "routing_eval.md"


def outcome(expected: str, acceptable: tuple[str, ...], got: str) -> str:
    if got in acceptable:
        return "correct"
    if expected == rc.ASK:
        return "guessed"
    return "asked" if got == rc.ASK else "misrouted"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    routable = [r for r in rows if r["expected"] != rc.ASK]
    ask = [r for r in rows if r["expected"] == rc.ASK]

    def n(rs: list[dict[str, Any]], o: str) -> int:
        return sum(r["outcome"] == o for r in rs)
    cats: dict[str, dict[str, int]] = {}
    for r in rows:
        c = cats.setdefault(r["category"], {"cases": 0, "correct": 0, "misrouted": 0, "asked": 0, "guessed": 0})
        c["cases"] += 1
        c[r["outcome"]] += 1
    return {"cases": len(rows), "correct": n(rows, "correct"), "routable": len(routable),
            "routed_right": n(routable, "correct"), "misrouted": n(routable, "misrouted"), "asked": n(routable, "asked"),
            "ask_cases": len(ask), "ask_cases_asked": n(ask, "correct"), "guessed": n(ask, "guessed"),
            "methods": {m: sum(r["method"] == m for r in rows) for m in ("db2", "db2+agent", "ask")},
            "agent_calls": sum(r["agent"] is not None for r in rows),
            "latency_ms_p50": int(statistics.median(r["latency_ms"] for r in rows)) if rows else 0,
            "by_category": cats}


def prepare(settings: Settings, embeddings: Embeddings) -> None:
    with db.connection(settings, "admin") as conn:
        schema.drop(conn, ROUTE_SCHEMA)
        schema.install(conn, ROUTE_SCHEMA)
        seed.seed_policy(conn, embeddings, ROUTE_SCHEMA)
        seed.seed_faq(conn, embeddings, ROUTE_SCHEMA)  # the grants name every table, the FAQ store too
        schema.apply_grants(conn, settings.asof_app_user, settings.asof_editor_user, ROUTE_SCHEMA)


def run(router: Router, cases: list[rc.RoutingCase]) -> list[dict[str, Any]]:
    rows = []
    for c in cases:
        started = time.monotonic()
        r = router.route(c.question, c.draft, c.as_of)
        got = r.doc_id or rc.ASK
        rows.append({"id": c.id, "category": c.category, "expected": c.expected, "got": got,
                     "outcome": outcome(c.expected, c.acceptable, got), "method": r.method, "leader": r.leader,
                     "margin": round(r.margin, 4), "distances": {k: round(v, 4) for k, v in r.distances.items()},
                     "agent": r.agent, "reason": r.reason, "latency_ms": int((time.monotonic() - started) * 1000)})
        print(f"  {c.id} {c.category:13} expected {c.expected:15} got {got:15} {rows[-1]['outcome']:9} "
              f"via {r.method:9} margin {r.margin:.2f}", flush=True)
    return rows


def _rate(a: int, b: int) -> str:
    return f"{a} of {b}" if b else "none"


def render(results: list[dict[str, Any]]) -> str:
    lines = ["# Routing evaluation", "",
             "Which policy document a question and draft are about, decided by `asof/router.py`: Db2 ranks the clauses "
             "of both documents in force on the customer's date by `VECTOR_DISTANCE` and routes a clear lead with no "
             "model call; a close call goes to the routing agent, which can only confirm Db2's leader or hand the "
             "question to a person (reason `ROUTE_UNCERTAIN`, answered in the specialist inbox).", "",
             f"Thresholds, set on the 20-case dev split: route on Db2 alone when the leader is nearer by at least "
             f"{CLEAR_MARGIN} (cosine distance) and the other document's best clause is farther than {NEAR}; ask a person "
             f"when no clause of either document is nearer than {FAR}; between the two, the routing agent may confirm "
             f"Db2's leader only when it leads by at least {AGENT_MARGIN}. The 40-case test split was committed and its "
             "SHA-256 pinned in `6f3a15e`, before the router existed, and is never tuned on.", "",
             "**Misrouted** is the dangerous error: a draft checked against the other company's policy. **Asked** costs "
             "a specialist's time but is safe. **Guessed**: a question that needs a person (ambiguous, out of scope, or "
             "needing both documents) routed to one document anyway.", "",
             "Whether the routing agent runs depends on the model (`ASOF_ROUTER_AGENT=auto`, the default): only a model "
             "whose run on the pinned test split misrouted nothing and guessed on none of the questions that need a "
             "person (`router.MEASURED`, held to these run files by a test). The default hosted model qualifies. The "
             "local 7B model recovered the same shared-vocabulary cases but guessed on ambiguous questions, so with it "
             "close calls go to a person, the safe failure. The agent's model client has no local fallback, so a "
             "failed routing call also asks a person. A deployment measures its own model with "
             "`python -m asof.eval.routing --split routing-test --provider ...`.", ""]
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for r in sorted(results, key=lambda x: x["started_at"]):
        latest[(r["split"], r["label"])] = r  # the newest run of each split and configuration is shown in full
    earlier = [r for r in results if latest[(r["split"], r["label"])] is not r]
    test = sorted((r for r in latest.values() if r["split"] == "routing-test"),
                  key=lambda x: (x.get("model") is not None, "ollama" in (x.get("model") or "")))
    if test:
        lines += ["## The test split, side by side", "",
                  "| Configuration | Routed right | **Misrouted** | Asked, document was clear | Asked when it should "
                  "| Guessed | Agent calls | Median latency |", "|---|---|---|---|---|---|---|---|"]
        for r in test:
            t = r["summary"]
            lines.append(f"| {r['label']} | {_rate(t['routed_right'], t['routable'])} | "
                         f"**{_rate(t['misrouted'], t['routable'])}** | {_rate(t['asked'], t['routable'])} | "
                         f"{_rate(t['ask_cases_asked'], t['ask_cases'])} | {_rate(t['guessed'], t['ask_cases'])} | "
                         f"{t['agent_calls']} | {t['latency_ms_p50']} ms |")
        lines.append("")
    for r in sorted(latest.values(), key=lambda x: (x["split"] != "routing-test", x.get("model") is not None,
                                                     "ollama" in (x.get("model") or ""), x["started_at"])):
        s = r["summary"]
        lines += [f"## {r['split']}: {r['label']}, run {r['started_at'][:10]} at `{r['git_commit']}`", "",
                  "| Measure | Result |", "|---|---|",
                  f"| Routed to the right document | {_rate(s['routed_right'], s['routable'])} |",
                  f"| **Misrouted** (other document) | **{_rate(s['misrouted'], s['routable'])}** |",
                  f"| Asked a person, document was clear | {_rate(s['asked'], s['routable'])} |",
                  f"| Asked a person when it should | {_rate(s['ask_cases_asked'], s['ask_cases'])} |",
                  f"| Guessed when it should have asked | {_rate(s['guessed'], s['ask_cases'])} |",
                  f"| Decided by Db2 alone / with the agent / asked | {s['methods']['db2']} / {s['methods']['db2+agent']} / "
                  f"{s['methods']['ask']} |",
                  f"| Routing agent calls | {s['agent_calls']} |",
                  f"| Median latency | {s['latency_ms_p50']} ms |", "",
                  "| Category | Cases | Correct | Misrouted | Asked | Guessed |", "|---|---|---|---|---|---|"]
        lines += [f"| {cat} | {c['cases']} | {c['correct']} | {c['misrouted']} | {c['asked']} | {c['guessed']} |"
                  for cat, c in r["summary"]["by_category"].items()]
        wrong = [x for x in r["rows"] if x["outcome"] != "correct"]
        if wrong:
            lines += ["", "Not as labelled: " + "; ".join(
                f"`{x['id']}` ({x['category']}) expected {x['expected']}, got {x['got']} via {x['method']}"
                + (f", agent said {x['agent']['document']}" if x["agent"] else "") for x in wrong) + "."]
        lines.append("")
    if earlier:
        lines += ["## Other runs", "", "Earlier or repeated runs of a split and configuration shown above. Every run "
                  "is kept; the newest is shown in full.", ""]
        for r in sorted(earlier, key=lambda x: (x["split"], x["started_at"])):
            s = r["summary"]
            lines.append(f"- {r['split']}, {r['label']}, {r['started_at'][:10]} at `{r['git_commit']}`: "
                         f"{_rate(s['routed_right'], s['routable'])} routed right, {s['misrouted']} misrouted, "
                         f"{s['asked']} asked; {_rate(s['ask_cases_asked'], s['ask_cases'])} asked when they should, "
                         f"{s['guessed']} guessed.")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.eval.routing")
    p.add_argument("--split", choices=list(rc.SPLITS), required=True)
    p.add_argument("--provider", choices=["openrouter", "ollama", "openai_compatible"])
    p.add_argument("--model")
    p.add_argument("--no-agent", action="store_true", help="Db2's vote alone: close calls go to a person")
    args = p.parse_args(argv)
    if args.split in rc.FROZEN and rc.split_sha256(args.split) != rc.FROZEN[args.split]:
        print(f"Refusing to run: the frozen {args.split} split has changed since it was pinned.")
        return 2
    settings = get_settings()
    llm = None
    if not args.no_agent:
        provider = args.provider or settings.llm_provider
        if provider == "replay":
            print("Refusing to run: the routing agent is measured with a live model (or use --no-agent).")
            return 2
        llm = build_llm(settings, provider=provider, model=args.model, fallback=False)
    embeddings = get_embeddings(settings.embedding_model)
    prepare(settings, embeddings)
    pool = db.ConnectionPool(settings, "app")
    label = "Db2 vote only (no model)" if llm is None else f"Db2 vote + routing agent ({llm.info})"
    print(f"Routing {args.split}: {label}", flush=True)
    started = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        rows = run(Router(embeddings, pool.connect, ROUTE_SCHEMA, llm), rc.load(args.split))
    finally:
        pool.close()
        with db.connection(settings, "admin") as conn:
            schema.drop(conn, ROUTE_SCHEMA)
    result = {"split": args.split, "label": label, "model": llm.info if llm else None, "started_at": started,
              "git_commit": _git_commit(), "cases_sha256": rc.split_sha256(args.split),
              "thresholds": {"clear_margin": CLEAR_MARGIN, "near": NEAR, "far": FAR, "agent_margin": AGENT_MARGIN},
              "summary": summarize(rows), "rows": rows}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = "db2-only" if llm is None else llm.info.replace(":", "_").replace("/", "_")
    stamp = started.replace("-", "").replace(":", "")[:15]  # repeated runs at one commit are all kept
    (OUT_DIR / f"{args.split}__{slug}__{result['git_commit']}__{stamp}.json").write_text(
        json.dumps(result, indent=1, default=str))
    REPORT.write_text(render([json.loads(f.read_text()) for f in sorted(OUT_DIR.glob("*.json"))]))
    s = result["summary"]
    print(f"{s['routed_right']}/{s['routable']} routed right, {s['misrouted']} misrouted, {s['asked']} asked; "
          f"{s['ask_cases_asked']}/{s['ask_cases']} asked when they should, {s['guessed']} guessed. Wrote {REPORT.name}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
