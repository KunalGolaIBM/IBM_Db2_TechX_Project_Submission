"""Stage 1: translate source SQL to Db2 with IBM's sqlglot dialect.

Importing :mod:`db2_sqlglot` registers the ``db2`` dialect that IBM ships as
``db2-sqlglot-dialect``. PortProof deliberately uses IBM's own translator as the
first pass, because the point of the project is to *verify* it rather than
replace it.
"""
from __future__ import annotations

from dataclasses import dataclass

import sqlglot

try:  # pragma: no cover - import side effect registers the dialect
    import db2_sqlglot  # noqa: F401

    DIALECT_AVAILABLE = True
except Exception:  # pragma: no cover
    DIALECT_AVAILABLE = False


@dataclass(frozen=True)
class Translation:
    """What the translator produced, and whether it admitted to a problem."""

    ok: bool
    db2_sql: str | None
    error: str | None = None
    raised: bool = False

    @property
    def silent(self) -> bool:
        """True when the translator returned SQL without reporting anything.

        The measured failure mode is exactly this: output produced, no error
        raised, and the result still rejected by Db2.
        """
        return self.ok and not self.raised


def translate(sql: str, source_dialect: str) -> Translation:
    """Translate one statement to the Db2 dialect.

    ``unsupported_level=RAISE`` asks sqlglot to be as loud as it can be, so any
    silent failure that follows is the dialect's, not a suppressed warning.
    """
    if not DIALECT_AVAILABLE:
        return Translation(
            ok=False,
            db2_sql=None,
            error="db2-sqlglot-dialect is not installed (pip install db2-sqlglot-dialect)",
            raised=True,
        )
    try:
        out = sqlglot.transpile(
            sql,
            read=source_dialect,
            write="db2",
            unsupported_level=sqlglot.ErrorLevel.RAISE,
        )
    except Exception as exc:
        return Translation(
            ok=False, db2_sql=None, error=f"{type(exc).__name__}: {exc}", raised=True
        )
    if not out or not out[0].strip():
        return Translation(ok=False, db2_sql=None, error="translator produced no SQL", raised=True)
    return Translation(ok=True, db2_sql=out[0].strip())


def normalise(sql: str) -> str:
    """Collapse whitespace so two spellings of the same SQL compare equal."""
    return " ".join(sql.split())
