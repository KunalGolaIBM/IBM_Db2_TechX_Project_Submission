"""JSON and Markdown report generation for a verification session."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

REPORT_VERSION = "1.0"
DISCLAIMER = (
    "AEGIS produces evidence-linked assessments, not guarantees of factual accuracy. "
    "Insufficient evidence is not evidence of contradiction. Automated judgments require "
    "researcher review."
)


def _json_default(value: Any) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def build_json_report(session: dict) -> str:
    payload = {
        "report_version": REPORT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "system": {
            "name": "AEGIS",
            "tagline": "Verify Before You Trust.",
            "database": "IBM Db2",
            "orchestration": "LangChain",
        },
        "disclaimer": DISCLAIMER,
        "session": session,
    }
    return json.dumps(payload, indent=2, default=_json_default)


def build_markdown_report(session: dict) -> str:
    counts = session.get("counts") or {}
    lines: list[str] = [
        f"# AEGIS verification report — session #{session.get('session_id')}",
        "",
        f"**Status:** {_fmt(session.get('status'))}  ",
        f"**Model:** {_fmt(session.get('model_provider'))}  ",
        f"**Created:** {_fmt(session.get('created_at'))}  ",
        f"**Completed:** {_fmt(session.get('completed_at'))}  ",
        f"**Duration:** {_fmt(session.get('duration_ms'))} ms  ",
        "",
        "## Summary",
        "",
        "| Total | Supported | Contradicted | Insufficient | Errors |",
        "| ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {counts.get('total', 0)} | {counts.get('supported', 0)} | "
            f"{counts.get('contradicted', 0)} | {counts.get('insufficient_evidence', 0)} | "
            f"{counts.get('verification_error', 0)} |"
        ),
        "",
        "## Submitted response",
        "",
        f"> {session.get('submitted_text', '').strip()}",
        "",
        "## Claims",
        "",
    ]

    claims = session.get("claims") or []
    if not claims:
        lines.extend(["No verifiable claims were extracted.", ""])

    for index, claim in enumerate(claims, start=1):
        lines.extend(
            [
                f"### {index}. {claim.get('classification') or 'PENDING'}",
                "",
                f"**Claim:** {claim.get('original_claim', '')}",
                "",
                f"- Type: `{claim.get('claim_type', '—')}`",
                f"- Human review: `{claim.get('human_review_status', 'PENDING')}`",
                f"- Verification method: `{claim.get('verification_method', '—')}`",
                "",
                f"**Explanation:** {claim.get('explanation') or '—'}",
                "",
                f"**Limitations:** {claim.get('limitations') or '—'}",
                "",
            ]
        )
        if claim.get("numerical_analysis"):
            lines.extend([f"**Numerical check:** {claim['numerical_analysis']}", ""])
        evidence = claim.get("evidence") or []
        if evidence:
            lines.extend(["**Evidence:**", ""])
            for item in evidence:
                lines.extend(
                    [
                        (
                            f"- {item.get('document_title', 'Unknown document')}, "
                            f"page {_fmt(item.get('page_number'))}, passage {item.get('passage_id')} "
                            f"({item.get('evidence_relationship') or 'context'}, "
                            f"score {_fmt(item.get('relevance_score'))})"
                        ),
                        "",
                        f"  > {item.get('passage_text', '').strip()}",
                        "",
                    ]
                )
        else:
            lines.extend(["**Evidence:** none linked.", ""])

    unresolved = [
        claim
        for claim in claims
        if claim.get("classification") in ("INSUFFICIENT_EVIDENCE", "VERIFICATION_ERROR")
    ]
    lines.extend(["## Unresolved questions", ""])
    if unresolved:
        for claim in unresolved:
            lines.append(
                f"- ({claim.get('classification')}) {claim.get('original_claim')}"
            )
    else:
        lines.append("No unresolved claims in this session.")
    lines.extend(["", "---", "", DISCLAIMER, ""])
    return "\n".join(lines)
