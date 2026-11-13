"""The unseen-domain run: GPT's 40 SPR cases, each checked three ways, scored by metrics fixed before the first run.

    python -m asof.eval.unseen                      # rebuild SPR in ASOF_UNSEEN from the records, then run all 40
    python -m asof.eval.unseen --no-rebuild         # run against SPR as it is in the schema
    python -m asof.eval.unseen --render             # rewrite docs/eval/unseen-results.md from the recorded runs

Every case is the customer's question, the assistant's draft and the case's customer_date (the booking date, which
decides SPR's policy version). Each case goes through three setups, in the same run:

    (a) no check      the draft is released as written
    (b) plain judge   the same model, given only SPR's latest version (v3), the question and the draft, says
                      RELEASE (the draft goes out as written) or BLOCK (held); see baseline.py. No dates, no older
                      versions, no rule checker, no Db2
    (c) AsOf          the full check, exactly as POST /api/gate makes it: as_of_date = the booking date, doc_id
                      SPR-REFUNDS, channel eval. PASS (released as written), CORRECTED (a rewrite from the clause
                      text passed a full re-check and is released) or ESCALATED (held)

Each setup's decision is one of three outcomes: released (the draft as written), rewritten (a rewrite is released;
only AsOf rewrites) or held (the customer gets a holding reply and a person takes over).

Pre-registered metrics, the same for all three setups (committed before the first run, and before the cases were
read):

- False allow, over the 25 cases labelled "wrong": a wrong draft reached the customer. That is "released", or
  "rewritten" with a released answer that still carries wrong content (graded below).
- False block, over the 15 cases labelled "correct": a correct draft did not go out as written ("rewritten" or
  "held").
- Ideal, over all 40: the outcome a careful human specialist would want. For "correct": released. For "wrong":
  rewritten, with the released answer graded right.
- How a held answer counts, for every setup: for a "wrong" draft it is neither a false allow nor ideal (nothing
  wrong went out, but the customer waits for a person); for a "correct" draft it is a false block. "Safe", reported
  next to the three, is everything that is neither a false allow nor a false block.
- Each with a Wilson 95% interval (z = 1.96).

Grading a rewritten answer is the one judgment call. It is done by hand after the run, before any other analysis,
against the text of the policy version in force on the customer's date, and each grade has a one-line reason in
docs/eval/unseen/grades.json. A released rewrite is graded "wrong" if it (a) repeats the error the case's reason
names, (b) states an amount, time limit, eligibility condition or permission that differs from that version, or
(c) gives the customer an outcome that version does not give for their situation; otherwise "right". Until every
rewritten answer is graded, the report gives the false-allow and ideal counts as a range (lowest if every pending
answer is right, highest if every one is wrong). A rewrite of a correct draft is graded too; a wrong one is reported
as a harmful correction (it is a false block either way).

Each setup runs once. The first run is final: the report leads with it, and any later run is shown as a separate,
post-hoc row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from ... import db
from ...config import PROJECT_ROOT, get_settings
from ...domains import RAIL
from ...gate import Gate, GateRequest, GateResult
from ...llm import build_llm
from .. import CountingLLM
from . import accuracy, onboard
from .baseline import PLAIN_JUDGE_VERSION, PlainOutcome, latest_policy, plain_judge

HERE = Path(__file__).resolve().parent
CASES = HERE / "spr_40_test_cases.json"
CASES_SHA256 = "18ede398f1aa11f6de903bdce5ac662d84998c881728ee31485407f688c114f0"  # as tests/test_unseen_provenance.py
LABELS = ("correct", "wrong")
OUT_DIR = PROJECT_ROOT / "docs" / "eval" / "unseen"  # a subfolder: docs/eval/*.json is the main eval's
GRADES = OUT_DIR / "grades.json"
REPORT = PROJECT_ROOT / "docs" / "eval" / "unseen-results.md"
Z95 = 1.96
SQL_POLICY = ("SELECT CLAUSE_ID, VERSION_LABEL, BUS_START, BUS_END, CLAUSE_TEXT, RULE_JSON FROM POLICY_CLAUSE "
              "WHERE DOC_ID = ? ORDER BY CLAUSE_ID, BUS_START")
_DATE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\b")


class RunError(RuntimeError):
    pass


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    customer_date: str
    as_of: date
    draft: str
    label: str
    reason: str


def booking_date(value: str) -> date:
    """The case's customer_date as the as_of_date: its YYYY-MM-DD part. Anything else fails loudly."""
    m = _DATE.match(value or "")
    if not m:
        raise RunError(f"customer_date {value!r} does not start with a YYYY-MM-DD date")
    return date.fromisoformat(m.group(1))


