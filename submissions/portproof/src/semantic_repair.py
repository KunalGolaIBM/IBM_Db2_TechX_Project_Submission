"""Stage 3b: repair a statement that compiles and still means something else.

The compile repair loop in :mod:`src.repair` closes a loop that Db2 itself
opens: Db2 rejected the SQL, so Db2 can say when it stops rejecting it. The
harder failure has no such signal. A statement that *compiles* and returns the
wrong rows is accepted by every tool in the chain, which is precisely why
PortProof hunts for it -- and until now PortProof hunted for it and then
stopped, reporting PROVEN DIFFERENT and leaving the engineer to it.

This module closes that loop too:

    prove meaning -> DIFFERENT -> rewrite -> compile-check -> prove meaning again

Three properties make this safe to automate, and they are the point:

1. **A candidate is never trusted.** It goes back through ``PREPARE`` and then
   through the whole differential proof. A rewrite that compiles but still
   disagrees is discarded with the same indifference as one that does not
   compile at all.
2. **The acceptance test is the one that found the bug.** The repair is accepted
   only if the counterexample that proved the statement different now agrees,
   *and* the proof is not vacuous -- a rewrite that makes both engines return
   nothing would otherwise look like a fix.
3. **The rules are engine findings, not guesses.** Each one encodes a divergence
   measured on this Db2 and this source engine, with the measurement in its
   docstring.

The rules are dialect-scoped on purpose. MySQL's ``=`` on strings is
case-insensitive and PostgreSQL's is not, so a rule that "fixes" case
sensitivity must never fire on a PostgreSQL statement -- it would introduce the
very class of bug this file exists to remove.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Sequence

from . import db
from .corpus import Variant
from .counterexample import Db2Target, SemanticVerdict, SourceEngine, prove_semantics

#: Db2's Unicode Collation Algorithm, strength 1: primary differences only, so
#: case and accents are ignored. Verified on CE 12.1.5 to reproduce MySQL's
#: default ``utf8mb4_0900_ai_ci`` equality exactly on the mixed_case fixture:
#: both return ids 1, 2 and 3 for ``name = 'asha smith'`` where plain Db2 ``=``
#: returns none.
UCA_CASE_INSENSITIVE = "UCA500R1_S1"
#: Strength 2: letter case is ignored and accents are not. That is SQL Server's
#: default (``SQL_Latin1_General_CP1_CI_AS``: case-insensitive, accent-sensitive),
#: where MySQL's default ignores both.
UCA_CASE_INSENSITIVE_ACCENT_SENSITIVE = "UCA500R1_S2"

#: The same algorithm at strength 3: case and accents *do* distinguish, but only
#: after the letter does. Verified on CE 12.1.5 to reproduce PostgreSQL's
#: default linguistic ordering: ``ORDER BY sku`` over {A1, a1, B2, b2} gives
#: ``a1, A1, b2, B2`` on PostgreSQL and on Db2 through this key, against
#: ``A1, B2, a1, b2`` from Db2's own code-point ordering.
UCA_LINGUISTIC = "UCA500R1_S3"

#: MySQL's decimal division: the result scale is the numerator's scale plus
#: ``div_precision_increment`` (4 by default), and the result is *rounded*.
#: Db2's ``/`` truncates to a much wider scale instead, so 0.01/7 is
#: 0.00142857... in Db2 against MySQL's 0.001429.
MYSQL_DIV_PRECISION_INCREMENT = 4

_STRING_EQ_RE = re.compile(
    r"(?P<lhs>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)"
    r"\s*(?P<op>=|<>|!=)\s*"
    r"(?P<rhs>'(?:''|[^'])*')"
)
_OPERAND = r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?|\d+(?:\.\d+)?"
#: The shape IBM's ``db2-sqlglot-dialect`` emits for MySQL's ``/``: it casts the
#: numerator to DOUBLE. See :func:`_mysql_decimal_division`.
_DOUBLE_DIVISION_RE = re.compile(
    rf"CAST\s*\(\s*(?P<num>{_OPERAND})\s+AS\s+(?:DOUBLE|FLOAT|REAL)\s*\)"
    rf"\s*/\s*(?P<den>NULLIF\s*\([^()]*\)|{_OPERAND})",
    re.IGNORECASE,
)
_DIVISION_RE = re.compile(rf"(?P<num>{_OPERAND})\s*/\s*(?P<den>{_OPERAND})")
#: What the compile-repair rule ``array_agg->listagg`` leaves behind.
_LISTAGG_CAST_RE = re.compile(
    r"LISTAGG\s*\(\s*CAST\s*\((?P<expr>[^()]*?)\s+AS\s+VARCHAR\s*\(\s*\d+\s*\)\s*\)\s*,\s*','\s*\)",
    re.IGNORECASE,
)


_STRING_IN_RE = re.compile(
    r"(?P<lhs>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)"
    r"\s+(?P<neg>NOT\s+)?IN\s*\(\s*(?P<items>'(?:''|[^'])*'(?:\s*,\s*'(?:''|[^'])*')*)\s*\)",
    re.IGNORECASE,
)
_STRING_ITEM_RE = re.compile(r"'(?:''|[^'])*'")
_STRING_LIKE_RE = re.compile(
    r"(?P<lhs>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)"
    r"\s+(?P<neg>NOT\s+)?LIKE\s+(?P<rhs>'(?:''|[^'])*')",
    re.IGNORECASE,
)


def _rewrite_string_comparisons(sql: str, one: Callable[[str, str, str], str]) -> str:
    """Apply ``one(lhs, '=' or '<>', literal)`` to every string comparison.

    ``x IN ('a', 'b')`` is a list of equalities and is rewritten as one, which
    is what the first version of these rules missed: it handled ``=`` and left
    ``IN`` comparing the way Db2 does.
    """

    def rewrite_in(match: re.Match[str]) -> str:
        lhs, negated = match.group("lhs"), bool(match.group("neg"))
        items = _STRING_ITEM_RE.findall(match.group("items"))
        parts = [one(lhs, "<>" if negated else "=", item) for item in items]
        return "(" + (" AND " if negated else " OR ").join(parts) + ")"

    def rewrite_eq(match: re.Match[str]) -> str:
        op = "=" if match.group("op") == "=" else "<>"
        return one(match.group("lhs"), op, match.group("rhs"))

    # Equalities first: the IN expansion writes equalities of its own, and
    # they must not be rewritten a second time.
    return _STRING_IN_RE.sub(rewrite_in, _STRING_EQ_RE.sub(rewrite_eq, sql))


def _has_string_comparison(sql: str) -> bool:
    return bool(_STRING_EQ_RE.search(sql) or _STRING_IN_RE.search(sql))


def _case_insensitive_like(sql: str) -> str:
    """LIKE the way MySQL, SQL Server and SQLite decide it: letter case ignored.

    Db2's LIKE is case-sensitive, so ``name LIKE '%SMITH%'`` misses 'Asha Smith'
    there and finds it on the other three. Folding both sides is the rewrite
    the model proposed for this on the first live run, statement by statement.
    """

    def rewrite(match: re.Match[str]) -> str:
        negated = "NOT " if match.group("neg") else ""
        return f"UPPER({match.group('lhs')}) {negated}LIKE UPPER({match.group('rhs')})"

    return _STRING_LIKE_RE.sub(rewrite, sql)


def _collate_string_equality(sql: str) -> str:
    """Make string equality case-insensitive, the way MySQL's default is.

    ``COLLATION_KEY_BIT`` is applied to *both* sides so the comparison is
    between collation keys rather than between code points. Measured: with the
    mixed_case fixture, ``name = 'asha smith'`` returns nothing on Db2 and three
    rows on MySQL; with both sides wrapped at UCA strength 1, Db2 returns the
    same three rows.

    The length comparison was added after the ``trailing_spaces`` dataset
    disproved the first version of this rule. MySQL 8's default collation is
    NO PAD, so ``'Asha Smith '`` is not equal to ``'asha smith'`` there. The
    collation keys of the two are identical on Db2, so the key comparison
    alone matched a row MySQL does not. Six datasets never noticed; the
    seventh did. Length is counted in characters (``CODEUNITS32``), because an
    accent-insensitive match of ``'José'`` and ``'Jose'`` is four characters
    against four and five bytes against four.
    """

    def one(lhs: str, op: str, rhs: str) -> str:
        key = f"COLLATION_KEY_BIT(%s, '{UCA_CASE_INSENSITIVE}')"
        size = "CHARACTER_LENGTH(%s, CODEUNITS32)"
        if op == "=":
            return f"({key % lhs} = {key % rhs} AND {size % lhs} = {size % rhs})"
        return f"({key % lhs} <> {key % rhs} OR {size % lhs} <> {size % rhs})"

    return _rewrite_string_comparisons(sql, one)


def _collate_string_equality_tsql(sql: str) -> str:
    """String equality the way SQL Server's default collation decides it.

    Two things at once, both measured: letter case is ignored, and so are
    trailing blanks ('Asha Smith ' = 'Asha Smith' is true there). Accents are
    not ignored, which is why this is strength 2 and the MySQL rule above is
    strength 1.
    """

    def one(lhs: str, op: str, rhs: str) -> str:
        key = f"COLLATION_KEY_BIT(RTRIM(%s), '{UCA_CASE_INSENSITIVE_ACCENT_SENSITIVE}')"
        return f"{key % lhs} {op} {key % rhs}"

    return _rewrite_string_comparisons(sql, one)


def _blank_sensitive_equality(sql: str) -> str:
    """String equality the way PostgreSQL and SQLite decide it: blanks count.

    Db2 compares a VARCHAR to a string by padding the shorter one with blanks,
    so ``'Asha Smith ' = 'Asha Smith'`` is true on Db2 and false on PostgreSQL
    and SQLite. Requiring the lengths to match as well removes exactly the rows
    that differ only by padding.

    This rule was written by reading what the model did. On the first live run
    it rediscovered this one rewrite for statement after statement, and each
    rediscovery was a paid call. As a rule it is free, and the model is left
    for the divergences that do not have a rule yet.
    """

    def one(lhs: str, op: str, rhs: str) -> str:
        if op == "=":
            return f"({lhs} = {rhs} AND LENGTH({lhs}) = LENGTH({rhs}))"
        return f"({lhs} <> {rhs} OR LENGTH({lhs}) <> LENGTH({rhs}))"

    return _rewrite_string_comparisons(sql, one)


def _mysql_decimal_division(sql: str) -> str:
    """Give ``/`` MySQL's exact decimal scale and rounding.

    Two things are wrong with the division that reaches Db2, and the first is
    not Db2's doing. Measured: IBM's ``db2-sqlglot-dialect`` renders MySQL's
    ``amount / quantity`` as ``CAST(amount AS DOUBLE) / NULLIF(quantity, 0)``.
    MySQL's ``/`` is **exact decimal** arithmetic; the translation is binary
    floating point. It compiles, it returns a number, and for ``0.01 / 7`` it
    returns 0.0014285714285714286 where MySQL returns 0.001429 -- a money column
    silently turned into a float, which is the oldest bug in finance software
    and one that no syntax check can see.

    The second is a genuine Db2/MySQL difference: Db2's decimal ``/`` keeps a
    very wide scale and *truncates*, while MySQL rounds to the numerator's scale
    plus ``div_precision_increment`` (4).

    So the rewrite does both: decimal, not float, and MySQL's scale with MySQL's
    rounding. ``NULLIF`` is kept, because MySQL's ``x / 0`` really is NULL.

    The numerator's declared scale is not knowable from the SQL text, so this
    uses 4 for an integer literal (MySQL's ``7 / 2`` is ``3.5000``) and 6
    otherwise -- a ``DECIMAL(n,2)`` column, by far the common case, giving
    ``2 + 4``. A wrong guess is harmless by construction: the rewrite is
    re-proved against the source engine and discarded unless every row matches.
    """

    def rewrite(match: re.Match[str]) -> str:
        num, den = match.group("num"), match.group("den")
        scale = MYSQL_DIV_PRECISION_INCREMENT if re.fullmatch(r"\d+", num) else 6
        return (
            f"CAST(ROUND(CAST({num} AS DECIMAL(31,12)) / {den}, {scale}) "
            f"AS DECIMAL(31,{scale}))"
        )

    # The translator's float idiom first; a bare `a / b` only where it is left.
    rewritten = _DOUBLE_DIVISION_RE.sub(rewrite, sql)
    if rewritten != sql:
        return rewritten
    return _DIVISION_RE.sub(rewrite, sql)


def _postgres_array_text(sql: str) -> str:
    """Render an aggregated list the way PostgreSQL renders an array.

    Db2 has no array type in a result column, so the compile-repair rule turns
    ``array_agg(id)`` into ``LISTAGG(CAST(id AS VARCHAR(200)), ',')``. That
    compiles, and it quietly changes the value: PostgreSQL's ``integer[]`` casts
    to the text ``{10,11}`` while the Db2 rewrite yields ``10,11``. A consumer
    parsing the column -- and something always parses that column -- gets a
    different answer.

    Braces are the whole fix, and they are not cosmetic: they are what makes the
    migrated column round-trip through an array parser. ``LISTAGG`` already
    returns NULL for an empty group, which matches an empty PostgreSQL array
    cast only loosely, so the proof is still what decides.
    """
    return _LISTAGG_CAST_RE.sub(
        lambda m: (
            "('{' || LISTAGG(CAST("
            + m.group("expr").strip()
            + " AS VARCHAR(200)), ',') || '}')"
        ),
        sql,
    )


_ORDER_KEY_RE = re.compile(
    r"(?P<lead>\bORDER\s+BY\s+)(?P<keys>[^()]*?)"
    r"(?=\s*(?:\)|\bOFFSET\b|\bFETCH\b|\bLIMIT\b|$))",
    re.IGNORECASE,
)
_PLAIN_KEY_RE = re.compile(
    r"^\s*(?P<expr>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)"
    r"(?P<tail>(?:\s+(?:ASC|DESC))?(?:\s+NULLS\s+(?:FIRST|LAST))?)\s*$",
    re.IGNORECASE,
)


def _linguistic_order(sql: str) -> str:
    """Sort strings the way PostgreSQL sorts them, not the way Db2 does.

    Db2 orders character data by code point, so every upper-case letter sorts
    before every lower-case one: ``A1, B2, a1, b2``. PostgreSQL's default
    collation is linguistic: ``a1, A1, b2, B2``. Both are correct and they are
    not the same, which is a migration bug with teeth, because the three places
    it surfaces all look like something else:

    * ``ORDER BY ... LIMIT n`` -- pagination silently returns different rows,
      and only for the pages where a case boundary falls inside the window;
    * ``string_agg(x ORDER BY x)`` -- the aggregated *string* differs, so a
      downstream parser sees different data, not a different sort;
    * any report whose rows a human eyeballs for order.

    ``COLLATION_KEY_BIT(k, 'UCA500R1_S3')`` gives Db2 PostgreSQL's ordering.
    Keys are wrapped only where they are a bare column reference, with ASC /
    DESC / NULLS kept outside the call where they still apply; a numeric key
    wrapped this way will not compile, and the loop discards it like any other
    failed candidate.
    """

    def wrap_keys(match: re.Match[str]) -> str:
        rewritten = []
        for key in match.group("keys").split(","):
            plain = _PLAIN_KEY_RE.match(key)
            if not plain:
                rewritten.append(key.strip())
                continue
            expr, tail = plain.group("expr"), plain.group("tail")
            rewritten.append(
                f"COLLATION_KEY_BIT({expr}, '{UCA_LINGUISTIC}'){tail}"
            )
        return match.group("lead") + ", ".join(rewritten)

    return _ORDER_KEY_RE.sub(wrap_keys, sql)


_STRFTIME_IN_FORMAT_RE = re.compile(
    r"(VARCHAR_FORMAT|TO_CHAR|TIMESTAMP_FORMAT)\s*\(([^()]*?)'(?P<fmt>[^']*%[A-Za-z][^']*)'\s*\)",
    re.IGNORECASE,
)
#: strftime pattern -> Db2 format model. Db2's VARCHAR_FORMAT takes a format
#: *model* ('YYYY-MM'), not strftime escapes.
_STRFTIME_TO_DB2 = (
    ("%Y", "YYYY"), ("%m", "MM"), ("%d", "DD"),
    ("%H", "HH24"), ("%M", "MI"), ("%S", "SS"),
)


def _db2_format_model(sql: str) -> str:
    """Translate a strftime format string into Db2's format model.

    This one is worth reading twice, because it is the failure mode PortProof
    exists to make visible and it got past PortProof's own compile oracle.

    Measured: ``to_char(created_at, 'YYYY-MM')`` is translated to
    ``VARCHAR_FORMAT(created_at, '%Y-%m')`` -- the format string is converted
    the *wrong way*, from Db2's model into strftime. ``PREPARE`` accepts it,
    because the format is a string literal and its contents are not validated
    at compile time. It fails only when a row is fetched. So a compile oracle
    alone passes it, and the statement reaches production and then breaks on
    the first execution.

    The differential proof catches it because the proof *runs* the statement.
    """

    def rewrite(match: re.Match[str]) -> str:
        fmt = match.group("fmt")
        for src, dst in _STRFTIME_TO_DB2:
            fmt = fmt.replace(src, dst)
        head = match.group(0)[: match.start("fmt") - match.start(0) - 1]
        return f"{head}'{fmt}')"

    return _STRFTIME_IN_FORMAT_RE.sub(rewrite, sql)


@dataclass(frozen=True)
class SemanticRule:
    """One measured divergence, and the rewrite that closes it."""

    name: str
    #: The source dialect this rule is about. It fires for no other.
    dialect: str
    #: What the rule is for, in the report and the UI.
    because: str
    #: True if the *source* statement shows the construct the rule addresses.
    detect: Callable[[str], bool]
    rewrite: Callable[[str], str]


_BLANKS_COUNT = (
    "{engine} treats trailing blanks as part of a string; Db2 pads the shorter "
    "side before comparing a VARCHAR, so 'x ' = 'x' is true there"
)

SEMANTIC_RULES: list[SemanticRule] = [
    SemanticRule(
        name="postgres-blank-sensitive-equality",
        dialect="postgres",
        because=_BLANKS_COUNT.format(engine="PostgreSQL"),
        detect=_has_string_comparison,
        rewrite=_blank_sensitive_equality,
    ),
    SemanticRule(
        name="sqlite-blank-sensitive-equality",
        dialect="sqlite",
        because=_BLANKS_COUNT.format(engine="SQLite"),
        detect=_has_string_comparison,
        rewrite=_blank_sensitive_equality,
    ),
    SemanticRule(
        name="sqlserver-case-insensitive-collation",
        dialect="tsql",
        because=(
            "SQL Server's default collation makes string equality ignore "
            "letter case and trailing blanks; Db2's ignores neither"
        ),
        detect=_has_string_comparison,
        rewrite=_collate_string_equality_tsql,
    ),
    SemanticRule(
        name="mysql-case-insensitive-collation",
        dialect="mysql",
        because=(
            "MySQL's default collation (utf8mb4_0900_ai_ci) makes string "
            "equality case-insensitive; Db2's is case-sensitive"
        ),
        detect=_has_string_comparison,
        rewrite=_collate_string_equality,
    ),
    *[
        SemanticRule(
            name=f"{label}-case-insensitive-like",
            dialect=dialect,
            because=f"{engine}'s LIKE ignores letter case; Db2's does not",
            detect=lambda sql: bool(_STRING_LIKE_RE.search(sql)),
            rewrite=_case_insensitive_like,
        )
        for label, dialect, engine in (
            ("mysql", "mysql", "MySQL"),
            ("sqlserver", "tsql", "SQL Server"),
            ("sqlite", "sqlite", "SQLite"),
        )
    ],
    SemanticRule(
        name="mysql-decimal-division",
        dialect="mysql",
        because=(
            "MySQL's '/' is exact decimal division rounded to the numerator's "
            "scale + 4; the translator emits binary floating point and Db2's "
            "own decimal '/' truncates at a wider scale"
        ),
        detect=lambda sql: bool(_DIVISION_RE.search(sql)),
        rewrite=_mysql_decimal_division,
    ),
    SemanticRule(
        name="postgres-array-text-form",
        dialect="postgres",
        because=(
            "PostgreSQL's array_agg produces an array whose text form is "
            "'{10,11}'; the Db2 rewrite via LISTAGG produces '10,11'"
        ),
        detect=lambda sql: bool(re.search(r"\barray_agg\b", sql, re.IGNORECASE)),
        rewrite=_postgres_array_text,
    ),
    SemanticRule(
        name="postgres-linguistic-collation-order",
        dialect="postgres",
        because=(
            "PostgreSQL's default collation orders strings linguistically "
            "(a1 < A1 < b2); Db2 orders them by code point (A1 < B2 < a1), so "
            "ORDER BY, LIMIT windows and string_agg all come out differently"
        ),
        detect=lambda sql: bool(re.search(r"\bORDER\s+BY\b", sql, re.IGNORECASE)),
        rewrite=_linguistic_order,
    ),
    # Not dialect-specific in nature, but the translator only produces it from
    # PostgreSQL's to_char; registered for both so neither is missed.
    *[
        SemanticRule(
            name="strftime->db2-format-model",
            dialect=dialect,
            because=(
                "the translator renders the date format the wrong way round, "
                "producing strftime escapes ('%Y-%m') where Db2 wants a format "
                "model ('YYYY-MM'); PREPARE accepts it and the fetch fails"
            ),
            detect=lambda sql: bool(
                re.search(r"\b(?:to_char|date_format)\b", sql, re.IGNORECASE)
            ),
            rewrite=_db2_format_model,
        )
        for dialect in ("postgres", "mysql", "tsql", "sqlite")
    ],
]

#: The name the memory tier's replayed rewrite is recorded under.
MEMORY_RULE = "memory:verified-rewrite"

SEMANTIC_PROMPT = """A {dialect} query was translated to IBM Db2. The Db2 version compiles, and it returns different rows.

Original {dialect} query:
{source_sql}

Current Db2 query:
{db2_sql}

Counterexample, on a dataset built to test this: {targets}
{dialect} returned (first rows): {source_rows}
Db2 returned (first rows): {db2_rows}
{db2_error}{history}
Rewrite the Db2 query so that it returns exactly what {dialect} returns, on any data.
Keep the same column names. Reason from how {dialect} behaves by default (collation,
blank padding, NULL ordering, integer and decimal division, string functions that
count characters where Db2 counts bytes unless told CODEUNITS32).

Reply with the corrected Db2 SQL statement only."""

SEMANTIC_SYSTEM = (
    "You repair SQL that was migrated to IBM Db2 and changed meaning. "
    "Reply with one Db2 SELECT statement only: no prose, no markdown fences."
)


@dataclass
class SemanticAttempt:
    n: int
    rule: str
    sql: str
    compiled: bool
    outcome: str = ""
    strength: str = "NONE"
    sqlcode: int | None = None
    message: str = ""

    @property
    def accepted(self) -> bool:
        return self.compiled and self.outcome == "EQUIVALENT"


@dataclass
class SemanticRepairOutcome:
    repaired: bool
    final_sql: str
    verdict: SemanticVerdict | None = None
    rule: str = ""
    because: str = ""
    attempts: list[SemanticAttempt] = field(default_factory=list)
    #: True when the rewrite fixed every divergence the statement's own SQL
    #: determines, and the rows that still differ differ only because the
    #: ORDER BY has ties. Nothing can fix that, and nothing should claim to.
    partial: bool = False
    #: Who proposed the accepted rewrite: "rules" or "model".
    tier: str = ""
    #: True when the model was not asked because Db2 already records that it
    #: failed on this exact statement.
    model_skipped: bool = False

    @property
    def model_calls(self) -> int:
        return sum(1 for a in self.attempts if a.rule.startswith("model:"))

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    def summary(self) -> str:
        if self.repaired and self.partial:
            return (
                f"semantic repair accepted as far as the SQL determines: "
                f"{self.rule} ({self.because}); what still differs is row order "
                "the statement never specified -- add a tiebreaker to ORDER BY"
            )
        if self.repaired:
            return f"semantic repair accepted: {self.rule} ({self.because})"
        if not self.attempts:
            return "no semantic repair rule applies to this divergence"
        tried = ", ".join(a.rule for a in self.attempts)
        return f"semantic repair failed; Db2 rejected or disproved: {tried}"


class SemanticRepairLoop:
    """Try measured rewrites until the differential proof itself agrees."""

    def __init__(
        self,
        conn,
        *,
        source: SourceEngine,
        target: Db2Target,
        rules: Sequence[SemanticRule] | None = None,
        model=None,
        max_model_attempts: int = 2,
        case_name: str = "",
        memory=None,
        dead_ends=None,
    ) -> None:
        #: Statements the model was already asked about in full and could not
        #: repair. It is not asked again.
        self.dead_ends = dead_ends
        #: The Db2 fix memory. A rewrite that was proved for this exact
        #: statement on an earlier run is tried first, and costs nothing.
        self.memory = memory
        self.conn = conn
        self.source = source
        self.target = target
        self.rules = list(rules if rules is not None else SEMANTIC_RULES)
        #: A language model, asked only when no measured rule closes the
        #: divergence. It is shown the counterexample and nothing else.
        self.model = model
        self.max_model_attempts = max_model_attempts
        self.case_name = case_name

    def candidates(self, *, source_sql: str, db2_sql: str, dialect: str) -> list[SemanticRule]:
        """Which rules are even relevant. Dialect first, then the construct."""
        return [
            rule
            for rule in self.rules
            if rule.dialect == dialect and rule.detect(source_sql) and rule.rewrite(db2_sql) != db2_sql
        ]

    def run(
        self,
        *,
        source_sql: str,
        db2_sql: str,
        dialect: str,
        variants: Sequence[Variant] | None = None,
        before: SemanticVerdict | None = None,
    ) -> SemanticRepairOutcome:
        attempts: list[SemanticAttempt] = []
        agreed_before = before.instances_agreed if before is not None else -1
        rules = self.candidates(source_sql=source_sql, db2_sql=db2_sql, dialect=dialect)
        exact = getattr(self.memory, "exact", None)
        remembered = exact(bad_sql=db2_sql, dialect=dialect) if callable(exact) else None
        if remembered and remembered != db2_sql:
            rules = [
                SemanticRule(
                    name=MEMORY_RULE,
                    dialect=dialect,
                    because="a rewrite of this exact statement that an earlier run "
                            "proved, replayed from the Db2 fix memory and proved again",
                    detect=lambda _sql: True,
                    rewrite=lambda _sql, fixed=remembered: fixed,
                )
            ] + rules
        for n, rule in enumerate(rules, start=1):
            candidate = rule.rewrite(db2_sql)
            compiled = db.compile_check(self.conn, candidate)
            if not compiled.ok:
                attempts.append(
                    SemanticAttempt(
                        n=n,
                        rule=rule.name,
                        sql=candidate,
                        compiled=False,
                        sqlcode=compiled.sqlcode,
                        message=compiled.message[:200],
                    )
                )
                continue

            verdict = prove_semantics(
                source_sql=source_sql,
                db2_sql=candidate,
                source=self.source,
                target=self.target,
                variants=variants,
                dialect=dialect,
            )
            attempts.append(
                SemanticAttempt(
                    n=n,
                    rule=rule.name,
                    sql=candidate,
                    compiled=True,
                    outcome=verdict.outcome,
                    strength=verdict.strength,
                )
            )
            # EQUIVALENT is necessary and not sufficient: a rewrite that made
            # both engines return nothing would satisfy it. VACUOUS is already a
            # separate outcome, and strength NONE catches the rest.
            full = verdict.outcome == "EQUIVALENT" and verdict.strength != "NONE"

            # A rewrite also counts when what is left over is not a difference
            # anybody can fix. `postgres/limit_offset` is the case: the engines
            # part company on mixed-case names, which the collation rewrite
            # settles, *and* on three rows whose sort key is literally the same
            # string, which no rewrite can settle because the statement never
            # said which of them comes first. Accepting the rewrite and naming
            # the residue is more use than discarding a correct fix.
            partial = (
                not full
                and verdict.outcome == "DIFFERENT"
                and verdict.order_unstable
                and verdict.instances_agreed > agreed_before
            )
            if full or partial:
                return SemanticRepairOutcome(
                    repaired=True,
                    final_sql=candidate,
                    verdict=verdict,
                    rule=rule.name,
                    because=rule.because,
                    attempts=attempts,
                    partial=partial,
                    tier="memory" if rule.name == MEMORY_RULE else "rules",
                )

        skipped = False
        if self.model is not None and before is not None and before.witness is not None:
            name = getattr(self.model, "model", "model")
            subject = (dialect, source_sql, db2_sql)
            if self.dead_ends is not None and self.dead_ends.known("SEMANTIC_REPAIR", name, *subject):
                skipped = True
            else:
                asked = len(attempts)
                fixed = self._ask_model(
                    source_sql=source_sql, db2_sql=db2_sql, dialect=dialect,
                    variants=variants, before=before, attempts=attempts,
                )
                if fixed is not None:
                    return fixed
                # A dead end only if the model used every attempt it had and
                # each one produced SQL that was then rejected or disproved. A
                # timeout or an exhausted budget proves nothing about it.
                answered = [a for a in attempts[asked:] if a.sql]
                if self.dead_ends is not None and len(answered) >= self.max_model_attempts:
                    self.dead_ends.record(
                        "SEMANTIC_REPAIR", name, self.case_name, len(answered), *subject)

        return SemanticRepairOutcome(
            repaired=False, final_sql=db2_sql, attempts=attempts, model_skipped=skipped
        )

    def _ask_model(
        self, *, source_sql, db2_sql, dialect, variants, before, attempts
    ) -> "SemanticRepairOutcome | None":
        """The model tier. Its answer earns nothing until the proof agrees.

        The proposal takes the same road as a rule's rewrite, with one more
        gate at the start because a model can write anything: it must be a
        single read-only statement before it is allowed near a connection.
        Then Db2 compiles it, and then the differential proof that found the
        divergence is run again, over every dataset. A model that is
        confidently wrong costs one call and changes nothing.
        """
        from .repair import clean_sql
        from .safety import UnsafeSql, check_read_only

        witness, history, current = before.witness, "", db2_sql
        name = getattr(self.model, "model", "model")
        for n in range(len(attempts) + 1, len(attempts) + 1 + self.max_model_attempts):
            # The rows in a counterexample are PortProof's own synthetic data,
            # with one exception: the source-shaped dataset carries the source
            # tables' real MIN and MAX. Those never go to a model. The model is
            # told which kind of dataset disagreed and has to work from that.
            withheld = witness.strategy == "source_shaped"
            hidden = "(withheld: this dataset carries values taken from the source)"
            prompt = SEMANTIC_PROMPT.format(
                dialect=dialect, source_sql=source_sql, db2_sql=current,
                targets=witness.targets,
                source_rows=hidden if withheld else witness.source_rows[:5],
                db2_rows=hidden if withheld else witness.db2_rows[:5],
                db2_error=f"Db2 raised: {witness.db2_error}\n" if witness.db2_error else "",
                history=history,
            )
            try:
                candidate = clean_sql(
                    self.model.ask(SEMANTIC_SYSTEM, prompt, stage="SEMANTIC_REPAIR",
                                   case_name=self.case_name)
                )
                check_read_only(candidate)
            except (UnsafeSql, Exception) as exc:
                attempts.append(SemanticAttempt(
                    n=n, rule=f"model:{name}", sql="", compiled=False,
                    message=f"rejected before execution: {str(exc)[:160]}"))
                return None
            compiled = db.compile_check(self.conn, candidate)
            if not compiled.ok:
                attempts.append(SemanticAttempt(
                    n=n, rule=f"model:{name}", sql=candidate, compiled=False,
                    sqlcode=compiled.sqlcode, message=compiled.message[:200]))
                history = (
                    f"\nA previous attempt was rejected by Db2 with SQLCODE={compiled.sqlcode}: "
                    f"{compiled.message[:200]}\nThat attempt was: {candidate}\n"
                )
                continue
            verdict = prove_semantics(
                source_sql=source_sql, db2_sql=candidate, source=self.source,
                target=self.target, variants=variants, dialect=dialect,
            )
            attempts.append(SemanticAttempt(
                n=n, rule=f"model:{name}", sql=candidate, compiled=True,
                outcome=verdict.outcome, strength=verdict.strength))
            full = verdict.outcome == "EQUIVALENT" and verdict.strength != "NONE"
            partial = (
                not full and verdict.outcome == "DIFFERENT" and verdict.order_unstable
                and verdict.instances_agreed > before.instances_agreed
            )
            if full or partial:
                return SemanticRepairOutcome(
                    repaired=True, final_sql=candidate, verdict=verdict,
                    rule=f"model:{name}",
                    because=(
                        f"proposed by {name} from the counterexample, and accepted "
                        "only because the differential proof now agrees"
                    ),
                    attempts=attempts, partial=partial, tier="model",
                )
            if verdict.witness is not None:
                witness, current = verdict.witness, candidate
                history = (
                    "\nA previous rewrite compiled and still disagreed; the "
                    "counterexample above is from that rewrite.\n"
                )
        return None
