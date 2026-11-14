"""Input validation for SQL that arrives from a human or from a model.

PortProof's whole job is to hand *arbitrary* SQL to Db2, so it cannot
parameterise the statement under test -- that statement *is* the input. Two
things make that safe rather than reckless, and both are enforced here:

* **Read-only.** Only a single ``SELECT`` / ``WITH`` statement is accepted. No
  DDL, no DML, no ``CALL``, no multi-statement payload. So the worst a pasted
  statement can do is read the throwaway fixture tables.
* **Single statement.** A trailing semicolon is tolerated, but anything after it
  is rejected, which is what stops ``SELECT 1; DROP TABLE ...`` in its tracks.

This is defence in depth, not the only defence: the compile oracle only ever
``PREPARE``s (it never executes), the semantic prover runs against the disposable
``PPTEST`` schema, and the runtime identity holds nothing but ``SELECT`` and
``EXECUTE``. Every value PortProof stores about a statement -- the SQL text
included -- is bound as a parameter marker, never concatenated.
"""
from __future__ import annotations

import re

#: Statement kinds that only read.
_ALLOWED_LEADERS = ("SELECT", "WITH", "VALUES")

#: Line and block comments, and single-quoted literals. Stripped before the
#: structural checks so that a semicolon or keyword *inside* a string or comment
#: cannot trip the guard, and -- more importantly -- cannot smuggle one past it.
_STRIP_RE = re.compile(
    r"--[^\n]*|/\*.*?\*/|'(?:[^']|'')*'",
    re.DOTALL,
)

_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|MERGE|TRUNCATE|DROP|ALTER|CREATE|GRANT|REVOKE|"
    r"CALL|EXECUTE|COMMIT|ROLLBACK|SET\s+CURRENT|LOCK|IMPORT|LOAD|EXPORT)\b",
    re.IGNORECASE,
)

MAX_LENGTH = 20_000


class UnsafeSql(ValueError):
    """Raised when a statement is not a single read-only query."""


def _strip_noise(sql: str) -> str:
    return _STRIP_RE.sub(" ", sql)


def check_read_only(sql: str) -> str:
    """Return the statement if it is a single read-only query, else raise."""
    text = (sql or "").strip()
    if not text:
        raise UnsafeSql("empty statement")
    if len(text) > MAX_LENGTH:
        raise UnsafeSql(f"statement is longer than {MAX_LENGTH} characters")

    bare = _strip_noise(text).strip()

    # One statement only. A single trailing ';' is fine; content after it is not.
    body, _, tail = bare.partition(";")
    if tail.strip():
        raise UnsafeSql(
            "more than one statement: PortProof proves one query at a time"
        )

    leader = re.match(r"\(*\s*([A-Za-z_]+)", body)
    if not leader or leader.group(1).upper() not in _ALLOWED_LEADERS:
        found = leader.group(1).upper() if leader else "?"
        raise UnsafeSql(
            f"only {', '.join(_ALLOWED_LEADERS)} statements are accepted, got {found}"
        )

    hit = _FORBIDDEN.search(body)
    if hit:
        # A CTE named e.g. "updates" is fine -- the word-boundary match is on
        # the keyword, and `WITH x AS (SELECT ...)` contains none of these.
        raise UnsafeSql(f"statement contains the forbidden keyword {hit.group(1).upper()}")

    return text


def is_read_only(sql: str) -> bool:
    try:
        check_read_only(sql)
    except UnsafeSql:
        return False
    return True
