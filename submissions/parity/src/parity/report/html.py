"""Self contained HTML report.

One file, no external assets, no build step. It can
be attached to a ticket or saved as evidence.
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime

from parity.engine.result import ComparisonStatus
from parity.report.metrics import build_metrics
from parity.report.risk import QueryReport

_STYLE = """
body { font-family: sans-serif; margin: 2em; max-width: 900px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ccc; padding: 6px; text-align: left; }
.match { color: green; } .mismatch { color: red; }
pre { background: #f4f4f4; padding: 8px; overflow-x: auto; }
""".strip()


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _status_class(status: ComparisonStatus) -> str:
    if status is ComparisonStatus.MATCH:
        return "match"
    return "mismatch"


def render_html(reports: list[QueryReport], title: str = "Parity report") -> str:
    """Render the full HTML report."""
    generated = datetime.now(UTC).isoformat()
    passed = sum(1 for r in reports if r.result.status is ComparisonStatus.MATCH)
    failed = len(reports) - passed
    rows = []
    for report in reports:
        status = report.result.status.value
        rows.append(
            "<tr>"
            f"<td>{_esc(report.query_id)}</td>"
            f"<td class='{_status_class(report.result.status)}'>{_esc(status)}</td>"
            f"<td>{report.score} ({_esc(report.label)})</td>"
            f"<td><pre>{_esc(report.source_sql)}</pre></td>"
            f"<td><pre>{_esc(report.db2_sql)}</pre></td>"
            f"<td>{_esc(report.result.note)}</td>"
            "</tr>"
        )
    diff_sections = []
    for report in reports:
        if not report.result.diffs:
            continue
        items = "".join(
            f"<li>{_esc(diff.kind.value)}: {_esc(diff.detail)} "
            f"(source={_esc(diff.source_value)} target={_esc(diff.target_value)})</li>"
            for diff in report.result.diffs
        )
        diff_sections.append(f"<h3>{_esc(report.query_id)}</h3><ul>{items}</ul>")
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{_STYLE}</style></head><body>"
        f"<h1>{_esc(title)}</h1>"
        f"<p>Generated: {_esc(generated)}</p>"
        f"<p>Passed: {passed} Failed: {failed} Total: {len(reports)}</p>"
        "<table><tr><th>Query</th><th>Status</th><th>Risk</th>"
        "<th>Source SQL</th><th>Db2 SQL</th><th>Note</th></tr>"
        + "".join(rows)
        + "</table><h2>First differences</h2>"
        + ("".join(diff_sections) if diff_sections else "<p>None.</p>")
        + "</body></html>"
    )


def render_json_summary(
    reports: list[QueryReport],
    run_id: int | None = None,
    regression: dict | None = None,
    llm_usage: dict | None = None,
) -> str:
    """Render a machine readable JSON summary."""
    entries = []
    for report in reports:
        entries.append(
            {
                "query_id": report.query_id,
                "status": report.result.status.value,
                "risk_score": report.score,
                "risk_label": report.label,
                "note": report.result.note,
                "diff_count": len(report.result.diffs),
            }
        )
    payload: dict = {"queries": entries, "metrics": build_metrics(reports, llm_usage)}
    if run_id is not None:
        payload["run_id"] = run_id
    if regression is not None:
        payload["regression"] = regression
    if llm_usage is not None:
        payload["llm_usage"] = llm_usage
    return json.dumps(payload, indent=2)
