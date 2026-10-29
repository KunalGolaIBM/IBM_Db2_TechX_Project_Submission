"""IBM Db2 SQLGlot Dialect and Cross-Dialect Transpiler.

Translates queries from PostgreSQL, SQLite, MySQL, Snowflake, or ANSI SQL
into valid IBM Db2 LUW syntax (e.g. FETCH FIRST n ROWS ONLY, CURRENT TIMESTAMP,
SYSIBM.SYSDUMMY1, and date arithmetic).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

try:
    import sqlglot
    from sqlglot import exp
    HAS_SQLGLOT = True
except ImportError:
    sqlglot = None
    HAS_SQLGLOT = False


@dataclass
class TranspileResult:
    """Result of cross-dialect SQL transpilation to IBM Db2."""

    original_sql: str
    transpiled_sql: str
    source_dialect: str
    target_dialect: str = "db2"
    rules_applied: List[str] = field(default_factory=list)


class Db2DialectTranspiler:
    """Translates SQL expressions into IBM Db2 LUW compliant syntax."""

    def __init__(self, default_source_dialect: str = "postgres") -> None:
        self.default_source = default_source_dialect.lower()

    def transpile(self, sql: str, source_dialect: Optional[str] = None) -> TranspileResult:
        """Translates a source SQL string into IBM Db2 syntax."""
        src = (source_dialect or self.default_source).lower()
        applied: List[str] = []
        clean = sql.strip().strip(";")

        # 1. If sqlglot is installed, try sqlglot translation first
        if HAS_SQLGLOT:
            try:
                # Transpile using sqlglot's target if supported, or intermediate AST
                parsed = sqlglot.parse_one(clean, read=src)
                clean = parsed.sql(dialect="postgres")  # baseline normalization
                applied.append("sqlglot_ast_normalized")
            except Exception:
                pass

        # 2. Rule Engine Transformations for IBM Db2 LUW
        result_sql = clean

        # Rule: LIMIT n OFFSET m -> OFFSET m ROWS FETCH FIRST n ROWS ONLY
        limit_offset_pattern = re.compile(
            r"\bLIMIT\s+(\d+)\s+OFFSET\s+(\d+)\b", re.IGNORECASE
        )
        if limit_offset_pattern.search(result_sql):
            result_sql = limit_offset_pattern.sub(
                r"OFFSET \2 ROWS FETCH FIRST \1 ROWS ONLY", result_sql
            )
            applied.append("LIMIT_OFFSET_TO_DB2_FETCH_FIRST")

        # Rule: OFFSET m LIMIT n -> OFFSET m ROWS FETCH FIRST n ROWS ONLY
        offset_limit_pattern = re.compile(
            r"\bOFFSET\s+(\d+)\s+LIMIT\s+(\d+)\b", re.IGNORECASE
        )
        if offset_limit_pattern.search(result_sql):
            result_sql = offset_limit_pattern.sub(
                r"OFFSET \1 ROWS FETCH FIRST \2 ROWS ONLY", result_sql
            )
            applied.append("OFFSET_LIMIT_TO_DB2_FETCH_FIRST")

        # Rule: Standalone LIMIT n -> FETCH FIRST n ROWS ONLY
        limit_only_pattern = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)
        if limit_only_pattern.search(result_sql):
            result_sql = limit_only_pattern.sub(r"FETCH FIRST \1 ROWS ONLY", result_sql)
            applied.append("LIMIT_TO_FETCH_FIRST_ROWS_ONLY")

        # Rule: ILIKE -> LOWER(col) LIKE LOWER(val)
        ilike_pattern = re.compile(
            r"([A-Za-z0-9_\.]+)\s+ILIKE\s+('?[^'\s]+'?)", re.IGNORECASE
        )
        if ilike_pattern.search(result_sql):
            result_sql = ilike_pattern.sub(r"LOWER(\1) LIKE LOWER(\2)", result_sql)
            applied.append("ILIKE_TO_LOWER_LIKE")

        # Rule: FROM DUAL -> FROM SYSIBM.SYSDUMMY1
        if re.search(r"\bFROM\s+DUAL\b", result_sql, re.IGNORECASE):
            result_sql = re.sub(
                r"\bFROM\s+DUAL\b", "FROM SYSIBM.SYSDUMMY1", result_sql, flags=re.IGNORECASE
            )
            applied.append("DUAL_TO_SYSIBM_SYSDUMMY1")

        # Rule: NOW() / CURRENT_TIMESTAMP() -> CURRENT TIMESTAMP
        if re.search(r"\bNOW\(\)", result_sql, re.IGNORECASE):
            result_sql = re.sub(r"\bNOW\(\)", "CURRENT TIMESTAMP", result_sql, flags=re.IGNORECASE)
            applied.append("NOW_TO_CURRENT_TIMESTAMP")

        # Rule: CURRENT_DATE() -> CURRENT DATE
        if re.search(r"\bCURRENT_DATE\(\)", result_sql, re.IGNORECASE):
            result_sql = re.sub(r"\bCURRENT_DATE\(\)", "CURRENT DATE", result_sql, flags=re.IGNORECASE)
            applied.append("CURRENT_DATE_FUNC_TO_KEYWORD")

        # Rule: INTERVAL '1' DAY / INTERVAL '1 DAY' -> 1 DAYS
        interval_pattern = re.compile(
            r"INTERVAL\s+['\"](\d+)\s*([A-Za-z]+)['\"]", re.IGNORECASE
        )
        if interval_pattern.search(result_sql):
            result_sql = interval_pattern.sub(r"\1 \2S", result_sql)
            applied.append("INTERVAL_TO_DB2_DURATION")

        # Rule: Standalone TRUE / FALSE booleans (in comparisons or select)
        true_pattern = re.compile(r"\bIS\s+TRUE\b", re.IGNORECASE)
        if true_pattern.search(result_sql):
            result_sql = true_pattern.sub("= 1", result_sql)
            applied.append("IS_TRUE_TO_NUMERIC")

        false_pattern = re.compile(r"\bIS\s+FALSE\b", re.IGNORECASE)
        if false_pattern.search(result_sql):
            result_sql = false_pattern.sub("= 0", result_sql)
            applied.append("IS_FALSE_TO_NUMERIC")

        # Append terminal semicolon
        final_sql = f"{result_sql.strip()};"

        return TranspileResult(
            original_sql=sql,
            transpiled_sql=final_sql,
            source_dialect=src,
            target_dialect="db2",
            rules_applied=applied,
        )


_TRANSPILER: Optional[Db2DialectTranspiler] = None


def transpile_to_db2(sql: str, source_dialect: str = "postgres") -> str:
    """Convenience helper translating SQL directly to Db2 syntax."""
    global _TRANSPILER
    if _TRANSPILER is None:
        _TRANSPILER = Db2DialectTranspiler()
    return _TRANSPILER.transpile(sql, source_dialect).transpiled_sql

