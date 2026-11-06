"""Deterministic checks of a claim against a clause's RULE_JSON parameters.

The LLM judge reads meaning; this module reads numbers and a few yes/no permissions, the
details where a wrong answer costs money. It is built for precision, not recall: it can
only force a claim to CONTRADICTED (MISMATCH) or confirm the numbers line up (MATCH). It
never turns a contradiction into a pass, and when it cannot tell, it says NOT_APPLICABLE.

How RULE_JSON keys are read:
- the unit comes from the suffix: _usd, _pct, _hours, _days, _business_days, _months, _kg, _chars
- keys starting with max_/min_ or containing _max_/_min_ are limits; the rest are values
- a few count keys (max_passengers, ...) are values counted in a noun (passenger, pet, ...)
- booleans are permissions, matched against a small lexicon of how claims express them
- "applies_when": {"delay_hours": [lo, hi]} marks the situation a tier covers, so a claim's
  "7 hours late" picks the tier instead of being compared as a policy value
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

Status = Literal["MATCH", "MISMATCH", "NOT_APPLICABLE"]

_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
          "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
_NUM_STRICT = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
# "a"/"an" count as 1 only before a duration ("a year", "an hour"), never before a noun or weight.
_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|an?)"
_LIMIT_BEFORE = re.compile(
    r"\b(up to|no more than|not more than|maximum(?: of)?|max|at most|less than|fewer than|under|over|more than|"
    r"at least|minimum(?: of)?|within|longer than|exceeding|exceeds?|beyond|above|below)\s*\$?\s*$",
    re.I,
)
# After the cue only a negated verb counts ("requests after travel aren't accepted");
# "without"/"no" there usually qualify something else ("after travel, without a fee").
_VERB_NEGATION = re.compile(r"\b(?:is|are|was|were|will|can|could|do|does)\s+not\b"
                            r"|\b(?:isn't|aren't|wasn't|weren't|won't|can't|cannot|doesn't|don't)\b", re.I)
_NEGATION = re.compile(r"\b(not|cannot|can ?not|no|never|none|without|unable|ineligible|nor)\b|n't\b", re.I)
_FREE = re.compile(r"\b(free(?: of charge)?|no (?:change )?(?:fee|charge|cost)|at no (?:extra )?cost"
                   r"|without charge|no extra cost)\b", re.I)

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("usd", re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)", re.I)),
    ("usd", re.compile(rf"\b{_NUM_STRICT}\s?(?:dollars|usd)\b", re.I)),
    ("pct", re.compile(r"\b(\d+(?:\.\d+)?)\s?(?:%|percent\b)", re.I)),
    ("duration", re.compile(rf"\b{_NUM}[\s-]*(business[\s-]days?|working[\s-]days?|days?|hours?|hrs?|weeks?|months?"
                            r"|years?)\b", re.I)),
    ("kg", re.compile(rf"\b{_NUM_STRICT}\s?(?:kg|kgs|kilograms?|kilos?)\b", re.I)),
    ("count", re.compile(rf"\b{_NUM_STRICT}\s+((?:[a-z-]+\s+){{0,2}}?)"
                         r"(passengers?|people|persons?|travell?ers?|credits?|pets?|animals?|items?|characters?|letters?"
                         r"|fees?|refunds?|reversals?)\b",
                         re.I)),
]
_RELATIVE = re.compile(r"\b(additional|other|more|extra|further|accompanying)\b", re.I)
_NOUNS = {"passenger": "passenger", "people": "passenger", "person": "passenger", "traveler": "passenger",
          "traveller": "passenger", "credit": "credit", "pet": "pet", "animal": "pet", "item": "item",
          "character": "character", "letter": "character", "fee": "fee", "refund": "refund", "reversal": "refund"}
_COUNT_KEYS = {"max_passengers": "passenger", "max_credits_per_booking": "credit", "max_pets_per_passenger": "pet",
               "max_pets_per_flight": "pet", "personal_items": "item", "free_name_correction_chars": "character",
               # Fernhollow Bank (the second domain); keys that only its fee schedule uses
               "max_overdraft_fees_per_day": "fee", "courtesy_refunds_per_year": "refund"}
_SUFFIXES = [("_business_days", "days"), ("_days", "days"), ("_hours", "hours"), ("_months", "months"),
             ("_usd", "usd"), ("_pct", "pct"), ("_kg", "kg")]
_SITUATION_UNITS = {"delay_hours": "hours"}

# How claims typically express each permission. A cue in a negated phrase means False.
_FLAG_CUES: dict[str, re.Pattern] = {
    "retroactive_allowed": re.compile(
        r"retroactiv|after (?:you(?:'ve| have)? )?(?:travel|fl(?:y|ew|own)|complet)"
        r"|after (?:your|the) (?:trip|flight|journey|travel)"
        r"|once (?:you(?:'ve| have) )?(?:travel|flown|flew)|already (?:travel|flown|flew)", re.I),
    "request_before_travel_required": re.compile(
        r"(?:must|have to|need to|only)\b.{0,30}\bbefore (?:you )?(?:travel|fly|departure|the (?:trip|flight|journey))", re.I),
    "name_change_allowed": re.compile(r"transfer|name change|change the name|to (?:another|someone else|a friend)", re.I),
    "transfer_allowed": re.compile(r"transfer|to (?:another (?:person|passenger)|someone else|a friend)", re.I),
    "cash_out_allowed": re.compile(r"cash(?: it| them)? out|cash value|exchang\w*(?: it| them)? for (?:cash|money|a refund)"
                                   r"|in cash|as cash", re.I),
    "changes_allowed": re.compile(r"\b(?:chang|upgrad|modif)", re.I),
    "compensation_allowed": re.compile(r"compensat|qualif|entitled|eligible for (?:a )?(?:payment|compensation)", re.I),
    "airport_booking_allowed": re.compile(r"\bairport", re.I),
    "travel_agency_allowed": re.compile(r"travel agen", re.I),
    "business_class_allowed": re.compile(r"\bbusiness(?: class)?\b", re.I),
    "fare_difference_applies": re.compile(r"fare difference|difference in (?:the )?fare", re.I),
    # Fernhollow Bank
    "automatic_refund": re.compile(r"\bautomatic|without (?:you )?(?:having to )?(?:ask|request)", re.I),
}


@dataclass(frozen=True)
class Quantity:
    forms: tuple[tuple[str, float], ...]  # the same amount in every unit it can be compared in
    limit: bool                           # stated as a limit: "up to 8 kg", "within 90 days"
    text: str

    def units(self) -> set[str]:
        return {u for u, _ in self.forms}

    def value_in(self, unit: str) -> float | None:
        return next((v for u, v in self.forms if u == unit), None)


@dataclass(frozen=True)
class Param:
    key: str
    unit: str
    value: float
    limit: bool


@dataclass(frozen=True)
class RuleClause:
    clause_id: str
    rule: dict[str, Any]


@dataclass(frozen=True)
class RuleResult:
    status: Status
    details: tuple[str, ...] = field(default_factory=tuple)
    clause_id: str | None = None  # set when the claim belongs to a different tier than the cited clause


def _number(token: str) -> float:
    token = token.lower().replace(",", "")
    return float(_WORDS[token]) if token in _WORDS else float(token)


def _forms(value: float, unit_word: str) -> tuple[tuple[str, float], ...]:
    u = unit_word.lower().replace("-", " ")
    if u.startswith(("business", "working")) or u.startswith("day"):
        return (("days", value), ("hours", value * 24))
    if u.startswith(("hour", "hr")):
        return (("hours", value),)
    if u.startswith("week"):
        return (("days", value * 7),)
    if u.startswith("month"):
        return (("months", value), ("days", round(value * 365 / 12)))
    if u.startswith("year"):
        return (("days", value * 365), ("months", value * 12))
    raise ValueError(unit_word)


def extract_quantities(text: str) -> list[Quantity]:
    """Every amount, percentage, duration, weight and count in a claim, with its unit."""
    found: list[tuple[int, int, Quantity]] = []

    def taken(start: int, end: int) -> bool:
        return any(start < e and s < end for s, e, _ in found)

    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if taken(m.start(), m.end()):
                continue
            limit = bool(_LIMIT_BEFORE.search(text[max(0, m.start() - 25):m.start()]))
            value = _number(m.group(1))
            if kind == "duration":
                forms = _forms(value, m.group(2))
            elif kind == "count":
                # "three additional passengers" is relative to someone else, not a total.
                if _RELATIVE.search(m.group(2)):
                    continue
                noun = m.group(3).lower().rstrip("s")
                forms = ((f"count:{_NOUNS.get(noun, noun)}", value),)
            else:
                forms = ((kind, value),)
            found.append((m.start(), m.end(), Quantity(forms, limit, m.group(0))))
    for m in _FREE.finditer(text):
        if not re.search(r"\bnot\s+$|n't\s+$", text[max(0, m.start() - 8):m.start()], re.I):
            found.append((m.start(), m.end(), Quantity((("usd", 0.0),), False, m.group(0))))
    return [q for _, _, q in sorted(found, key=lambda t: t[0])]


def rule_params(rule: dict[str, Any]) -> list[Param]:
    params: list[Param] = []
    for key, value in rule.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        is_limit = key.startswith(("max_", "min_")) or "_max_" in key or "_min_" in key
        if key in _COUNT_KEYS:
            params.append(Param(key, f"count:{_COUNT_KEYS[key]}", float(value), limit=False))
            continue
        unit = next((u for suffix, u in _SUFFIXES if key.endswith(suffix)), None)
        if unit:
            params.append(Param(key, unit, float(value), is_limit))
    return params


def asserted_flag(claim: str, key: str) -> bool | None:
    """True/False if the claim states this permission, None if it does not mention it."""
    cue = _FLAG_CUES.get(key)
    if cue is None:
        return None
    for segment in re.split(r"[;.!?]|,\s|\bbut\b|\bhowever\b", claim):
        m = cue.search(segment)
        if m:
            negated = _NEGATION.search(segment[: m.start()]) or _VERB_NEGATION.search(segment[m.end():])
            return not negated
    return None


def _situation(rule: dict[str, Any]) -> dict[str, tuple[float, float | None]]:
    out = {}
    for key, bounds in (rule.get("applies_when") or {}).items():
        if key in _SITUATION_UNITS and isinstance(bounds, list) and len(bounds) == 2:
            out[key] = (float(bounds[0]), None if bounds[1] is None else float(bounds[1]))
    return out


def _in_range(value: float, lo: float, hi: float | None) -> bool:
    return value >= lo and (hi is None or value < hi)


def _close(a: float, b: float, unit: str) -> bool:
    return abs(a - b) <= (1.0 if unit == "days" and max(a, b) > 60 else 1e-6)


def check(claim: str, clause: RuleClause, candidates: Sequence[RuleClause] = (), _depth: int = 0) -> RuleResult:
    """Compare one claim with one clause's rule parameters."""
    quantities = extract_quantities(claim)
    situational: set[int] = set()

    # 1. Tiered clauses: find the tier the claim's situation falls in.
    for key, (lo, hi) in _situation(clause.rule).items():
        unit = _SITUATION_UNITS[key]
        for i, q in enumerate(quantities):
            v = q.value_in(unit)
            if v is None or q.limit:
                continue
            if _in_range(v, lo, hi):
                situational.add(i)
                continue
            if _depth == 0:
                for other in candidates:
                    rng = _situation(other.rule).get(key)
                    if other.clause_id != clause.clause_id and rng and _in_range(v, *rng):
                        res = check(claim, other, candidates, _depth=1)
                        note = f"{q.text} falls under {other.clause_id}, not {clause.clause_id}"
                        return RuleResult(res.status, (note, *res.details), other.clause_id)
            return RuleResult("NOT_APPLICABLE", (f"{q.text} is outside the situation {clause.clause_id} covers",))

    # 2. Numbers, per unit: one matching amount is enough; the rest may describe the situation.
    params = rule_params(clause.rule)
    statuses: list[Status] = []
    details: list[str] = []
    units = {u for i, q in enumerate(quantities) if i not in situational for u in q.units()}
    # An amount that matches a parameter in one of its units is settled: "a 12-month period" that
    # matches period_months=12 is not also a wrong number of days.
    settled = {i for i, q in enumerate(quantities) if i not in situational
               and any(p.unit == u and _close(v, p.value, u) for u, v in q.forms for p in params)}
    for unit in sorted(units):
        qs = [(i, q, q.value_in(unit)) for i, q in enumerate(quantities)
              if i not in situational and q.value_in(unit) is not None]
        values = [p for p in params if p.unit == unit and not p.limit]
        limits = [p for p in params if p.unit == unit and p.limit]
        if not values and not limits:
            continue
        if any(_close(v, p.value, unit) for _, _, v in qs for p in values + limits):
            statuses.append("MATCH")
            continue
        qs = [(i, q, v) for i, q, v in qs if i not in settled]
        if not qs:
            continue
        claimed = ", ".join(q.text for _, q, _ in qs)
        if values:
            statuses.append("MISMATCH")
            details.append(f"claim says {claimed}; {clause.clause_id} says "
                           + ", ".join(f"{p.key}={p.value:g}" for p in values))
        elif any(q.limit for _, q, _ in qs):
            statuses.append("MISMATCH")
            details.append(f"claim states the limit {claimed}; {clause.clause_id} limits are "
                           + ", ".join(f"{p.key}={p.value:g}" for p in limits))

    # 3. Permissions.
    for key, expected in clause.rule.items():
        if not isinstance(expected, bool):
            continue
        said = asserted_flag(claim, key)
        if said is None:
            continue
        if said == expected:
            statuses.append("MATCH")
        else:
            statuses.append("MISMATCH")
            details.append(f"claim implies {key}={str(said).lower()}; {clause.clause_id} says {str(expected).lower()}")

    if "MISMATCH" in statuses:
        return RuleResult("MISMATCH", tuple(details))
    if "MATCH" in statuses:
        return RuleResult("MATCH", tuple(details))
    return RuleResult("NOT_APPLICABLE", tuple(details))
