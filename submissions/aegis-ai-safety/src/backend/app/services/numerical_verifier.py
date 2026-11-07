"""Deterministic, explainable numeric checks against cited evidence.

This module does not decide truth. It extracts simple numeric expressions from a
claim and compares them literally with the passages the model cited. It is
deliberately conservative: percentages, BLEU scores, parameter counts, layer and
head counts, GPUs, days, and word counts only. Advanced statistics are out of
scope.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.models.domain import PassageCandidate

_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_ENTITY = re.compile(r"\bBERT[\s-]?(base|large)\b|\bBERT(BASE|LARGE)\b", re.IGNORECASE)

_UNIT_PATTERNS = [
    ("percent", re.compile(rf"(?P<value>{_NUMBER})\s*(?:%|percent(?:age)?\s*points?)", re.IGNORECASE)),
    ("BLEU", re.compile(rf"(?P<value>{_NUMBER})\s*BLEU\b", re.IGNORECASE)),
    ("BLEU", re.compile(rf"BLEU(?: score)?(?: of)?\s*(?P<value>{_NUMBER})", re.IGNORECASE)),
    (
        "million parameters",
        re.compile(
            rf"(?P<value>{_NUMBER})\s*(?P<scale>million|billion|M|B)\s*(?:total\s+)?(?:parameters|params)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "million parameters",
        re.compile(
            rf"(?:parameters|params)\s*[=:]?\s*(?P<value>{_NUMBER})\s*(?P<scale>million|billion|M|B)\b",
            re.IGNORECASE,
        ),
    ),
    ("layers", re.compile(rf"(?P<value>\d+)\s*(?:identical\s+)?layers?\b", re.IGNORECASE)),
    ("heads", re.compile(rf"(?P<value>\d+)\s*(?:parallel\s+)?(?:attention\s+)?heads?\b", re.IGNORECASE)),
    ("GPUs", re.compile(rf"(?P<value>\d+)\s*(?:P100\s+)?GPUs?\b", re.IGNORECASE)),
    ("days", re.compile(rf"(?P<value>{_NUMBER})\s*days?\b", re.IGNORECASE)),
    ("times", re.compile(rf"(?P<value>{_NUMBER})\s*(?:times\b|[x×])", re.IGNORECASE)),
    (
        "megabytes",
        re.compile(rf"(?P<value>{_NUMBER})\s*(?P<scale>TB|GB|MB)\b", re.IGNORECASE),
    ),
    (
        "million words",
        re.compile(rf"(?P<value>{_NUMBER})\s*(?P<scale>billion|million|M|B)\s*words?\b", re.IGNORECASE),
    ),
]


@dataclass(slots=True)
class NumericMention:
    value: float
    unit: str
    display: str
    entity: str | None = None
    passage_id: int | None = None


@dataclass(slots=True)
class NumericCheckResult:
    summary: str | None
    discrepancies: list[str]
    matches: list[str]
    discrepant_passage_ids: list[int] = field(default_factory=list)
    discrepancy_units: list[str] = field(default_factory=list)

    @property
    def has_discrepancy(self) -> bool:
        return bool(self.discrepancies)

    @property
    def override_eligible(self) -> bool:
        # Percentages are context-dependent (accuracy, prevalence, cost, etc.).
        # Use them for explanation but do not let a bare percent mismatch
        # deterministically override the model's classification.
        return any(unit != "percent" for unit in self.discrepancy_units)


def _normalized_value(value: str, scale: str | None, unit: str) -> tuple[float, str]:
    number = float(value.replace(",", ""))
    if unit == "million parameters":
        factor = 1000.0 if (scale or "").lower() in ("billion", "b") else 1.0
        return number * factor, "million parameters"
    if unit == "million words":
        factor = 1000.0 if (scale or "").lower() in ("billion", "b") else 1.0
        return number * factor, "million words"
    if unit == "megabytes":
        factor = {"tb": 1_000_000.0, "gb": 1000.0, "mb": 1.0}.get((scale or "").lower(), 1.0)
        return number * factor, "megabytes"
    return number, unit


def _entity_at(text: str, start: int, end: int) -> str | None:
    preceding: tuple[int, str] | None = None
    following: tuple[int, str] | None = None
    for match in _ENTITY.finditer(text):
        entity = (match.group(1) or match.group(2) or "").lower()
        if not entity:
            continue
        if match.end() <= start and start - match.end() <= 120:
            if preceding is None or match.end() > preceding[0]:
                preceding = (match.end(), entity)
        elif match.start() >= end and match.start() - end <= 120:
            if following is None or match.start() < following[0]:
                following = (match.start(), entity)
    if preceding is not None:
        return preceding[1]
    return following[1] if following else None


def extract_mentions(text: str, passage_id: int | None = None) -> list[NumericMention]:
    mentions: list[NumericMention] = []
    seen: set[tuple[float, str, str | None]] = set()
    for unit, pattern in _UNIT_PATTERNS:
        for match in pattern.finditer(text):
            value, normalized_unit = _normalized_value(
                match.group("value"), match.groupdict().get("scale"), unit
            )
            entity = _entity_at(text, match.start(), match.end())
            key = (round(value, 6), normalized_unit, entity)
            if key in seen:
                continue
            seen.add(key)
            mentions.append(
                NumericMention(
                    value=value,
                    unit=normalized_unit,
                    display=" ".join(match.group(0).split()),
                    entity=entity,
                    passage_id=passage_id,
                )
            )
    return mentions


def _format_values(mentions: list[NumericMention]) -> str:
    values = []
    for mention in mentions:
        passage = f" (passage {mention.passage_id})" if mention.passage_id is not None else ""
        values.append(f"{mention.display}{passage}")
    return ", ".join(dict.fromkeys(values))


def check_numerics(claim_text: str, passages: list[PassageCandidate]) -> NumericCheckResult:
    claim_mentions = extract_mentions(claim_text)
    if not claim_mentions:
        return NumericCheckResult(summary=None, discrepancies=[], matches=[])

    evidence_mentions: list[NumericMention] = []
    for passage in passages:
        evidence_mentions.extend(
            extract_mentions(passage.passage_text, passage_id=passage.passage_id)
        )

    lines: list[str] = []
    discrepancies: list[str] = []
    matches: list[str] = []
    discrepant_passage_ids: list[int] = []
    discrepancy_units: list[str] = []
    for claim in claim_mentions:
        same_unit = [item for item in evidence_mentions if item.unit == claim.unit]
        if not same_unit:
            lines.append(
                f"Claim states '{claim.display}'; no matching {claim.unit} value appears in the cited evidence."
            )
            continue

        same_entity = [
            item
            for item in same_unit
            if claim.entity is not None and item.entity == claim.entity
        ]
        candidates = same_entity or same_unit
        values = [item.value for item in candidates]
        if any(abs(claim.value - value) < 1e-6 for value in values):
            line = (
                f"Claim states '{claim.display}'; a matching value appears in the cited evidence "
                f"({_format_values(candidates)}). This is a consistency check, not proof of support."
            )
            lines.append(line)
            matches.append(line)
        else:
            scope = f" for {claim.entity.upper()}" if claim.entity else ""
            line = (
                f"Claim states '{claim.display}'; cited evidence gives "
                f"{_format_values(candidates)}{scope}."
            )
            lines.append(line)
            discrepancies.append(line)
            discrepancy_units.append(claim.unit)
            for item in candidates:
                if item.passage_id is not None and item.passage_id not in discrepant_passage_ids:
                    discrepant_passage_ids.append(item.passage_id)

    summary = "Deterministic numeric check: " + " ".join(lines) if lines else None
    return NumericCheckResult(
        summary=summary,
        discrepancies=discrepancies,
        matches=matches,
        discrepant_passage_ids=discrepant_passage_ids,
        discrepancy_units=discrepancy_units,
    )


def analyze_numerics(claim_text: str, passages: list[PassageCandidate]) -> str | None:
    """Backward-compatible summary string used by callers and tests."""
    return check_numerics(claim_text, passages).summary
