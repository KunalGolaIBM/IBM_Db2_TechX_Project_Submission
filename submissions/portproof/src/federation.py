"""Ask Db2 to read the source engines itself, and to do the comparing.

PortProof's main proof runs the source statement on PostgreSQL or MySQL, runs
the translated statement on Db2, and compares the two answers in Python. That
is sound, but it leaves one question open. When the two answers differ, the
cause could be either of two very different things:

* the **meaning** differs, which is a translation bug and the thing PortProof
  exists to catch, or
* the **data** differs, because the fixture loader put something slightly
  different into Db2 than it put into the source engine. A timestamp that lost
  its fractional seconds, a DECIMAL that arrived with a different scale, a
  string that arrived under a different collation.

Python set arithmetic cannot tell those apart, because it only ever sees the
two answers, never the two inputs side by side.

Db2 federation can. With a nickname over the source table, a single Db2
statement reads both copies of the data at once and computes the symmetric
difference, and the engine's own optimiser does the matching. If the inputs are
identical, a disagreement is about meaning. If the inputs already differ, the
disagreement was never evidence about the translation at all.

This module is entirely optional. Nothing here is required for a proof, and
every function degrades to "not available" rather than failing, so a checkout
with no federated server behaves exactly as before.

Setup lives in ``scripts/create_federation.sh``, which also records what Db2
Community Edition actually accepts; several of its options are not what the
documentation suggests.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import db
from .counterexample import FIXTURE_SCHEMA

#: Which federated server stands in for which source dialect, and the prefix
#: its nicknames carry. Both are fixed identifiers from this file, never user
#: input, which is what makes it safe to put them into statement text below.
SERVERS: dict[str, tuple[str, str]] = {
    "postgres": ("PGSRV", "PG_"),
    "mysql": ("MYSRV", "MY_"),
}

#: The schema holding the Db2 copies of the fixture tables. The same schema the
#: differential proof loads, so the two comparisons are about the same rows.
TARGET_SCHEMA = FIXTURE_SCHEMA

_IDENT_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def _safe_identifier(name: str) -> str:
    """Upper-case an identifier and refuse anything that is not one.

    Nicknames and table names reach the statement text as identifiers, because
    SQL has no parameter marker for an identifier. Everything passed here comes
    from :data:`SERVERS` or from Db2's own catalogue, so this is a guard against
    a future caller rather than against today's one, but it is cheap and it
    means no path exists where a value becomes SQL.
    """
    upper = name.strip().upper()
    if not upper or not set(upper) <= _IDENT_OK or upper[0].isdigit():
        raise ValueError(f"not a usable SQL identifier: {name!r}")
    return upper


@dataclass(frozen=True)
class FederationStatus:
    """What federation is available right now."""

    #: Dialect to the nicknames Db2 holds for it, each schema-qualified and
    #: upper-cased. They are qualified because the setup script creates them as
    #: the instance owner, so they do not sit in the application's own schema.
    nicknames: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Why federation is unavailable, when it is. Empty when all is well.
    note: str = ""

    @property
    def available(self) -> bool:
        return any(self.nicknames.values())

    def dialects(self) -> tuple[str, ...]:
        return tuple(sorted(d for d, n in self.nicknames.items() if n))

    def headline(self) -> str:
        if not self.available:
            return self.note or "federation is not configured"
        parts = [f"{d}: {len(self.nicknames[d])} nicknames" for d in self.dialects()]
        return "Db2 reads the source directly (" + ", ".join(parts) + ")"


def status(conn) -> FederationStatus:
    """Read SYSCAT.NICKNAMES and work out which dialects Db2 can reach.

    A nickname existing is not quite a promise that the remote is reachable, so
    callers that care should follow up with :func:`compare_inputs`, which finds
    out by asking.
    """
    try:
        rows = db.fetch_all(
            conn,
            "SELECT TABSCHEMA, TABNAME, SERVERNAME FROM SYSCAT.NICKNAMES "
            "WHERE SERVERNAME IN (?, ?)",
            [SERVERS["postgres"][0], SERVERS["mysql"][0]],
        )
    except db.Db2Error as exc:
        return FederationStatus(note=f"could not read SYSCAT.NICKNAMES: {exc.message}")

    found: dict[str, list[str]] = {d: [] for d in SERVERS}
    by_server = {server: dialect for dialect, (server, _) in SERVERS.items()}
    for tabschema, tabname, servername in rows:
        dialect = by_server.get(str(servername).strip())
        if dialect:
            found[dialect].append(f"{str(tabschema).strip()}.{str(tabname).strip()}")

    note = ""
    if not any(found.values()):
        note = "no federated nicknames; run scripts/create_federation.sh to add them"
    return FederationStatus(
        nicknames={d: tuple(sorted(v)) for d, v in found.items()},
        note=note,
    )


@dataclass(frozen=True)
class InputComparison:
    """Db2's own verdict on whether two copies of one table hold the same rows."""

    table: str
    dialect: str
    nickname: str
    #: Rows the source engine has and Db2 does not.
    only_in_source: int = 0
    #: Rows Db2 has and the source engine does not.
    only_in_db2: int = 0
    #: How many columns the comparison actually read.
    columns_compared: int = 0
    #: Columns left out because Db2 would not cast the remote type to the local
    #: one. Naming them matters: a skipped column is a gap in the check, and a
    #: check with a silent gap is worse than no check.
    columns_skipped: tuple[str, ...] = ()
    #: Set when the comparison could not be made, with the engine's reason.
    error: str = ""

    @property
    def attempted(self) -> bool:
        return not self.error

    @property
    def identical(self) -> bool:
        return self.attempted and self.only_in_source == 0 and self.only_in_db2 == 0

    def describe(self) -> str:
        if self.error:
            return f"{self.table}: not compared ({self.error})"
        if self.identical:
            body = f"{self.table}: both engines hold the same rows"
        else:
            body = (
                f"{self.table}: inputs differ, {self.only_in_source} only in "
                f"{self.dialect} and {self.only_in_db2} only in Db2"
            )
        body += f", across {self.columns_compared} columns"
        if self.columns_skipped:
            body += " (not " + ", ".join(self.columns_skipped) + ": Db2 will not cast those)"
        return body


