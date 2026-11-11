"""Deterministic checks of a claim against a clause's RULE_JSON parameters.

The LLM judge reads meaning; this module reads numbers and a few yes/no permissions, the
details where a wrong answer costs money. It is built for precision, not recall: it can
only force a claim to CONTRADICTED (MISMATCH) or confirm the numbers line up (MATCH). It
never turns a contradiction into a pass, and when it cannot tell, it says NOT_APPLICABLE.

How RULE_JSON keys are read:
- the unit comes from the suffix (_usd, _pct, _hours, _days, _business_days, _months, _kg), or from the
  same word inside the key when nothing follows it as a unit (min_days_before_departure)
- keys starting with max_/min_ or containing _max_/_min_ are limits; the rest are values
- a few count keys (max_passengers, ...) are values counted in a noun (passenger, pet, ...)
- booleans are permissions, matched against a small lexicon of how claims express them
- "applies_when": {"delay_hours": [lo, hi]} marks the situation a tier covers, so a claim's
  "7 hours late" picks the tier instead of being compared as a policy value
- lists (eligible_relations, accepted_documents) are checked for membership: a claim that something the list
  leaves out qualifies, or that something it names does not, is a mismatch
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

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("usd", re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)", re.I)),
    ("usd", re.compile(rf"\b{_NUM_STRICT}\s?(?:dollars|usd)\b", re.I)),
    ("pct", re.compile(r"\b(\d+(?:\.\d+)?)\s?(?:%|percent\b)", re.I)),
    ("duration", re.compile(rf"\b{_NUM}[\s-]*(business[\s-]days?|working[\s-]days?|calendar[\s-]days?|days?|hours?|hrs?"
                            r"|weeks?|months?|years?)\b", re.I)),
    # "48 h", as a fare table writes hours (found onboarding SPR's policy text): digits only, never "a h".
    ("duration", re.compile(r"\b(\d+(?:\.\d+)?)\s?(h)\b", re.I)),
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
_FLAG_CUES: dict[str, re.Pattern[str]] = {
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
    if u.startswith(("business", "working", "calendar")) or u.startswith("day"):
        return (("days", value), ("hours", value * 24))
    if u.startswith(("hour", "hr")) or u == "h":
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
        if unit is None:  # a unit word inside the key: min_days_before_departure
            unit = next((u for suffix, u in _SUFFIXES if f"{suffix}_" in f"{key}_"), None)
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


# List parameters: what each one enumerates, written as the terms a claim may use, each mapped to the list's own
# entry. A term mapped to something the clause's list does not contain is outside it ("mother-in-law" -> "in-law").
# Only clear terms are here; ambiguous ones ("partner", "half-brother", "great-grandparent") are left to the judge.
_IN_LAW = "in-law"
_LIST_TERMS: dict[str, dict[str, str]] = {
    "eligible_relations": {
        **dict.fromkeys(("spouse", "husband", "wife"), "spouse"),
        "common-law partner": "common-law partner",
        **dict.fromkeys(("parent", "mother", "father", "mom", "mum", "dad"), "parent"),
        **dict.fromkeys(("step-parent", "stepparent", "stepmother", "stepfather", "step-mother", "step-father"),
                        "step-parent"),
        **dict.fromkeys(("child", "children", "son", "daughter"), "child"),
        **dict.fromkeys(("step-child", "stepchild", "stepchildren", "stepson", "stepdaughter"), "step-child"),
        **dict.fromkeys(("sibling", "brother", "sister"), "sibling"),
        **dict.fromkeys(("grandparent", "grandmother", "grandfather", "grandma", "grandpa"), "grandparent"),
        **dict.fromkeys(("grandchild", "grandchildren", "grandson", "granddaughter"), "grandchild"),
        **dict.fromkeys(("legal guardian", "guardian"), "legal guardian"),
        **dict.fromkeys(("mother-in-law", "father-in-law", "son-in-law", "daughter-in-law", "brother-in-law",
                         "sister-in-law", "in-law", "parents-in-law"), _IN_LAW),
        **{f"{whose}'s {rel}": _IN_LAW for whose in ("partner", "spouse", "wife", "husband", "fiance", "fiancee")
           for rel in ("mother", "father", "parent", "parents", "brother", "sister")},
        **{t: t for t in ("aunt", "uncle", "niece", "nephew", "cousin", "friend", "best friend", "fiance", "fiancee",
                          "fiancé", "fiancée", "boyfriend", "girlfriend", "coworker", "co-worker", "colleague",
                          "godmother", "godfather", "godparent", "neighbor", "neighbour")},
    },
    "accepted_documents": {
        "death certificate": "death certificate",
        **dict.fromkeys(("physician letter", "physician's letter", "doctor's letter", "doctor's note",
                         "letter from the attending physician", "letter from the physician", "letter from a physician",
                         "letter from her attending physician", "letter from his attending physician",
                         "letter from their attending physician", "letter from your attending physician",
                         "letter from the doctor"), "physician letter"),
        **dict.fromkeys(("funeral home letter", "letter from the funeral home", "letter from a funeral home"),
                        "funeral home letter"),
        **{t: t for t in ("obituary", "death notice", "newspaper notice", "funeral program", "memorial card",
                          "social media post", "note from a family member", "letter from a family member",
                          "statement from a family member", "family member's note", "family member's letter",
                          "email from a family member")},
    },
}
_LIST_PATTERN = {key: re.compile(r"\b(" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True))
                                 + r")(?:e?s)?\b", re.I) for key, terms in _LIST_TERMS.items()}
# A segment of the claim that says the thing qualifies, is accepted, or is covered.
_LIST_CUES = {
    "eligible_relations": re.compile(r"\b(count(?:s|ed)?\s+as|qualif\w*|eligible|considered|included|includes?|"
                                     r"cover(?:s|ed)?|immediate family|appl(?:y|ies))\b", re.I),
    "accepted_documents": re.compile(r"\b(accept\w*|enough|suffic\w*|works?|valid|qualif\w*|send|provide|submit|"
                                     r"use|proof|documentation)\b", re.I),
}


def _list_segments(claim: str, cue: re.Pattern[str]) -> list[tuple[str, bool]]:
    """The parts of a claim that say something qualifies, each with whether it is negated. A part between commas
    holding the cue counts on its own. A sentence whose cue and term sit in different parts ("Since she was your
    godmother, you are eligible") counts as a whole, but only when nothing in it is negated."""
    out: list[tuple[str, bool]] = []
    for sentence in re.split(r"[;.!?]|\bbut\b|\bhowever\b", claim):
        parts = re.split(r",\s", sentence)
        cued = [p for p in parts if cue.search(p)]
        out += [(p, bool(_NEGATION.search(p))) for p in cued]
        rest = " ".join(p for p in parts if not cue.search(p))
        if cued and rest and not _NEGATION.search(sentence):
            out.append((rest, False))
    return out


def list_checks(claim: str, clause: RuleClause) -> tuple[list[Status], list[str]]:
    """Membership in a list parameter (eligible_relations, accepted_documents). A claim that something the list
    leaves out qualifies, or that something it names does not, is a MISMATCH; agreeing with the list is a MATCH.
    Only a segment that says the thing qualifies or is accepted counts, and its negation is read from that segment."""
    statuses: list[Status] = []
    details: list[str] = []
    for key, listed in clause.rule.items():
        if key not in _LIST_TERMS or not isinstance(listed, list):
            continue
        members = {str(x).casefold() for x in listed}
        for segment, negated in _list_segments(claim, _LIST_CUES[key]):
            for m in _LIST_PATTERN[key].finditer(segment):
                canonical = _LIST_TERMS[key][m.group(1).casefold()]
                inside = canonical.casefold() in members
                if inside != negated:
                    statuses.append("MATCH")
                elif inside:
                    statuses.append("MISMATCH")
                    details.append(f"claim says {m.group(0)} does not qualify; {clause.clause_id} {key} includes {canonical}")
                else:
                    statuses.append("MISMATCH")
                    details.append(f"claim says {m.group(0)} qualifies; {clause.clause_id} {key} lists only "
                                   + ", ".join(str(x) for x in listed))
    return statuses, details


def _situation(rule: dict[str, Any]) -> dict[str, tuple[float, float | None]]:
    out = {}
    for key, bounds in (rule.get("applies_when") or {}).items():
        if key in _SITUATION_UNITS and isinstance(bounds, list) and len(bounds) == 2:
            out[key] = (float(bounds[0]), None if bounds[1] is None else float(bounds[1]))
    return out


# How a text states this customer's situation for a tiered key: "arrived 7 hours late", "a 7-hour delay",
# "delayed by 7 hours". A threshold ("9 hours or more", "at least 9 hours") is a rule, not the situation.
_SITUATION_TEXT = {
    "delay_hours": re.compile(
        rf"\b(?:delayed\s+(?:by\s+)?)?{_NUM_STRICT}[\s-]*(?:hours?|hrs?)"
        r"(?=\s+(?:late|behind)\b|[\s-]+delay(?:ed)?\b)(?![\s-]+(?:or|and)\s+(?:more|longer|over|less))"
        rf"|\bdelayed\s+(?:by\s+)?{_NUM_STRICT}[\s-]*(?:hours?|hrs?)\b", re.I),
}


def situation_values(text: str, key: str) -> list[float]:
    out = []
    for m in _SITUATION_TEXT[key].finditer(text):
        start = m.start()
        if _LIMIT_BEFORE.search(text[max(0, start - 25):start]):
            continue
        out.append(_number(next(g for g in m.groups() if g)))
    return out


def situation_conflicts(claim: str, question: str) -> tuple[str, ...]:
    """The claim states this customer's situation differently from how the customer stated it.

    Deterministic, and only when the question states that situation: a claim that says "you arrived
    10 hours late" when the customer wrote "my flight was 2 hours late" picks the wrong tier, however
    well its amount matches that tier."""
    out = []
    for key in _SITUATION_TEXT:
        asked = situation_values(question, key)
        if not asked:
            continue
        for v in situation_values(claim, key):
            if not any(_close(v, a, _SITUATION_UNITS[key]) for a in asked):
                out.append(f"claim says {v:g} {_SITUATION_UNITS[key]}; the customer said "
                           + ", ".join(f"{a:g}" for a in asked))
    return tuple(out)


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
        qs = [(i, q, v) for i, q in enumerate(quantities)
              if i not in situational and (v := q.value_in(unit)) is not None]
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

    # 4. Lists: membership in eligible_relations, accepted_documents.
    list_statuses, list_details = list_checks(claim, clause)
    statuses += list_statuses
    details += list_details

    if "MISMATCH" in statuses:
        return RuleResult("MISMATCH", tuple(details))
    if "MATCH" in statuses:
        return RuleResult("MATCH", tuple(details))
    return RuleResult("NOT_APPLICABLE", tuple(details))


# ---- Time bands: a charge that depends on how long before departure a cancellation is made ---------------------
# RULE_JSON "time_bands" is a list of bands of T, the time from the cancellation request to the scheduled departure,
# in hours: {"from_h": 12, "to_h": 48, "charge_inr": {"1A": 120, ...}}. from_h is inclusive ("at least 12 hours"
# includes 12 h 00 min), to_h exclusive, either may be left out for an open end. A band states one outcome: a flat
# charge per class ("charge_inr"), a charge as a percentage of the fare ("charge_pct"), or "refund": false. Added
# after the first unseen-domain run (SPR's fare tables); a clause without "time_bands" is never checked here.
BAND_KEYS = {"from_h", "to_h", "charge_inr", "charge_pct", "refund"}
CLASSES = {"1a": "1A", "ac first": "1A", "first ac": "1A", "2a": "2A", "ac two tier": "2A", "ac 2 tier": "2A",
           "two tier": "2A", "sl": "SL", "sleeper": "SL", "2s": "2S", "second sitting": "2S"}
_CLASS = re.compile(r"\b(1a|2a|sl|2s|ac first|first ac|ac two tier|ac 2 tier|two tier|sleeper|second sitting)\b", re.I)
_HM = r"(\d+(?:\.\d+)?)\s*(?:h|hrs?|hours?)(?:\s*(?:and\s*)?(\d+)\s*(?:m|mins?|minutes?))?"
_T_PATTERN = re.compile(
    rf"\b(?:{_HM}|(\d+)\s*(?:mins?|minutes?)|(\d+)\s*(?:days?))\b"
    r"(?=\s*(?:before|ahead|out\b|prior|left|remaining|to\s+(?:go|departure)|until)|\s+(?:early|in advance))", re.I)
_INR = re.compile(r"(?:INR|Rs\.?|₹)\s?(\d{1,3}(?:,\d{3})+|\d+)", re.I)
_FARE = re.compile(r"(?:(?:base\s+)?fare(?:\s+(?:of|is|was))?\s*:?\s*(?:INR|Rs\.?|₹)\s?(\d{1,3}(?:,\d{3})+|\d+))"
                   r"|(?:(?:INR|Rs\.?|₹)\s?(\d{1,3}(?:,\d{3})+|\d+)\s*(?:base\s+)?fare)"
                   r"|(?:for\s+(?:INR|Rs\.?|₹)\s?(\d{1,3}(?:,\d{3})+|\d+))", re.I)
_NO_REFUND = re.compile(r"\bno (?:voluntary )?refund\b|\bnon-?refundable\b|\bnothing back\b|\bnot (?:be )?refunded\b"
                        r"|\bno money back\b|\bget nothing\b", re.I)
_REFUND_CUE = re.compile(r"\b(?:refund\w*|back|receive|get|return\w*|recover)\b", re.I)
_CHARGE_CUE = re.compile(r"\b(?:charge\w*|deduct\w*|fee|cost\w*|penalty|pay)\b", re.I)
_FEE_ONLY = re.compile(r"\b(?:booking|service)\s+(?:service\s+)?fee\b|\bclerkage\b", re.I)
_RESULT_CUE = re.compile(r"\b(?:resulting in|leaving|leaves|left with|comes to|so you (?:get|receive))\b[^.;]{0,30}$", re.I)


def validate_time_bands(value: Any) -> None:
    """Raise ValueError unless `value` is a well-formed time_bands list (used where RULE_JSON is accepted)."""
    if not isinstance(value, list) or not 1 <= len(value) <= 8:
        raise ValueError("time_bands must be a list of 1 to 8 bands")
    for band in value:
        if not isinstance(band, dict) or not set(band) <= BAND_KEYS:
            raise ValueError(f"a time band may only have {sorted(BAND_KEYS)}")
        for k in ("from_h", "to_h", "charge_pct"):
            if k in band and (isinstance(band[k], bool) or not isinstance(band[k], (int, float)) or band[k] < 0):
                raise ValueError(f"time band {k} must be a number of at least 0")
        outcomes = [k for k in ("charge_inr", "charge_pct", "refund") if k in band]
        if len(outcomes) != 1:
            raise ValueError("a time band states exactly one of charge_inr, charge_pct, refund")
        if "refund" in band and band["refund"] is not False:
            raise ValueError("time band refund may only be false")
        if "charge_inr" in band and not (isinstance(band["charge_inr"], dict) and band["charge_inr"] and all(
                k in CLASSES.values() and isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0
                for k, v in band["charge_inr"].items())):
            raise ValueError(f"time band charge_inr maps a class ({sorted(set(CLASSES.values()))}) to an amount")


def _amount(token: str) -> float:
    return float(token.replace(",", ""))


def time_before_departure(text: str) -> list[float]:
    """Every cancellation time T stated in `text`, in hours ("2 hours 59 minutes before departure", "35h59m ahead",
    "exactly 3 hours before", "8 days before"). A limit ("at least 36 hours before") is a rule, not a time."""
    out = []
    for m in _T_PATTERN.finditer(text):
        before = text[max(0, m.start() - 25):m.start()]
        if _LIMIT_BEFORE.search(before) or re.search(r"(?:\d\s*(?:h|hours?)?\s*(?:to|-|and)|between)\s*$", before, re.I):
            continue  # a limit ("at least 36 hours before") or a range ("4 to 12 hours before") is a rule
        hours, minutes, only_minutes, days = m.group(1), m.group(2), m.group(3), m.group(4)
        if hours is not None:
            out.append(float(hours) + (float(minutes) / 60 if minutes else 0.0))
        elif only_minutes is not None:
            out.append(float(only_minutes) / 60)
        else:
            out.append(float(days) * 24)
    return out


def _one(values: list[Any]) -> Any:
    distinct = set(values)
    return next(iter(distinct)) if len(distinct) == 1 else None


def band_for(bands: list[dict[str, Any]], hours: float) -> dict[str, Any] | None:
    """The band T falls in: from_h <= T < to_h, minutes counted exactly, so 2 h 59 min is below a 3 h edge."""
    eps = 1e-9
    return next((b for b in bands if (b.get("from_h") is None or hours >= b["from_h"] - eps)
                 and (b.get("to_h") is None or hours < b["to_h"] - eps)), None)


def _describe(band: dict[str, Any]) -> str:
    lo, hi = band.get("from_h"), band.get("to_h")
    span = (f"{lo:g} <= T < {hi:g} h" if lo is not None and hi is not None else
            f"T >= {lo:g} h" if lo is not None else f"T < {hi:g} h" if hi is not None else "any T")
    if "refund" in band:
        return f"{span}: no refund"
    if "charge_pct" in band:
        return f"{span}: a {band['charge_pct']:g}% charge"
    return f"{span}: charge " + ", ".join(f"{c} INR {v:g}" for c, v in band["charge_inr"].items())


def band_check(claim: str, question: str, rule: dict[str, Any], clause_id: str = "") -> RuleResult:
    """Check a claim's charge or refund against the band its cancellation time falls in.

    The time T comes from the claim, or else from the customer's question; the class and the fare likewise. With no
    single T, or a clause with no time_bands, the result is NOT_APPLICABLE. MISMATCH when the claim promises a refund
    in a no-refund band, says there is no refund in a band with one, or states a charge or refund (percentage, or
    rupees when the class and fare are known) that is not the band's."""
    bands = rule.get("time_bands")
    if not isinstance(bands, list):
        return RuleResult("NOT_APPLICABLE")
    t = _one(time_before_departure(claim)) if time_before_departure(claim) else _one(time_before_departure(question))
    if t is None:
        return RuleResult("NOT_APPLICABLE")
    band = band_for(bands, t)
    if band is None:
        return RuleResult("NOT_APPLICABLE")
    cls = _one([CLASSES[m.group(1).lower()] for m in _CLASS.finditer(claim)]) or _one(
        [CLASSES[m.group(1).lower()] for m in _CLASS.finditer(question)])
    fares = [_amount(next(g for g in m.groups() if g)) for m in _FARE.finditer(question)]
    fare = _one(fares)
    where = f"T = {int(t)} h {round((t - int(t)) * 60):02d} min falls in {clause_id} {_describe(band)}"
    # "The booking service fee is not refunded" is about the fee, not the fare: only other sentences count.
    said_none = any(_NO_REFUND.search(x) and not _FEE_ONLY.search(x) for x in re.split(r"[.;!?]", claim))
    pcts = [(float(m.group(1)), m.span()) for m in re.finditer(r"\b(\d+(?:\.\d+)?)\s?(?:%|percent\b)", claim)]
    rupees = [(_amount(m.group(1)), m.span()) for m in _INR.finditer(claim)]

    def cue(span: tuple[int, int]) -> str | None:
        """Whether an amount is a charge or a refund: the nearer cue word within 40 characters decides."""
        def gap(pattern: re.Pattern[str]) -> int | None:
            gaps = [max(m.start() - span[1], span[0] - m.end(), 0) for m in pattern.finditer(claim)]
            near = [g for g in gaps if g <= 40]
            return min(near) if near else None
        if _RESULT_CUE.search(claim[max(0, span[0] - 40):span[0]]) or re.match(r"\s*(?:back|refund)", claim[span[1]:]):
            return "refund"  # "... minus this charge, resulting in INR 800", "INR 800 back"
        refund, charge = gap(_REFUND_CUE), gap(_CHARGE_CUE)
        if refund is None or (charge is not None and charge < refund):
            return None if charge is None else "charge"
        return "refund" if charge is None or refund < charge else None

    statuses: list[Status] = []
    if "refund" in band:
        if said_none:
            statuses.append("MATCH")
        elif pcts or any(a != fare and cue(span) == "refund" for a, span in rupees):
            return RuleResult("MISMATCH", (f"{where}; the claim states a charge or refund",))
        return RuleResult(statuses[0] if statuses else "NOT_APPLICABLE", (where,))
    if "charge_pct" in band:
        p = float(band["charge_pct"])
        expected = {"charge": p, "refund": 100 - p}
        money = None if fare is None else {"charge": fare * p / 100, "refund": fare * (100 - p) / 100}
    else:
        flat = band["charge_inr"].get(cls) if cls else None
        expected = {}
        if flat is not None and pcts:
            return RuleResult("MISMATCH", (f"{where}; the claim states a percentage",))
        charge = None if flat is None else (min(float(flat), fare) if fare is not None else float(flat))
        money = None if charge is None else {"charge": charge, **({"refund": fare - charge} if fare is not None else {})}
    if said_none:
        refund_left = money.get("refund") if money else None
        if refund_left is None and "charge_pct" in band:
            refund_left = 100 - float(band["charge_pct"])
        if refund_left is not None and refund_left > 0:
            return RuleResult("MISMATCH", (f"{where}; the claim says there is no refund",))
        if refund_left is not None:
            statuses.append("MATCH")  # the flat charge takes the whole fare
    for value, span in pcts:
        kind = cue(span)
        if kind and expected:
            statuses.append("MATCH" if _close(value, expected[kind], "pct") else "MISMATCH")
    for value, span in rupees:
        kind = cue(span)
        if value == fare or kind is None or not money or kind not in money:
            continue
        statuses.append("MATCH" if abs(value - money[kind]) < 0.5 else "MISMATCH")
    if "MISMATCH" in statuses:
        return RuleResult("MISMATCH", (f"{where}; the claim's charge or refund is not this band's",))
    return RuleResult("MATCH" if statuses else "NOT_APPLICABLE", (where,))
