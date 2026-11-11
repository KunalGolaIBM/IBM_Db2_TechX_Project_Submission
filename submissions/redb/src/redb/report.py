"""Export a tuning run as a Markdown report."""
from __future__ import annotations

from typing import Any


def _ms(v: Any) -> str:
    return f"{v:,.1f}" if isinstance(v, (int, float)) else "-"


def to_markdown(state: dict[str, Any], llm_mode: str = "") -> str:
    rep = state.get("report") or {}
    out = ["# reDB tuning report", ""]
    if llm_mode:
        out += [f"Diagnosis engine: {llm_mode}", ""]
    if rep.get("narrative"):
        out += [rep["narrative"], ""]
    if rep.get("per_statement"):
        out += ["## Measured results (median ms)", "", "| Statement | Before | After | Gain % |", "|---|---:|---:|---:|"]
        out += [f"| {r['case_id']} | {_ms(r.get('ms_before'))} | {_ms(r.get('ms_after'))} | {r.get('gain_pct', '-')} |"
                for r in rep["per_statement"]]
        if rep.get("reduction_pct") is not None:
            out.append(f"| **Total** | **{_ms(rep['ms_before'])}** | **{_ms(rep['ms_after'])}** | **{rep['reduction_pct']}** |")
        out.append("")
    applied = {p["id"]: p for p in rep.get("applied", [])}
    out += ["## Statements", ""]
    for c in state.get("cases", []):
        d = c.get("diagnosis", {})
        out += [f"### {c['case_id']}: {d.get('headline', '')}", "", "```sql", c["sql"], "```", "",
                d.get("plain_english", ""), ""]
        out += [f"- {rc}" for rc in d.get("root_causes", [])]
        after = c.get("plan_after")
        out += ["", f"Estimated cost: {c['plan_cost']:,.1f} timerons now"
                + (f", {after['cost']:,.1f} with the proposed indexes (virtual)" if after else ""), "",
                "```", c["plan_summary"], "```", ""]
    out += ["## Proposals", ""]
    for p in state.get("proposals", []):
        a = applied.get(p["id"])
        status = f"{a['status']} (ledger #{a['change_id']})" if a else ("proven, not applied" if p["verified"] else "rejected")
        out += [f"### [{p['kind']}] {p['title']}", "", f"- Status: {status}", f"- Evidence: {p['evidence']}",
                f"- Rationale: {p['rationale']}", ""]
        body = "\n".join(p["ddl"]) or p.get("rewrite_sql") or ""
        if body:
            out += ["```sql", body, "```", ""]
        if p["undo"]:
            out += ["Undo:", "", "```sql", "\n".join(p["undo"]), "```", ""]
    out += ["## Agent log", "", "```", *state.get("log", []), "```", ""]
    return "\n".join(out)
