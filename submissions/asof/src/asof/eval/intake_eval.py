"""Policy intake evaluation: the model's proposals and the deterministic checks, scored against gold answers.

    python -m asof.eval.intake_eval [--provider openrouter|ollama|openai_compatible|watsonx] [--model NAME]

Three fictional documents (src/asof/eval/intake), frozen with gold.json before the first run. No Db2 is needed: the
policy the proposals are compared with is the shipped corpus, which is what setup seeds. Each expected item ends in
one of five outcomes:

    correct, acceptable   the checks let a right proposal through to the editor
    correct, blocked      a false block: a right proposal the editor cannot accept
    wrong, blocked        the checks caught a wrong proposal
    wrong, acceptable     a wrong proposal reached the editor unblocked (the editor is then the only safeguard)
    missing               the model proposed nothing for it

Proposals that match nothing expected are reported too, and so is whatever came of the document's injected
instruction. Writes docs/eval-intake/<provider>__<model>__<commit>.json and rebuilds docs/intake_eval.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import intake, rules
from ..config import get_settings
from ..llm import LLMError, build_llm

HERE = Path(__file__).with_name("intake")
GOLD = HERE / "gold.json"
PROJECT = Path(__file__).resolve().parents[3]
OUT_DIR = PROJECT / "docs" / "eval-intake"
REPORT = PROJECT / "docs" / "intake_eval.md"


def document_paths() -> list[Path]:
    return [(HERE / d["file"]).resolve() for d in json.loads(GOLD.read_text(encoding="utf-8"))["documents"]]


def frozen_digest() -> str:
    """SHA-256 over gold.json and every document, in order: the evaluation's identity."""
    h = hashlib.sha256(GOLD.read_bytes())
    for p in document_paths():
        h.update(p.read_bytes())
    return h.hexdigest()


def _value_ok(spec: dict, rule: dict[str, Any]) -> bool:
    if "unit" in spec:
        want = float(spec["value"])
        return any(p.unit == spec["unit"] and rules._close(p.value, want, p.unit) for p in rules.rule_params(rule))
    if "flag" in spec:
        return rule.get(spec["flag"]) is spec["value"]
    if "items" in spec:
        items = {intake.normalize(x).casefold() for x in spec["items"]}
        return any(isinstance(v, list) and {intake.normalize(str(x)).casefold() for x in v} == items for v in rule.values())
    raise ValueError(f"unknown value spec {spec}")


def _match(expect: dict, proposals: list[intake.Proposal], used: set[int]) -> intake.Proposal | None:
    for p in proposals:
        if p.item_no in used:
            continue
        if expect["clause_id"] == "NEW":
            if p.kind == "NEW" and expect["text_has"].casefold() in p.clause_text.casefold():
                return p
        elif p.clause_id == expect["clause_id"]:
            return p
    return None


def score(expect: dict, p: intake.Proposal | None) -> dict[str, Any]:
    if p is None:
        return {"expected": expect["clause_id"], "outcome": "missing"}
    problems = []
    if p.kind != expect["kind"]:
        problems.append(f"kind {p.kind}, expected {expect['kind']}")
    if p.effective_from.isoformat() != expect["from"]:
        problems.append(f"from {p.effective_from}, expected {expect['from']}")
    to = p.effective_to.isoformat() if p.effective_to else None
    if to not in expect["to"]:
        problems.append(f"to {to}, expected {' or '.join(str(t) for t in expect['to'])}")
    if expect["kind"] != "UNCHANGED":
        problems += [f"value {json.dumps(v)} not in the proposal" for v in expect["values"] if not _value_ok(v, p.rule)]
    correct = not problems
    outcome = ("correct, " if correct else "wrong, ") + ("blocked" if p.blocked else "acceptable")
    return {"expected": expect["clause_id"], "proposed": p.clause_id, "kind": p.kind, "outcome": outcome,
            "problems": problems, "warnings": [c.detail for c in p.checks if c.status == "warn"],
            "failed_checks": [c.detail for c in p.checks if c.status == "fail"], "rule": p.rule,
            "from": p.effective_from.isoformat(), "to": to}


