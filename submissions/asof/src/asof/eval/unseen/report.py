"""The generated part of docs/eval/unseen-results.md (see docblocks.py for how the blocks work).

Each document is written by hand around blocks marked <!-- generated:NAME --> ... <!-- /generated:NAME -->; only
the blocks are rewritten, from the recorded runs, grades and onboarding records, so every number in them comes
from a record and the notes around them survive a re-render.
"""

from __future__ import annotations

from typing import Any

from .docblocks import replace_blocks
from .run import REPORT, SETUP_NAMES, SETUPS, score


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _ci(ci: tuple[float, float] | None) -> str:
    return "n/a" if ci is None else f"{100 * ci[0]:.1f}% to {100 * ci[1]:.1f}%"


def _cell(m: dict[str, Any]) -> str:
    if m["k"] == m["k_high"]:
        return f"{m['k']} of {m['n']}, {_pct(m['rate'])} ({_ci(m['wilson'])})"
    hi = m["k_high"] / m["n"] if m["n"] else None
    return (f"{m['k']} to {m['k_high']} of {m['n']} (grades pending), {_pct(m['rate'])} to {_pct(hi)} "
            f"({_ci(m['wilson'])} / {_ci(m['wilson_high'])})")


def _mark(r: dict[str, Any]) -> str:
    text = {"released": "released", "rewritten": "rewritten", "held": "held"}[r["outcome"]]
    return f"**{text}, false allow**" if r["false_allow"] else (f"{text} (false block)" if r["false_block"] else text)


def run_block(run: dict[str, Any], grades: dict[str, dict[str, str]]) -> str:
    scores = {setup: score(run["records"], grades, setup) for setup in SETUPS}
    s = scores["asof"]
    title = "First run (final)" if run["first_run"] else f"Run {run['run']} (post-hoc: {run['note']})"
    lines = [f"### {title}", "",
             f"{run['provider']} `{run['model']}` for both the plain judge and AsOf, started {run['started_at']} at "
             f"commit `{run['git_commit']}`. AsOf prompt version `{run['prompt_version']}`, plain judge "
             f"`{run.get('plain_judge_version', '?')}`. {len(run['records'])} cases (file sha256 "
             f"`{run['cases_sha256'][:16]}...`). SPR as loaded: {run['policy_rows']} clause rows (sha256 "
             f"`{run['policy_sha256'][:16]}...`). {run['workers']} workers, wall time {run['wall_time_s']} s, "
             f"AsOf ledger chain {run['ledger_chain']}.", "",
             "| Metric (Wilson 95% interval) | " + " | ".join(SETUP_NAMES[x] for x in SETUPS) + " |",
             "|---|---|---|---|"]
    for key, name in (("false_allow", "False allow: a wrong draft reached the customer"),
                      ("false_block", "False block: a correct draft did not go out as written"),
                      ("ideal", "Ideal: what a careful specialist would want"),
                      ("safe", "Safe: neither a false allow nor a false block")):
        lines.append(f"| {name} | " + " | ".join(_cell(scores[x][key]) for x in SETUPS) + " |")
    lines += ["", "| Setup | correct: released / rewritten / held | wrong: released / rewritten / held |",
              "|---|---|---|"]
    for x in SETUPS:
        o = scores[x]["outcomes"]
        lines.append(f"| {SETUP_NAMES[x]} | " + " | ".join(
            f"{o[lab]['released']} / {o[lab]['rewritten']} / {o[lab]['held']}" for lab in ("correct", "wrong")) + " |")
    lines += ["",
              f"AsOf: rewritten answers still to grade {s['pending_grades']}; harmful corrections (a correct draft "
              f"rewritten into a wrong answer) {s['harmful_corrections']}; cases citing a clause row from another SPR "
              f"version than the booking date's {s['other_version_cited']}; errors (failed closed) {s['errors']}; "
              f"latency p50 {s['latency_p50_ms'] / 1000:.1f} s, p90 {s['latency_p90_ms'] / 1000:.1f} s. Plain judge "
              f"errors (blocked) {scores['plain_judge']['errors']}.", "",
              "| Case | Customer date | Version | Label | (a) No check | (b) Plain judge | (c) AsOf | AsOf ideal | "
              "AsOf latency | Clauses AsOf cited (draft; rewrite) | Grade of AsOf's rewrite |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    by_setup = {x: {r["id"]: r for r in scores[x]["rows"]} for x in SETUPS}
    for r in s["rows"]:
        ideal = "pending" if r["pending"] and r["ideal_high"] else ("yes" if r["ideal"] else "no")
        cited = ", ".join(r["cited_pass1"]) or "none"
        if r["cited_pass2"]:
            cited += "; " + ", ".join(r["cited_pass2"])
        grade = ""
        if r["outcome"] == "rewritten":
            g = grades.get(r["id"])
            grade = f"{g['grade']}: {g['why']}" if g else "pending"
        lines.append(f"| {r['id']} | {r['customer_date']} | {r['governing']} | {r['label']} | "
                     f"{_mark(by_setup['no_check'][r['id']])} | {_mark(by_setup['plain_judge'][r['id']])} | "
                     f"{_mark(r)}, {r['decision']} ({r['reason_code']}) | {ideal} | {r['latency_ms'] / 1000:.1f} s | "
                     f"{cited} | {grade} |")
    return "\n".join(lines)


RESULTS_SKELETON = """# Unseen-domain evaluation: SPR

<!-- generated:runs -->
<!-- /generated:runs -->
"""


def write(runs: list[dict[str, Any]], grades: dict[str, dict[str, dict[str, str]]]) -> None:
    body = "\n\n".join(run_block(r, grades.get(f"run-{r['run']}", {})) for r in runs) or "No run yet."
    replace_blocks(REPORT, {"runs": body}, RESULTS_SKELETON)
