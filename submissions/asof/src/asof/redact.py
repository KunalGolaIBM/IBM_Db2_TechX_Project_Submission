"""Remove personal data before text reaches an LLM provider or the ledger.

Masks email addresses, phone numbers, payment card numbers (Luhn-checked) and any other
13 to 19 digit number, airline booking references, and person names (asof/names.py: titles,
self-introductions, greetings and sign-offs, family terms, name fields and a list of common given
names). Policy amounts, dates and clause IDs never have those shapes, so they survive. The ledger
stores the redacted question and draft only. Name detection is rule-based and not exhaustive.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .names import find_names

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_PHONE = re.compile(r"(?<![\w$])(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?|\d{2,4}[\s.-])\d{3,4}[\s.-]?\d{3,4}\b")
_BOOKING_REF = re.compile(r"\b(?=[A-Z0-9]{6}\b)(?=[A-Z0-9]*\d)(?=[A-Z0-9]*[A-Z])[A-Z0-9]{6}\b")


@dataclass(frozen=True)
class Redaction:
    text: str
    counts: dict[str, int]


def _luhn(digits: str) -> bool:
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def redact(text: str) -> Redaction:
    counts = {"email": 0, "card": 0, "number": 0, "phone": 0, "booking_ref": 0, "name": 0}

    def sub(pattern: re.Pattern, label: str, key: str, s: str, valid=lambda m: True) -> str:
        def repl(m: re.Match) -> str:
            if not valid(m):
                return m.group(0)
            counts[key] += 1
            return label
        return pattern.sub(repl, s)

    out = sub(_EMAIL, "[EMAIL]", "email", text)
    # 13 to 19 digits: a card if the Luhn check passes, otherwise still masked (account numbers).
    out = sub(_CARD, "[CARD]", "card", out, lambda m: _luhn(re.sub(r"\D", "", m.group(0))))
    out = sub(_CARD, "[NUMBER]", "number", out)
    out = sub(_PHONE, "[PHONE]", "phone", out, lambda m: len(re.sub(r"\D", "", m.group(0))) >= 10)
    out = sub(_BOOKING_REF, "[BOOKING_REF]", "booking_ref", out)
    for start, end in reversed(find_names(out)):
        out = out[:start] + "[NAME]" + out[end:]
        counts["name"] += 1
    return Redaction(out, counts)