def run(provider: str | None, model: str | None) -> dict[str, Any]:
    settings = get_settings()
    llm = build_llm(settings, provider=provider, model=model, fallback=False,
                    max_output_tokens=settings.asof_intake_max_output_tokens, deadline_s=settings.asof_intake_timeout_s)
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    docs = []
    for d, path in zip(gold["documents"], document_paths(), strict=True):
        source = intake.read_pdf(path.read_bytes(), path.name)
        existing = intake.corpus_clauses(d["doc_id"])
        started = time.monotonic()
        try:
            extracted, _ = intake.extract(llm, source, d["doc_id"], existing)
            error = None
        except LLMError as exc:
            extracted, error = None, str(exc)[:300]
        latency = int((time.monotonic() - started) * 1000)
        proposals, discarded = intake.check_items(extracted, source, existing) if extracted else ([], [])
        used: set[int] = set()
        items = []
        for e in d["expect"]:
            p = _match(e, proposals, used)
            if p is not None:
                used.add(p.item_no)
            items.append(score(e, p))
        extras = [{"clause_id": p.clause_id, "kind": p.kind, "blocked": p.blocked, "text": p.clause_text[:200],
                   "from_injection": bool(d.get("injection") and d["injection"].casefold() in p.clause_text.casefold())}
                  for p in proposals if p.item_no not in used]
        docs.append({"document": path.name, "doc_id": d["doc_id"], "latency_ms": latency, "error": error,
                     "items": items, "extras": extras, "discarded": [x.__dict__ for x in discarded],
                     "injection_in_document": bool(d.get("injection"))})
    outcomes = [i["outcome"] for doc in docs for i in doc["items"]]
    count = {k: outcomes.count(k) for k in ("correct, acceptable", "correct, blocked", "wrong, blocked",
                                            "wrong, acceptable", "missing")}
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=PROJECT,
                            check=False).stdout.strip() or "unknown"
    return {"provider": llm.provider, "model": llm.model_name, "git_commit": commit, "frozen_sha256": frozen_digest(),
            "started_at": datetime.now(UTC).isoformat(timespec="seconds"), "expected_items": len(outcomes),
            "outcomes": count, "extras": sum(len(doc["extras"]) for doc in docs),
            "extras_unblocked": sum(1 for doc in docs for x in doc["extras"] if not x["blocked"]),
            "injection_items": sum(1 for doc in docs for x in doc["extras"] if x["from_injection"]),
            "injection_items_unblocked": sum(1 for doc in docs for x in doc["extras"]
                                             if x["from_injection"] and not x["blocked"]),
            "documents": docs}


def report() -> str:
    runs = sorted((json.loads(p.read_text(encoding="utf-8")) for p in OUT_DIR.glob("*.json")),
                  key=lambda r: r["started_at"], reverse=True)
    lines = ["# Policy intake evaluation", "",
             "Generated by `python -m asof.eval.intake_eval` from the runs in `docs/eval-intake/`. Three fictional documents "
             "(the demo sample, a bank fee update, a two-page airline revision with an injected instruction), 11 expected "
             "items, frozen with their gold answers before the first run. See the module docstring for the outcomes.", ""]
    for r in runs:
        o = r["outcomes"]
        lines += [f"## {r['provider']} `{r['model']}`, run {r['started_at'][:10]} at `{r['git_commit']}`", "",
                  "| Outcome | Items |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in o.items()]
        lines += ["", f"Proposals matching nothing expected: {r['extras']} ({r['extras_unblocked']} unblocked). "
                  f"From the injected instruction: {r['injection_items']} ({r['injection_items_unblocked']} unblocked).", ""]
        for doc in r["documents"]:
            err = f": {doc['error']}" if doc["error"] else ""
            lines.append(f"- **{doc['document']}** ({doc['latency_ms'] / 1000:.1f} s){err}")
            for i in doc["items"]:
                why = "; ".join(i.get("problems", []) + [f"failed check: {f}" for f in i.get("failed_checks", [])])
                lines.append(f"  - {i['expected']}: {i['outcome']}{' (' + why + ')' if why else ''}")
            for x in doc["extras"]:
                lines.append(f"  - extra {x['clause_id']} {x['kind']}: {'blocked' if x['blocked'] else 'acceptable'}"
                             f"{' (from the injected instruction)' if x['from_injection'] else ''}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m asof.eval.intake_eval", description=__doc__.split("\n\n")[0])
    ap.add_argument("--provider", choices=["openrouter", "ollama", "openai_compatible", "watsonx"])
    ap.add_argument("--model")
    args = ap.parse_args(argv)
    result = run(args.provider, args.model)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{result['provider']}__{result['model'].replace('/', '_').replace(':', '_')}__{result['git_commit']}.json"
    (OUT_DIR / name).write_text(json.dumps(result, indent=1, default=str) + "\n", encoding="utf-8")
    REPORT.write_text(report() + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("provider", "model", "git_commit", "outcomes", "extras", "extras_unblocked",
                                             "injection_items", "injection_items_unblocked")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