def load_cases(path: Path = CASES, sha256: str | None = CASES_SHA256) -> list[Case]:
    data = path.read_bytes()
    if sha256 is not None and hashlib.sha256(data).hexdigest() != sha256:
        raise RunError(f"{path.name} has changed since it was pinned; refusing to run")
    out = []
    for c in json.loads(data.decode("utf-8")):
        if c["label"] not in LABELS:
            raise RunError(f"case {c['id']}: unknown label {c['label']!r}")
        out.append(Case(str(c["id"]), c["customer_question"], c["customer_date"], booking_date(c["customer_date"]),
                        c["assistant_draft"], c["label"], c["reason"]))
    if len({c.id for c in out}) != len(out):
        raise RunError("case ids are not unique")
    return out


def governing_version(on: date) -> int:
    """SPR's policy version for a booking date (P-01: the booking date fixes the version)."""
    starts = sorted(accuracy.STARTS.items(), key=lambda kv: kv[1])
    found = [v for v, start in starts if start <= on]
    if not found:
        raise RunError(f"{on} is before SPR's first version")
    return found[-1]


def version_of_start(start: date) -> str:
    """The SPR version a clause row belongs to, from its business start (labels can differ: a clause first loaded
    in v2 is labelled v1)."""
    return next((f"V{v}" for v, s in accuracy.STARTS.items() if s == start), "?")


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """Wilson score interval for k successes in n trials."""
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def record(case: Case, result: GateResult, calls: int, tokens_in: int, tokens_out: int,
           plain: PlainOutcome) -> dict[str, Any]:
    """One case's outcome under the plain judge and AsOf, as recorded (no scoring here: grades come later)."""
    def cited(claims: list[Any]) -> list[str]:
        out: list[str] = []
        for c in claims:
            if c.clause:
                ref = f"{c.clause.clause_id} {c.clause.version_label} [{version_of_start(c.clause.bus_start)}]"
                if ref not in out:
                    out.append(ref)
        return out

    gov = governing_version(case.as_of)
    starts = {c.clause.bus_start for c in result.claims + result.rewrite_claims if c.clause}
    return {
        "id": case.id, "customer_date": case.customer_date, "as_of": case.as_of.isoformat(), "governing": f"V{gov}",
        "label": case.label, "decision": result.decision, "reason_code": result.reason_code,
        "released": result.released, "ledger_id": result.ledger_id, "latency_ms": result.latency_ms,
        "cited_pass1": cited(result.claims), "cited_pass2": cited(result.rewrite_claims),
        "other_version_cited": any(s != accuracy.STARTS[gov] for s in starts),
        "claims": [f"p{p}#{c.claim_no} {c.verdict} (llm {c.llm_verdict}, rule {c.rule_check}) "
                   f"{c.clause.clause_id + ' ' + c.clause.version_label if c.clause else '-'}: {c.text[:160]}"
                   for p, cs in ((1, result.claims), (2, result.rewrite_claims)) for c in cs],
        "final_answer": result.final_answer, "unchecked": list(result.unchecked)[:10], "error": result.error,
        "llm_calls": calls, "input_tokens": tokens_in, "output_tokens": tokens_out,
        "plain": {"decision": plain.decision, "reason": plain.reason, "latency_ms": plain.latency_ms,
                  "error": plain.error},
    }


SETUPS = ("no_check", "plain_judge", "asof")
SETUP_NAMES = {"no_check": "(a) No check", "plain_judge": "(b) Plain LLM judge", "asof": "(c) AsOf"}
_ASOF_OUTCOME = {"PASS": "released", "CORRECTED": "rewritten", "ESCALATED": "held"}
_PLAIN_OUTCOME = {"RELEASE": "released", "BLOCK": "held"}


def outcome(record: dict[str, Any], setup: str) -> str:
    """released, rewritten or held: what a setup did with this case's draft."""
    if setup == "no_check":
        return "released"
    if setup == "plain_judge":
        return _PLAIN_OUTCOME[record["plain"]["decision"]]
    return _ASOF_OUTCOME[record["decision"]]


