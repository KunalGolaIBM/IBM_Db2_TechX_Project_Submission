"""Deterministic intent analysis for DBA questions (no LLM required).

Order matters and encodes the safety posture: destructive requests are
detected FIRST and refused; everything else maps to a diagnostic plan.
Rules are plain regular expressions so behaviour is explainable and tested.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

Intent = str  # see INTENTS

INTENTS = (
    "destructive",
    "explain",
    "maintenance",
    "locks",
    "connections",
    "memory",
    "indexes",
    "statistics",
    "schema",
    "performance",
    "unknown",
)

_I = re.IGNORECASE

# Destructive / privileged requests the agent must refuse to improvise SQL for.
_DESTRUCTIVE = re.compile(
    r"\b(drop\s+(table|index|database|schema|view|column|tablespace)"
    r"|delete\s+from"
    r"|truncate\b"
    r"|alter\s+(table|database|tablespace)"
    r"|update\s+[\w.$#@]+\s+set"
    r"|insert\s+into"
    r"|grant\s+\w+"
    r"|revoke\s+\w+"
    r"|force\s+application"
    r"|kill\s+(the\s+)?(session|connection|application)"
    r"|restore\s+database"
    r"|deactivate\s+database)\b",
    _I,
)

_EXPLAIN = re.compile(
    r"\bexplain\b(?:\s+(?:plan|query|statement|sql))?\s*[:\-]?\s*((?:select|with)\b.+)$",
    _I | re.DOTALL,
)

_RUNSTATS = re.compile(
    r"\b(runstats|run\s+statistics|update\s+statistics|refresh\s+statistics|"
    r"collect\s+statistics|gather\s+statistics)\b",
    _I,
)
_CREATE_INDEX = re.compile(r"\b(create|add|build)\s+(an?\s+)?index\b", _I)
_INDEX_ON = re.compile(
    r"\bindex\s+on\s+(?:table\s+)?([A-Za-z_][\w$#@]*(?:\.[A-Za-z_][\w$#@]*)?)\s*"
    r"(?:\(\s*([A-Za-z_][\w$#@]*)\s*\)|(?:column|col)\s+([A-Za-z_][\w$#@]*))",
    _I,
)
_RUNSTATS_ON = re.compile(
    r"\b(?:on|for)\s+(?:table\s+)?([A-Za-z_][\w$#@]*(?:\.[A-Za-z_][\w$#@]*)?)", _I
)

_KEYWORDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("locks", re.compile(r"\b(locks?|locking|deadlocks?|blocked|blocking|lock\s*wait|waiting\s+on)\b", _I)),
    ("connections", re.compile(r"\b(connections?|sessions?|connected|applications?\s+connected|who\s+is\s+connected)\b", _I)),
    ("memory", re.compile(r"\b(buffer\s*pools?|bufferpools?|hit\s+ratio|cache\s+hit|memory)\b", _I)),
    ("indexes", re.compile(r"\b(unused\s+index(es)?|index\s+usage|useless\s+index|redundant\s+index|index(es)?\s+(is|are)\s+(not\s+used|unused))", _I)),
    ("statistics", re.compile(r"\b(statistics|stale|outdated\s+stats|last\s+analy[sz]ed)\b", _I)),
    (
        "schema",
        re.compile(
            r"\b(describe|columns?\s+(of|in)|schema|list\s+(all\s+)?tables|what\s+tables|"
            r"primary\s+key|foreign\s+key|constraints?|table\s+structure|which\s+indexes?)\b",
            _I,
        ),
    ),
    (
        "performance",
        re.compile(
            r"\b(slow|slowness|performance|bottleneck|cpu|full\s+(table\s+)?scans?|table\s+scans?|"
            r"taking\s+(too\s+)?long|health|diagnos\w*|tuning|tune|optimi[sz]\w*|sluggish|"
            r"timeouts?|expensive|hot\s+tables?|how\s+is\s+(my|the)\s+(db|database)|what'?s\s+wrong)\b",
            _I,
        ),
    ),
)

_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_$#@]*")


@dataclass(slots=True)
class IntentResult:
    intent: Intent
    confidence: float
    matched: list[str] = field(default_factory=list)
    entities: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "matched": list(self.matched),
            "entities": dict(self.entities),
        }


def _candidates(message: str) -> list[str]:
    """Upper-cased words that *could* be object names (resolved against the
    catalog later — never trusted as-is)."""
    seen: list[str] = []
    for word in _WORD.findall(message):
        up = word.upper()
        if len(up) >= 3 and up not in seen:
            seen.append(up)
    return seen


def _split_qualified(ref: str) -> tuple[str | None, str]:
    if "." in ref:
        schema, _, name = ref.partition(".")
        return schema.upper(), name.upper()
    return None, ref.upper()


def analyze_intent(message: str) -> IntentResult:
    """Classify a natural-language DBA message and extract entities."""
    text = " ".join(message.split())
    entities: dict[str, Any] = {"candidates": _candidates(text)}

    destructive = _DESTRUCTIVE.search(text)
    if destructive:
        entities["blocked_phrase"] = destructive.group(0).lower()
        return IntentResult("destructive", 0.95, [destructive.group(0).lower()], entities)

    explain = _EXPLAIN.search(text)
    if explain:
        entities["sql"] = explain.group(1).strip().rstrip(";")
        return IntentResult("explain", 0.95, ["explain <select>"], entities)

    if _RUNSTATS.search(text):
        action: dict[str, Any] = {"type": "runstats"}
        target = _RUNSTATS_ON.search(text)
        if target:
            schema, table = _split_qualified(target.group(1))
            action.update(table=table, schema=schema)
        entities["action"] = action
        return IntentResult("maintenance", 0.9, ["runstats"], entities)

    if _CREATE_INDEX.search(text):
        action = {"type": "create_index"}
        match = _INDEX_ON.search(text)
        if match:
            schema, table = _split_qualified(match.group(1))
            action.update(
                table=table,
                schema=schema,
                column=(match.group(2) or match.group(3)).upper(),
            )
        entities["action"] = action
        return IntentResult("maintenance", 0.9, ["create index"], entities)

    scores: list[tuple[str, int, list[str]]] = []
    for intent, rx in _KEYWORDS:
        hits = [m.group(0).lower() for m in rx.finditer(text)]
        if hits:
            scores.append((intent, len(hits), hits))
    if not scores:
        return IntentResult("unknown", 0.2, [], entities)
    # First rule with the most hits wins; _KEYWORDS order breaks ties
    # (specific intents before the broad "performance").
    best = max(scores, key=lambda s: s[1])
    for intent, count, hits in scores:
        if count == best[1]:
            best = (intent, count, hits)
            break
    return IntentResult(best[0], min(0.6 + 0.1 * best[1], 0.9), best[2], entities)
