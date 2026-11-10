"""Rule based Postgres to Db2 rewrites.

Each rule is a small regex rewrite with a name. Rules
run in order. Every change is recorded so a reviewer
can see exactly what was rewritten and why.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from parity.translate.result import TranslationResult
from parity.translate.schema import SchemaContext
from parity.translate.select_list import postgres_label, select_items

_CAST_TYPES = {
    "int": "INTEGER",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "smallint": "SMALLINT",
    "text": "VARCHAR(4000)",
    "varchar": "VARCHAR(255)",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
    "numeric": "DECIMAL(18, 6)",
    "decimal": "DECIMAL(18, 6)",
    "real": "REAL",
    "double precision": "DOUBLE",
}

_UNTRANSLATABLE: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("json_arrow_operator", re.compile(r"->>?")),
    ("regex_operator", re.compile(r"[^<>=!~]~\*?")),
    ("array_literal", re.compile(r"ARRAY\s*\[", re.IGNORECASE)),
    ("returning_clause", re.compile(r"\bRETURNING\b", re.IGNORECASE)),
    ("dollar_quoting", re.compile(r"\$\$")),
    ("serial_type", re.compile(r"\bSERIAL\b", re.IGNORECASE)),
)


@dataclass(frozen=True)
class Rule:
    """One rewrite rule.

    A rule either uses a pattern and a replacement, or a
    rewrite function that changes the whole statement. A
    rewrite function can also need the schema.
    """

    name: str
    pattern: re.Pattern[str] | None = None
    replace: str | Callable[[re.Match[str]], str] | None = None
    rewrite: Callable[[str, SchemaContext | None], str] | None = None


def _cast_repl(match: re.Match[str]) -> str:
    expr = match.group(1)
    raw_type = " ".join(match.group(2).strip().lower().split())
    db2_type = _CAST_TYPES.get(raw_type, raw_type.upper())
    return f"CAST({expr} AS {db2_type})"


def _alias_expressions(sql: str, schema: SchemaContext | None = None) -> str:
    """Give every unaliased select item the name Postgres gives it.

    Db2 names an unaliased expression by its text, for
    example `1` or `2`. Postgres names it by the function or
    by `?column?`. Without an alias the column names differ
    and the comparison reports a false mismatch.
    """
    items = select_items(sql)
    if not items:
        return sql
    edits: list[tuple[int, int, str]] = []
    for item in items:
        label = postgres_label(item.text)
        if label is None:
            continue
        alias = f' AS "{label}"' if not _SAFE_ALIAS.match(label) else f" AS {label}"
        end = item.end
        while end > item.start and sql[end - 1].isspace():
            end -= 1
        edits.append((end, end, alias))
    if not edits:
        return sql
    result = sql
    for start, end, text in sorted(edits, reverse=True):
        result = result[:start] + text + result[end:]
    return result


_SAFE_ALIAS = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

_SUM = re.compile(
    r"\bSUM\s*\(\s*((?:[A-Za-z_][A-Za-z0-9_]*\s*\.\s*)?)([A-Za-z_][A-Za-z0-9_]*)\s*\)",
    re.IGNORECASE,
)


def _sum_to_bigint(sql: str, schema: SchemaContext | None = None) -> str:
    """Cast an integer column to a bigint inside SUM.

    Db2 returns an INTEGER for SUM of an INTEGER and the sum
    can overflow. Postgres returns a bigint. The cast only
    fires when the column type is known and holds a whole
    number, so a decimal column keeps its value.
    """
    if schema is None:
        return sql
    from parity.ingest.models import extract_tables

    tables = extract_tables(sql)
    if not tables:
        return sql

    def replace(match: re.Match[str]) -> str:
        prefix = match.group(1).replace(" ", "")
        column = match.group(2)
        if not schema.is_integer(tables, column):
            return match.group(0)
        return f"SUM(CAST({prefix}{column} AS BIGINT))"

    return _SUM.sub(replace, sql)


def _limit_repl(match: re.Match[str]) -> str:
    limit = match.group(1)
    offset = match.group(2)
    if offset:
        return f"OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"
    return f"FETCH FIRST {limit} ROWS ONLY"


_RULES: tuple[Rule, ...] = (
    Rule(
        name="sum_to_bigint",
        rewrite=_sum_to_bigint,
    ),
    Rule(
        name="alias_expressions",
        rewrite=_alias_expressions,
    ),
    Rule(
        name="cast_double_colon",
        pattern=re.compile(
            r"(\S+?)::\s*(double\s+precision|smallint|integer|int|bigint|boolean|"
            r"numeric|decimal|varchar|text|date|timestamp|real)\b",
            re.IGNORECASE,
        ),
        replace=_cast_repl,
    ),
    Rule(
        name="ilike_to_upper_like",
        pattern=re.compile(r"(\S+)\s+ILIKE\s+(\S+)", re.IGNORECASE),
        replace=lambda m: f"UPPER({m.group(1)}) LIKE UPPER({m.group(2)})",
    ),
    Rule(
        name="limit_offset_to_fetch",
        pattern=re.compile(r"LIMIT\s+(\d+)(?:\s+OFFSET\s+(\d+))?", re.IGNORECASE),
        replace=_limit_repl,
    ),
    Rule(
        name="now_to_current_timestamp",
        pattern=re.compile(r"\bnow\s*\(\s*\)", re.IGNORECASE),
        replace="CURRENT_TIMESTAMP",
    ),
    Rule(
        name="random_to_rand",
        pattern=re.compile(r"\brandom\s*\(\s*\)", re.IGNORECASE),
        replace="RAND()",
    ),
    Rule(
        name="substring_from_to_comma",
        pattern=re.compile(
            r"SUBSTRING\s*\(\s*(.+?)\s+FROM\s+(\d+)(?:\s+FOR\s+(\d+))?\s*\)",
            re.IGNORECASE,
        ),
        replace=lambda m: (
            f"SUBSTRING({m.group(1)}, {m.group(2)}, {m.group(3)})"
            if m.group(3)
            else f"SUBSTRING({m.group(1)}, {m.group(2)})"
        ),
    ),
    Rule(
        name="offset_to_rows",
        pattern=re.compile(r"\bOFFSET\s+(\d+)(?!\s+ROWS)\b", re.IGNORECASE),
        replace=r"OFFSET \1 ROWS",
    ),
)


def list_rules() -> tuple[str, ...]:
    """Return rule names in run order."""
    return tuple(rule.name for rule in _RULES)


def find_untranslatable(sql: str) -> tuple[str, ...]:
    """Return names of patterns with no known Db2 form."""
    return tuple(name for name, pattern in _UNTRANSLATABLE if pattern.search(sql))


def translate(sql: str, schema: SchemaContext | None = None) -> TranslationResult:
    """Translate one Postgres statement to Db2 SQL.

    Rules apply in order. The result records which
    rules fired and which patterns need a human. A rule
    that needs the column types does nothing when no
    schema is given.
    """
    if not sql or not sql.strip():
        raise ValueError("empty SQL")
    result = sql.strip()
    applied: list[str] = []
    for rule in _RULES:
        if rule.rewrite is not None:
            new_text = rule.rewrite(result, schema)
        else:
            new_text, count = rule.pattern.subn(rule.replace, result)
            if not count:
                continue
        if new_text != result:
            applied.append(rule.name)
            result = new_text
    return TranslationResult(
        db2_sql=result,
        applied_rules=tuple(applied),
        untranslatable=find_untranslatable(result),
    )