#: Db2 type names that take a single length, and the ones that take none.
_SIZED = {"VARCHAR", "CHARACTER", "CHAR", "CLOB", "VARGRAPHIC", "GRAPHIC", "VARBINARY", "BINARY"}
_UNSIZED = {
    "INTEGER", "SMALLINT", "BIGINT", "REAL", "DOUBLE", "FLOAT", "DATE", "BOOLEAN", "XML",
}


def _db2_type(typename: str, length: int, scale: int) -> str:
    """Spell a SYSCAT.COLUMNS row back as a type the CAST syntax accepts."""
    name = typename.strip().upper()
    if name in _UNSIZED:
        return name
    if name in _SIZED:
        return f"{name}({max(int(length), 1)})"
    if name in ("DECIMAL", "NUMERIC", "DECFLOAT"):
        return f"DECIMAL({max(int(length), 1)},{int(scale)})"
    if name in ("TIMESTAMP", "TIME"):
        return name
    # Anything else is left alone and compared as the engine presents it.
    return name


def _columns_of(conn, schema: str, table: str) -> list[tuple[str, str]]:
    """``(name, cast target)`` for every column, in the table's own order."""
    rows = db.fetch_all(
        conn,
        "SELECT COLNAME, TYPENAME, LENGTH, SCALE FROM SYSCAT.COLUMNS "
        "WHERE TABSCHEMA = ? AND TABNAME = ? ORDER BY COLNO",
        [schema, table],
    )
    return [
        (str(r[0]).strip(), _db2_type(str(r[1]), int(r[2] or 0), int(r[3] or 0)))
        for r in rows
    ]


def _shared_columns(conn, nickname: tuple[str, str], table: str) -> tuple[tuple[str, str], ...]:
    """Columns present in both the nickname and the Db2 copy, in Db2's order.

    Nicknames keep the remote's own spelling, so a PostgreSQL ``orders`` arrives
    with lower-case column names that have to be quoted, while the Db2 copy has
    them folded to upper case. Pairing them by upper-cased name is what lets one
    statement read both.

    The type that comes back is the *Db2 copy's* type, which the remote column
    is then cast to. That is deliberate. Db2 gives a nickname column whatever
    type its own mapping produces, and that is often not the type PortProof
    created locally: a MySQL ``TEXT`` arrives as CLOB next to a local VARCHAR,
    and ``EXCEPT ALL`` then refuses the whole statement with SQL0415N, "the data
    types of corresponding columns are not compatible". Casting the remote side
    to the local type makes the comparison ask a well-posed question, which is
    whether the source row, read the way Db2 would read it, is the Db2 row.
    """
    remote = {name.upper(): name for name, _ in _columns_of(conn, nickname[0], nickname[1])}
    local = _columns_of(conn, TARGET_SCHEMA, table)
    return tuple((name, cast) for name, cast in local if name.upper() in remote)


