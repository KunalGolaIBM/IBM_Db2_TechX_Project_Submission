"""Detection of nondeterministic SQL calls.

Queries that use random or time dependent functions cannot
be compared safely unless the value is pinned. This module
finds those calls so the caller can pin them or mark the
query as NOT_COMPARABLE.
"""

from __future__ import annotations

import re

_PATTERNS: dict[str, re.Pattern[str]] = {
    "now": re.compile(r"\bnow\s*\(", re.IGNORECASE),
    "random": re.compile(r"\brandom\s*\(", re.IGNORECASE),
    "current_timestamp": re.compile(r"\bcurrent_timestamp\b", re.IGNORECASE),
    "current_date": re.compile(r"\bcurrent_date\b", re.IGNORECASE),
    "uuid": re.compile(r"\b(uuid|gen_random_uuid)\s*\(", re.IGNORECASE),
    "clock_timestamp": re.compile(r"\bclock_timestamp\s*\(", re.IGNORECASE),
}


def find_nondeterministic_calls(sql: str) -> tuple[str, ...]:
    """Return sorted names of nondeterministic calls found in SQL."""
    found = tuple(
        name for name, pattern in sorted(_PATTERNS.items()) if pattern.search(sql)
    )
    return found


def is_nondeterministic(sql: str) -> bool:
    """True when the SQL uses a nondeterministic call."""
    return bool(find_nondeterministic_calls(sql))