def score(records: list[dict[str, Any]], grades: dict[str, dict[str, str]], setup: str = "asof") -> dict[str, Any]:
    """The pre-registered metrics for one setup. `grades`: case id -> {"grade": "right" | "wrong", "why": ...} for
    rewritten answers (only AsOf rewrites)."""
    rows = []
    for r in records:
        oc = outcome(r, setup)
        grade = grades.get(r["id"], {}).get("grade") if oc == "rewritten" else None
        if grade not in (None, "right", "wrong"):
            raise RunError(f"case {r['id']}: grade must be right or wrong, not {grade!r}")
        pending = oc == "rewritten" and grade is None
        wrong = r["label"] == "wrong"
        fa_low = wrong and (oc == "released" or grade == "wrong")
        fa_high = fa_low or (wrong and pending)
        ideal_high = (oc == "released") if not wrong else (oc == "rewritten" and grade != "wrong")
        ideal_low = ideal_high and not pending
        false_block = (not wrong) and oc != "released"
        rows.append(r | {"outcome": oc, "grade": grade, "pending": pending, "false_allow": fa_low,
                         "false_allow_high": fa_high, "false_block": false_block,
                         "ideal": ideal_low, "ideal_high": ideal_high,
                         "safe": not fa_high and not false_block,
                         "harmful_correction": (not wrong) and grade == "wrong"})
    bad = [r for r in rows if r["label"] == "wrong"]
    good = [r for r in rows if r["label"] == "correct"]

    def metric(k: int, n: int, k_high: int | None = None) -> dict[str, Any]:
        return {"k": k, "k_high": k if k_high is None else k_high, "n": n, "rate": None if n == 0 else k / n,
                "wilson": wilson(k, n), "wilson_high": wilson(k if k_high is None else k_high, n)}

    outcomes = {lab: {o: sum(r["outcome"] == o for r in rows if r["label"] == lab)
                      for o in ("released", "rewritten", "held")} for lab in LABELS}
    out: dict[str, Any] = {
        "false_allow": metric(sum(r["false_allow"] for r in bad), len(bad), sum(r["false_allow_high"] for r in bad)),
        "false_block": metric(sum(r["false_block"] for r in good), len(good)),
        "ideal": metric(sum(r["ideal"] for r in rows), len(rows), sum(r["ideal_high"] for r in rows)),
        "safe": metric(sum(r["safe"] for r in rows), len(rows)),
        "pending_grades": sum(r["pending"] for r in rows),
        "harmful_corrections": sum(r["harmful_correction"] for r in rows),
        "outcomes": outcomes,
        "rows": rows,
    }
    if setup == "asof":
        lat = sorted(r["latency_ms"] for r in rows) or [0]
        out |= {"other_version_cited": sum(r["other_version_cited"] for r in rows),
                "errors": sum(r["reason_code"] == "ERROR_FAIL_CLOSED" for r in rows),
                "latency_p50_ms": int(statistics.median(lat)),
                "latency_p90_ms": int(lat[min(len(lat) - 1, int(round(0.9 * (len(lat) - 1))))])}
    if setup == "plain_judge":
        out["errors"] = sum(bool(r["plain"].get("error")) for r in rows)
    return out


def policy_fingerprint(conn: Any, schema: str) -> tuple[str, int]:
    """SHA-256 over every SPR clause row in force (ID, label, period, text, parameters): names the policy checked."""
    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_POLICY, (onboard.DOC_ID,))
    h = hashlib.sha256()
    for r in rows:
        h.update(json.dumps([str(x).strip() for x in r], ensure_ascii=False).encode("utf-8"))
    return h.hexdigest(), len(rows)


def _git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def load_runs() -> list[dict[str, Any]]:
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in OUT_DIR.glob("run-*.json")]
    return sorted(runs, key=lambda r: r["run"])


