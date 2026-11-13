"""Run the demonstration's questions through AsOf's full check, once, and publish them.

    python -m asof.eval.real.run              # rebuild US-DOT-REFUNDS in ASOF_REAL from the records, then ask
    python -m asof.eval.real.run --render     # rewrite the tables in docs/eval/real-regulation.md

Each question is one check, as POST /api/gate makes it: the question, the draft, as_of_date = the question's date,
doc_id US-DOT-REFUNDS, channel eval. Writes docs/eval/real/run.json and the generated block of
docs/eval/real-regulation.md. Refuses to overwrite a recorded run: it is run once.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from typing import Any

from ... import db
from ...config import PROJECT_ROOT, get_settings
from ...domains import DOT
from ...gate import Gate, GateRequest
from ...llm import build_llm
from ..unseen.docblocks import replace_blocks
from . import onboard
from .questions import QUESTIONS

OUT = PROJECT_ROOT / "docs" / "eval" / "real" / "run.json"
REPORT = PROJECT_ROOT / "docs" / "eval" / "real-regulation.md"


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def table(run: dict[str, Any]) -> str:
    lines = [f"Run {run['started_at']} at commit `{run['git_commit']}`, {run['provider']} `{run['model']}`, schema "
             f"`{run['schema']}`, ledger chain {run['ledger_chain']}.", "",
             "| Question | Date | Draft says | What the excerpt says on that date | AsOf | Cited (clause, version, in force) |",
             "|---|---|---|---|---|---|"]
    for r in run["records"]:
        lines.append(f"| {r['id']} | {r['as_of']} | {r['draft']} | {r['reading']} | **{r['decision']}** "
                     f"({r['reason_code']}) | {', '.join(r['cited']) or 'none'} |")
    lines += ["", "What AsOf sent the customer:", ""]
    for r in run["records"]:
        lines.append(f"- **{r['id']}** ({r['as_of']}): {r['final_answer']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.eval.real.run", description=__doc__.split("\n\n")[0])
    p.add_argument("--render", action="store_true")
    args = p.parse_args(argv)
    if args.render:
        replace_blocks(REPORT, {"answers": table(json.loads(OUT.read_text(encoding="utf-8")))}, "# Real regulation\n")
        return 0
    if OUT.exists():
        print(f"Refusing to run: {OUT.name} exists, and the demonstration is run once.")
        return 2
    from ...embeddings import get_embeddings

    settings = get_settings()
    if settings.llm_provider == "replay":
        print("Refusing to run: this needs a live model.")
        return 2
    embeddings = get_embeddings(settings.embedding_model)
    target = onboard.DEFAULT_SCHEMA
    onboard.rebuild(settings, target, embeddings)
    llm = build_llm(settings, fallback=False)
    pool = db.ConnectionPool(settings, "app")
    started = datetime.now(UTC)
    records = []
    for q in QUESTIONS:
        result = Gate(llm, embeddings, pool.connect, target).check(GateRequest(q.question, q.draft, q.as_of, DOT.doc_id,
                                                                               "eval"))
        cited: list[str] = []
        for c in result.claims + result.rewrite_claims:
            if c.clause:
                ref = (f"{c.clause.clause_id} {c.clause.version_label} (from {c.clause.bus_start.isoformat()}): "
                       f"{c.clause.title}")
                if ref not in cited:
                    cited.append(ref)
        records.append({"id": q.id, "as_of": q.as_of.isoformat(), "question": q.question, "draft": q.draft,
                        "reading": q.reading, "decision": result.decision, "reason_code": result.reason_code,
                        "final_answer": result.final_answer.split("\n\nPolicy references")[0], "cited": cited,
                        "claims": [f"p{p}#{c.claim_no} {c.verdict} (llm {c.llm_verdict}, rule {c.rule_check}): "
                                   f"{c.text[:160]}" for p, cs in ((1, result.claims), (2, result.rewrite_claims))
                                   for c in cs],
                        "latency_ms": result.latency_ms})
        print(f"  {q.id} {q.as_of} {result.decision} {result.reason_code}", flush=True)
    from ...ledger import verify_chain

    with db.connection(settings, "app") as conn:
        chain = verify_chain(conn, target)
    run = {"started_at": started.isoformat(timespec="seconds"), "git_commit": _commit(), "provider": settings.llm_provider,
           "model": llm.model_name, "schema": target, "ledger_chain": chain.status, "records": records}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(run, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    replace_blocks(REPORT, {"answers": table(run)}, "# Real regulation\n")
    print(f"wrote {OUT.relative_to(PROJECT_ROOT)} and {REPORT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