def _split_nickname(qualified: str) -> tuple[str, str]:
    schema, _, name = qualified.partition(".")
    return _safe_identifier(schema), _safe_identifier(name)


def _castable(conn, nick: tuple[str, str], name: str, cast: str) -> bool:
    """Will Db2 cast this one remote column to the local type?

    Asked with ``WHERE 1 = 0``, so the engine compiles the cast and fetches
    nothing. Not every pair is reconcilable: a MySQL ``BOOLEAN`` comes back
    through the nickname as BINARY, and Db2 answers SQL0461N, "a value with data
    type SYSIBM.BINARY cannot be CAST to type SYSIBM.BOOLEAN".
    """
    sql = (
        f'SELECT CAST("{name.lower()}" AS {cast}) FROM {nick[0]}.{nick[1]} WHERE 1 = 0'
    )
    try:
        db.fetch_all(conn, sql)
        return True
    except db.Db2Error:
        return False


def compare_inputs(conn, table: str, dialect: str, nickname: str) -> InputComparison:
    """Ask Db2, in one statement, whether both copies of ``table`` agree.

    The statement is a symmetric difference: ``EXCEPT ALL`` in each direction,
    counted. ``EXCEPT ALL`` rather than ``EXCEPT`` on purpose, so a duplicated
    row on one side is a difference and not something set semantics hides.
    """
    if dialect not in SERVERS:
        return InputComparison(table, dialect, "", error=f"no federated server for {dialect}")
    try:
        nick = _split_nickname(nickname)
        target = _safe_identifier(table)
    except ValueError as exc:
        return InputComparison(table, dialect, nickname, error=str(exc))

    try:
        shared = _shared_columns(conn, nick, target)
    except db.Db2Error as exc:
        return InputComparison(table, dialect, nickname, error=exc.message)
    if not shared:
        return InputComparison(
            table, dialect, nickname, error="no columns in common with the Db2 copy"
        )

    usable: list[tuple[str, str]] = []
    skipped_names: list[str] = []
    for name, cast in shared:
        if _castable(conn, nick, name, cast):
            usable.append((name, cast))
        else:
            skipped_names.append(name)
    skipped = tuple(skipped_names)
    if not usable:
        return InputComparison(
            table,
            dialect,
            nickname,
            columns_skipped=tuple(n for n, _ in shared),
            error="Db2 would not cast any remote column to the local type",
        )

    remote_cols = ", ".join(
        f'CAST("{name.lower()}" AS {cast}) AS {name}' for name, cast in usable
    )
    local_cols = ", ".join(name for name, _ in usable)
    sql = (
        f"WITH SRC AS (SELECT {remote_cols} FROM {nick[0]}.{nick[1]}), "
        f"TGT AS (SELECT {local_cols} FROM {TARGET_SCHEMA}.{target}), "
        "ONLY_SRC AS (SELECT * FROM SRC EXCEPT ALL SELECT * FROM TGT), "
        "ONLY_TGT AS (SELECT * FROM TGT EXCEPT ALL SELECT * FROM SRC) "
        "SELECT (SELECT COUNT(*) FROM ONLY_SRC), (SELECT COUNT(*) FROM ONLY_TGT) "
        "FROM SYSIBM.SYSDUMMY1"
    )
    try:
        row = db.fetch_one(conn, sql)
    except db.Db2Error as exc:
        return InputComparison(
            table, dialect, nickname, columns_skipped=skipped, error=exc.message
        )
    if row is None:
        return InputComparison(table, dialect, nickname, error="the engine returned no row")
    return InputComparison(
        table,
        dialect,
        nickname,
        only_in_source=int(row[0]),
        only_in_db2=int(row[1]),
        columns_compared=len(usable),
        columns_skipped=skipped,
    )


