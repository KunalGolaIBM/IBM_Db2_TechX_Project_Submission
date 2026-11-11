"""Deterministic question screens applied to every request, whichever planner runs.

They can only make an outcome stricter (BLOCKED or AMBIGUOUS); they never turn a
blocked or ambiguous plan into an executable one. They exist so that governance does
not depend on the model noticing the problem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Imperative data-changing language. Analytic phrasing ("cancelled orders", "refunded") is not matched.
_WRITE_PATTERNS = [
    r"\b(delete|drop|truncate|insert|alter|grant|revoke|wipe|erase|purge)\b",
    r"\bupdate\s+(?:the\s+|all\s+|every\s+)?(?:orders?|refunds?|products?|items?|tables?|data|records?|rows?|prices?"
    r"|metrics?|definitions?|status(?:es)?)\b",
    r"\b(?:create|replace)\s+(?:a\s+|an\s+|the\s+)?(?:table|index|view|user|schema|procedure|function|trigger)\b",
    r"\bmerge\s+into\b",
    r"\bset\s+\w+\s*=",
    r"\b(?:mark|change|modify|overwrite|edit|set)\b[^.?!]{0,40}\b(?:as|to)\s+(?:processed|completed|cancelled|pending"
    r"|rejected|approved|deprecated)\b",
]
_WRITE_RE = re.compile("|".join(_WRITE_PATTERNS), re.IGNORECASE)

# Raw SQL or system-catalog access is never accepted as a question.
_RAW_SQL_RE = re.compile(
    r"\b(?:select\s+(?:\*|distinct\b|count\s*\()|select\s+[\w.,\s]+\s+from\s+\w+\.\w+|union\s+(?:all\s+)?select|exec(?:ute)?\s+\w+|call\s+\w+\s*\()"
    r"|\b(?:syscat|sysibm|sysibmadm|sysproc|systools|sysstat)\b|/\*|;\s*(?:select|with|drop|delete|insert|update)\b"
    r"|\bfrom\s+metricguard\.\w+",
    re.IGNORECASE,
)

# Relative periods have no anchor: data coverage is fixed, "now" is not.
_RELATIVE_TIME_RE = re.compile(
    r"\b(?:(?:last|this|next|previous|past|prior|current|recent|trailing|coming)\s+(?:\d+\s+)?"
    r"(?:days?|weeks?|months?|quarters?|years?|fiscal\s+year|fy|period|half)"
    r"|yesterday|today|tonight|tomorrow|ytd|qtd|mtd|year[-\s]to[-\s]date|quarter[-\s]to[-\s]date"
    r"|month[-\s]to[-\s]date|so\s+far\s+this\s+\w+|recently|lately|(?:\d+|a|one|two|three|six)\s+(?:days?|weeks?"
    r"|months?|quarters?|years?)\s+ago)\b",
    re.IGNORECASE,
)

# A bare "revenue"/"sales" maps to two approved metrics (gross vs net).
_BARE_REVENUE_RE = re.compile(
    r"(?<!gross\s)(?<!net\s)\b(revenue|sales)\b(?!\s+(?:after|before|net|minus|less|channel|channels))",
    re.IGNORECASE,
)
_REVENUE_QUALIFIERS_RE = re.compile(
    r"\b(gross|net|bookings|after refunds|before refunds)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class ScreenFinding:
    code: str  # WRITE_INTENT | OUT_OF_SCOPE | AMBIGUOUS_METRIC | AMBIGUOUS_TIME_RANGE
    message: str
    term: str | None = None


def screen_question(question: str) -> list[ScreenFinding]:
    findings: list[ScreenFinding] = []
    if m := _WRITE_RE.search(question):
        findings.append(ScreenFinding(
            "WRITE_INTENT", "The question asks to change data or schema. MetricGuard only runs read-only, "
            "governed queries.", m.group(0)))
    if m := _RAW_SQL_RE.search(question):
        findings.append(ScreenFinding(
            "OUT_OF_SCOPE", "Raw SQL, SQL comments and system-catalog references are not accepted; ask in plain "
            "language about an approved metric.", m.group(0)))
    if m := _RELATIVE_TIME_RE.search(question):
        findings.append(ScreenFinding(
            "AMBIGUOUS_TIME_RANGE", f"\"{m.group(0)}\" is relative and has no anchor date; data covers "
            "2026-01-01..2026-06-30.", m.group(0)))
    if (m := _BARE_REVENUE_RE.search(question)) and not _REVENUE_QUALIFIERS_RE.search(question):
        findings.append(ScreenFinding(
            "AMBIGUOUS_METRIC", f"\"{m.group(1)}\" could mean gross_revenue or net_revenue.", m.group(1)))
    return findings
