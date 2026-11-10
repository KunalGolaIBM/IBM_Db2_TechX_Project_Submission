"""Helpers for safely composing Db2 SQL with identifier names."""

import re

_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")


def quote_identifier(identifier: str) -> str:
    """Validate a Db2 identifier and return it quoted in uppercase."""
    if not _IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"Invalid Db2 identifier: {identifier!r}")
    return f'"{identifier.upper()}"'
