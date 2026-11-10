"""Knowledge base loading and SQLCODE parsing (no database needed)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

DATA_FILE = Path(__file__).parent / "data" / "sqlcodes.json"
MAX_INPUT_CHARS = 2000

# Matches "SQL0204N", "SQL30082N", "SQLCODE=-204", "SQLCODE: -204".
_MESSAGE_ID = re.compile(r"\bSQL(\d{4,5})[NWC]?\b", re.IGNORECASE)
_SQLCODE = re.compile(r"\bSQLCODE\s*[=:]\s*(-?\d{1,5})\b", re.IGNORECASE)


class InputError(ValueError):
    """Raised when the user's error text is unusable."""


def load_entries(path: Path = DATA_FILE) -> list[dict[str, Any]]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    required = {"sqlcode", "title", "cause", "fix"}
    seen: set[str] = set()
    for entry in entries:
        missing = required - entry.keys()
        if missing:
            raise ValueError(f"Knowledge base entry is missing {sorted(missing)}: {entry}")
        if entry["sqlcode"] in seen:
            raise ValueError(f"Duplicate SQLCODE in knowledge base: {entry['sqlcode']}")
        seen.add(entry["sqlcode"])
    return entries


def entry_text(entry: dict[str, Any]) -> str:
    """The text that gets embedded for vector search."""
    return (
        f"SQLCODE {entry['sqlcode']} SQLSTATE {entry.get('sqlstate') or 'n/a'}. "
        f"{entry['title']}. Cause: {entry['cause']} Fix: {entry['fix']}"
    )


def clean_input(text: str) -> str:
    """Validate and normalise the error text a user pasted."""
    if not isinstance(text, str):
        raise InputError("Error text must be a string.")
    text = "".join(ch for ch in text if ch.isprintable() or ch in "\n\t").strip()
    if len(text) < 3:
        raise InputError("Paste the Db2 error message (at least 3 characters).")
    if len(text) > MAX_INPUT_CHARS:
        raise InputError(f"Error text is too long (limit {MAX_INPUT_CHARS} characters).")
    return text


def parse_sqlcode(text: str) -> str | None:
    """Return a canonical code such as '-204' if the text names one."""
    match = _SQLCODE.search(text)
    if match:
        return str(int(match.group(1)))
    match = _MESSAGE_ID.search(text)
    if match:
        return f"-{int(match.group(1))}"
    return None