def load_grades() -> dict[str, dict[str, dict[str, str]]]:
    if not GRADES.exists():
        return {}
    data: dict[str, dict[str, dict[str, str]]] = json.loads(GRADES.read_text(encoding="utf-8"))
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m asof.eval.unseen", description=__doc__.split("\n\n")[0])
    p.add_argument("--schema", default=onboard.DEFAULT_SCHEMA)
    p.add_argument("--no-rebuild", action="store_true", help="run against SPR as it is in the schema")
    p.add_argument("--provider", choices=["openrouter", "ollama", "openai_compatible", "watsonx"])
    p.add_argument("--model")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--note", default="", help="why this run was made (required for every run after the first)")
    p.add_argument("--render", action="store_true", help="only rewrite the report from the recorded runs")
    args = p.parse_args(argv)
    from . import report

    if args.render:
        report.write(load_runs(), load_grades())
        print(f"wrote {REPORT.relative_to(PROJECT_ROOT)}")
        return 0
    runs = load_runs()
    if runs and not args.note:
        print("Refusing to run: the first run is final. A later run needs --note saying why it was made; it is "
              "reported as post-hoc and never replaces the first.")
        return 2
    target = db.validate_schema(args.schema)
    cases = load_cases()
    settings = get_settings()
    provider = args.provider or settings.llm_provider
    if provider == "replay":
        print("Refusing to run: this measures a live model; set --provider or LLM_PROVIDER to one (not replay).")
        return 2
    from ...embeddings import get_embeddings

    embeddings = get_embeddings(settings.embedding_model)
    if not args.no_rebuild:
        if not onboard.complete():
            print("Refusing to run: SPR's onboarding records do not cover every version.")
            return 2
        onboard.rebuild(settings, target, embeddings, fresh=target != db.SCHEMA)
    with db.connection(settings, "app") as conn:
        fingerprint, n_rows = policy_fingerprint(conn, target)
    if n_rows == 0:
        print(f"Refusing to run: {target} has no SPR clauses.")
        return 2
    llm = build_llm(settings, provider=provider, model=args.model, fallback=False)  # one provider, measured alone
    connections = db.ConnectionPool(settings, "app")
    print(f"Running {len(cases)} SPR cases with {llm.info}, {args.workers} workers, schema {target} "
          f"({n_rows} clause rows, policy {fingerprint[:12]})", flush=True)

    policy_v3 = latest_policy()

    def one(case: Case) -> dict[str, Any]:
        plain = plain_judge(llm, case.question, case.draft, policy_v3)
        counting = CountingLLM(llm)
        gate = Gate(counting, embeddings, connections.connect, target)
        result = gate.check(GateRequest(case.question, case.draft, case.as_of, RAIL.doc_id, "eval"))
        rec = record(case, result, counting.calls, counting.input_tokens, counting.output_tokens, plain)
        print(f"  {case.id:<8} {rec['as_of']} {rec['governing']} {case.label:<7} plain {plain.decision:<7} "
              f"AsOf {rec['decision']:<9} {rec['latency_ms'] / 1000:5.1f}s", flush=True)
        return rec

    started = datetime.now(UTC)
    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        records = list(pool.map(one, cases))
    wall = round(time.monotonic() - t0, 1)
    from ...ledger import verify_chain

    with db.connection(settings, "app") as conn:
        chain = verify_chain(conn, target)
    n = len(runs) + 1
    out = {"run": n, "first_run": n == 1, "note": args.note, "provider": provider, "model": llm.model_name,
           "started_at": started.isoformat(timespec="seconds"), "git_commit": _git_commit(),
           "prompt_version": RAIL.prompt_version, "plain_judge_version": PLAIN_JUDGE_VERSION,
           "cases_sha256": CASES_SHA256, "schema": target,
           "policy_sha256": fingerprint, "policy_rows": n_rows, "workers": args.workers, "wall_time_s": wall,
           "ledger_chain": chain.status, "records": records}
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9.]+", "-", llm.model_name).strip("-")
    path = OUT_DIR / f"run-{n}__{provider}__{slug}__{out['git_commit']}.json"
    path.write_text(json.dumps(out, indent=1, default=str, ensure_ascii=False) + "\n", encoding="utf-8")
    grades = load_grades().get(f"run-{n}", {})
    for setup in SETUPS:
        s = score(records, grades, setup)
        print(f"{SETUP_NAMES[setup]:<22} false allow {s['false_allow']['k']}-{s['false_allow']['k_high']} of "
              f"{s['false_allow']['n']}, false block {s['false_block']['k']} of {s['false_block']['n']}, ideal "
              f"{s['ideal']['k']}-{s['ideal']['k_high']} of {s['ideal']['n']} ({s['pending_grades']} rewrites to grade)")
    print(f"wall {wall}s, ledger chain {chain.status}")
    report.write(load_runs(), load_grades())
    print(f"wrote {path.relative_to(PROJECT_ROOT)} and {REPORT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