@dataclass(frozen=True)
class Corroboration:
    """Why a disagreement happened, as far as federation can tell.

    ``verdict`` is one of:

    ``UNAVAILABLE``
        No federated nickname for this dialect, so nothing was learned. This is
        the normal case on a checkout that never ran the setup script, and it
        says nothing either way about the translation.
    ``INPUTS_MATCH``
        Db2 read both copies of every table the statement touches and found
        them identical. A semantic disagreement is therefore about the query,
        not about the data.
    ``INPUTS_DIFFER``
        The two copies of at least one table are not the same rows. Any
        disagreement about the answer has to be discounted until that is fixed.
    """

    verdict: str
    comparisons: tuple[InputComparison, ...] = ()
    note: str = ""

    @property
    def strengthens_proof(self) -> bool:
        return self.verdict == "INPUTS_MATCH"

    @property
    def undermines_proof(self) -> bool:
        return self.verdict == "INPUTS_DIFFER"

    def headline(self) -> str:
        if self.verdict == "UNAVAILABLE":
            return self.note or "federation was not available"
        if self.verdict == "INPUTS_MATCH":
            names = ", ".join(c.table for c in self.comparisons)
            return f"Db2 confirmed both engines hold identical rows in {names}"
        differing = [c for c in self.comparisons if not c.identical and c.attempted]
        return "Db2 found the two engines do not hold the same rows: " + "; ".join(
            c.describe() for c in differing
        )

    def evidence(self) -> str:
        lines = [self.headline()]
        lines.extend("  " + c.describe() for c in self.comparisons)
        return "\n".join(lines)


def corroborate(conn, tables, dialect: str) -> Corroboration:
    """Compare every named table's two copies and summarise what Db2 saw."""
    state = status(conn)
    held = state.nicknames.get(dialect, ())
    if not held:
        return Corroboration("UNAVAILABLE", note=state.note or f"no nicknames for {dialect}")

    _, prefix = SERVERS[dialect]
    by_table = {n.partition(".")[2].upper(): n for n in held}
    wanted = [(t, by_table[(prefix + t).upper()]) for t in tables
              if (prefix + t).upper() in by_table]
    if not wanted:
        return Corroboration(
            "UNAVAILABLE",
            note=f"federation is configured for {dialect} but not for these tables",
        )

    comparisons = tuple(compare_inputs(conn, t, dialect, n) for t, n in wanted)

    # A table that actually differs settles it, whatever happened to the rest.
    if any(c.attempted and not c.identical for c in comparisons):
        return Corroboration("INPUTS_DIFFER", comparisons)

    # Otherwise every comparison has to have succeeded before this counts as
    # confirmation. Folding an errored table in with the matching ones would
    # turn "four of five tables agree and the fifth was never read" into a
    # clean pass, which is the kind of quiet gap this module exists to close.
    failed = [c for c in comparisons if not c.attempted]
    if failed:
        return Corroboration(
            "UNAVAILABLE",
            comparisons,
            note="not compared: " + ", ".join(f"{c.table} ({c.error})" for c in failed),
        )
    return Corroboration("INPUTS_MATCH", comparisons)


def report(conn) -> str:
    """A short human-readable federation report, for ``python -m src.main``."""
    state = status(conn)
    lines = ["Federation", "", "  " + state.headline()]
    if not state.available:
        lines.append("")
        lines.append("  PortProof proves equivalence without this. What it adds is Db2's")
        lines.append("  own opinion on whether a disagreement is about meaning or about")
        lines.append("  the data, which is the difference between a translation bug and a")
        lines.append("  loading bug.")
        return "\n".join(lines)

    from .corpus import FIXTURE_TABLES

    for dialect in state.dialects():
        lines.append("")
        lines.append(f"  {dialect}")
        result = corroborate(conn, FIXTURE_TABLES, dialect)
        for line in result.evidence().splitlines():
            lines.append("    " + line)

    lines.append("")
    lines.append("  Read this one dialect at a time. Each proof run reloads the fixture")
    lines.append("  tables in both the source engine and Db2, so only the dialect that")
    lines.append("  ran most recently is expected to match here. A mismatch on the other")
    lines.append("  one means its data is stale, not that anything is wrong.")
    return "\n".join(lines)
