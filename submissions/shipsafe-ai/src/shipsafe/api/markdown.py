"""Markdown report rendered from stored Db2 rows (used by the API export endpoint)."""

import time
from typing import Any, Dict, List

ICON = {"BLOCKED": "BLOCKED", "PASS_WITH_WARNINGS": "PASS WITH WARNINGS", "PASS": "PASS"}


def markdown_from_rows(asm: Dict[str, Any], findings: List[Dict[str, Any]], runs: List[Dict[str, Any]]) -> str:
    started = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(int(asm["STARTED_AT"]) / 1000))
    lines = [
        "# ShipSafe AI production-readiness report", "",
        f"**Release gate:** `{ICON.get(asm['STATUS'], asm['STATUS'])}`  ",
        f"**Project:** `{asm.get('PROJECT_NAME', asm['PROJECT_ID'])}`  ",
        f"**Assessment:** `{asm['ASSESSMENT_ID']}` · profile `{asm['PROFILE']}` · {started}  ",
        f"**Commit:** `{asm.get('COMMIT_SHA') or 'uncommitted'}`", "",
        f"> {asm.get('GATE_REASON') or ''}", "",
        f"Critical **{asm['CRITICAL_COUNT']}** · High **{asm['HIGH_COUNT']}** · "
        f"Medium **{asm['MEDIUM_COUNT']}** · Low **{asm['LOW_COUNT']}**", "",
        "## Checks", "", "| Tool | Status | Duration | Notes |", "| --- | --- | --- | --- |",
    ]
    for r in runs:
        lines.append(f"| `{r['TOOL_NAME']}` | {r['STATUS']} | {r['DURATION_MS']} ms | {(r.get('MESSAGE') or '').replace('|', '/')} |")
    lines += ["", "## Findings", ""]
    if not findings:
        lines.append("_No findings._")
    for i, f in enumerate(findings, 1):
        loc = f"{f.get('FILE_PATH')}:{f.get('LINE_START')}" if f.get("FILE_PATH") else "repository"
        lines += [f"### {i}. [{f['SEVERITY'].upper()}] {f['TITLE']}",
                  f"- **Location:** `{loc}` · **Rule:** `{f['RULE_ID']}` · **Source:** `{f['SOURCE_TOOL']}`",
                  f"- **Fingerprint:** `{f['FINGERPRINT']}`"]
        if f.get("DESCRIPTION"):
            lines.append(f"- {f['DESCRIPTION']}")
        policy = (f.get("EVIDENCE") or {}).get("policy")
        if policy:
            lines.append(f"- **Policy:** {policy.get('doc_id')} {policy.get('title')} (section: {policy.get('section')})")
        if f.get("REMEDIATION"):
            lines.append(f"- **Fix:** {f['REMEDIATION']}")
        lines.append("")
    lines += ["---", "_A PASS reflects the checks above; it is not proof of correctness. Peer review still matters._"]
    return "\n".join(lines)
