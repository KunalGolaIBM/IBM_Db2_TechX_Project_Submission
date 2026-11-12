"""Markdown and JSON report generators for ShipSafe AI."""

import json
import time
from typing import Dict, Any
from ..orchestration.engine import AssessmentResult


class ReportGenerator:
    """Generates comprehensive audit reports in Markdown and JSON formats."""

    @staticmethod
    def to_json(result: AssessmentResult, indent: int = 2) -> str:
        """Serializes complete assessment bundle into standard JSON format."""
        return json.dumps(result.to_dict(), indent=indent, default=str)

    @staticmethod
    def to_sarif(result: AssessmentResult) -> str:
        """SARIF 2.1.0 for GitHub code scanning and other SARIF viewers."""
        return json.dumps(sarif_document(result.assessment.assessment_id,
                                         [f.to_dict() for f in result.findings]), indent=2)


    @staticmethod
    def to_markdown(result: AssessmentResult) -> str:
        """Generates an executive production-readiness report in Markdown format."""
        asm = result.assessment
        disc = result.discovery
        gate = result.gate
        fnds = result.findings
        tools = result.tool_runs

        status_emoji = "🔴 BLOCKED" if asm.status == "BLOCKED" else ("🟡 PASS WITH WARNINGS" if asm.status == "PASS_WITH_WARNINGS" else "🟢 PASS")

        lines = [
            f"# ShipSafe AI Production-Readiness Assessment Report",
            f"",
            f"**Release Gate Status:** `{status_emoji}`  ",
            f"**Project:** `{disc.repo_name}` (`{disc.project_id}`)  ",
            f"**Assessment ID:** `{asm.assessment_id}`  ",
            f"**Profile:** `{asm.profile}`  ",
            f"**Timestamp:** `{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(asm.started_at / 1000))}`  ",
            f"**Commit / HEAD:** `{asm.commit_sha}` | **Branch:** `{disc.current_branch or 'main'}`  ",
            f"",
            f"---",
            f"",
            f"## 1. Executive Summary",
            f"{asm.gate_reason}",
            f"",
            f"- **Critical Issues:** {asm.critical_count}",
            f"- **High Severity Issues:** {asm.high_count}",
            f"- **Medium Severity Issues:** {asm.medium_count}",
            f"- **Low / Informational:** {asm.low_count}",
            f"- **Total Findings:** {asm.findings_count}",
            f"",
            f"---",
            f"",
            f"## 2. Release Gate Policy Evaluation",
        ]

        for reason in gate.reasons:
            lines.append(f"- {reason}")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 3. Tool Execution & Provenance",
            f"",
            f"| Tool Name | Status | Exit Code | Duration (ms) | Operational Notes |",
            f"| :--- | :--- | :--- | :--- | :--- |",
        ])

        for tr in tools:
            lines.append(f"| `{tr.tool_name}` | `{tr.status}` | `{tr.exit_code}` | `{tr.duration_ms}ms` | {tr.message} |")

        if disc.skipped_checks:
            lines.extend([
                f"",
                f"### Skipped & Unsupported Checks",
            ])
            for chk, r in disc.skipped_checks.items():
                lines.append(f"- **`{chk}`**: {r}")

        lines.extend([
            f"",
            f"---",
            f"",
            f"## 4. Normalized Findings & Evidence",
        ])

        if not fnds:
            lines.append(f"\n*No findings identified. The codebase satisfies all scanned production-readiness checks.*\n")
        else:
            for idx, f in enumerate(fnds, 1):
                loc = f"`{f.file_path}:{f.line_start}`" if f.file_path else "`Repository scope`"
                lines.extend([
                    f"",
                    f"### Finding {idx}: {f.title}",
                    f"- **Severity:** `{f.severity.upper()}` | **Confidence:** `{f.confidence}` | **Category:** `{f.category}`",
                    f"- **Source Scanner:** `{f.source_tool}` | **Rule ID:** `{f.rule_id}`",
                    f"- **Fingerprint:** `{f.fingerprint}`",
                    f"- **Location:** {loc}",
                    f"- **Description:** {f.description}",
                ])

                if f.evidence:
                    lines.append(f"```json\n{json.dumps(f.evidence, indent=2)}\n```")

                if f.remediation:
                    lines.append(f"**Remediation Guidance:**\n{f.remediation}\n")

        # Knowledge & Policy Guidance
        if result.retrieved_policies:
            lines.extend([
                f"",
                f"---",
                f"",
                f"## 5. Governing Policies (retrieved from the IBM Db2 vector store)",
            ])
            for pol in result.retrieved_policies:
                lines.extend([
                    f"",
                    f"### {pol['title']} (`{pol['doc_id']}`)",
                    f"*Source: {pol['source']} | Section: {pol.get('section')} | Db2 cosine similarity: {pol.get('similarity', 0):.3f}*",
                    f"",
                    f"> {pol['content']}",
                ])

        # Disclaimer
        lines.extend([
            f"",
            f"---",
            f"",
            f"## 6. Limitations & Disclaimer",
            f"> **Disclaimer:** A clean scan (`PASS`) is an indication of conformance to deterministic engineering "
            f"> rules and static checks; it does not constitute mathematical proof of software correctness or complete "
            f"> vulnerability absence. Manual peer review, penetration testing, and load verification remain essential.",
            f"",
            f"*ShipSafe AI report. Assessment persisted in IBM Db2: {result.persisted}.*",
        ])

        return "\n".join(lines)


SARIF_LEVEL = {"critical": "error", "high": "error", "medium": "warning", "low": "note", "info": "note"}
SARIF_SCORE = {"critical": "9.5", "high": "7.5", "medium": "5.0", "low": "2.0", "info": "0.0"}


def sarif_document(assessment_id: str, findings: list) -> Dict[str, Any]:
    """Build a SARIF 2.1.0 log from finding dicts (engine objects or Db2 rows)."""
    def g(f, key):
        return f.get(key, f.get(key.upper()))

    rules: Dict[str, Dict[str, Any]] = {}
    results = []
    for f in findings:
        rule_id, sev = g(f, "rule_id"), (g(f, "severity") or "info").lower()
        rules.setdefault(rule_id, {
            "id": rule_id,
            "name": rule_id,
            "shortDescription": {"text": (g(f, "title") or rule_id)[:200]},
            "help": {"text": g(f, "remediation") or "See ShipSafe report."},
            "properties": {"security-severity": SARIF_SCORE.get(sev, "0.0"), "tags": ["security", g(f, "category")]},
        })
        res = {
            "ruleId": rule_id,
            "level": SARIF_LEVEL.get(sev, "note"),
            "message": {"text": f"{g(f, 'title')}. {g(f, 'description') or ''}".strip()[:1000]},
            "partialFingerprints": {"shipsafe/v1": g(f, "fingerprint")},
            "properties": {"severity": sev, "confidence": g(f, "confidence"), "category": g(f, "category")},
        }
        if g(f, "file_path"):
            region = {"startLine": int(g(f, "line_start") or 1)}
            res["locations"] = [{"physicalLocation": {"artifactLocation": {"uri": g(f, "file_path")}, "region": region}}]
        results.append(res)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "ShipSafe AI", "informationUri": "https://github.com/ddevSharma/IBM_Db2_TechX_Project_Submission",
                                "version": "2.0.0", "rules": list(rules.values())}},
            "automationDetails": {"id": f"shipsafe/{assessment_id}"},
            "results": results,
        }],
    }
