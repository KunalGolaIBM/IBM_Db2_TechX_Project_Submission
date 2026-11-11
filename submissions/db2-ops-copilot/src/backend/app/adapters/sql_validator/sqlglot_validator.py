"""AST-based SQL validation gate (sqlglot + official IBM ``db2`` dialect).

Layered validation — each layer is independent, and NONE of them alone is the
security boundary (see ``app/security/sql_policy.py`` for the full rationale):

1. **Input hygiene**   — length cap, control characters, empty input.
2. **Parse gate**      — sqlglot parse with the Db2 dialect; unparsable → reject
                         (fail-closed). Requires exactly ONE statement.
3. **Statement allow-list** — root node must be ``SELECT`` (blocks DDL/DML/
                         stacked statements by construction).
4. **Forbidden nodes** — ``SELECT INTO``, ``FOR UPDATE`` locks, and any DML/DDL
                         nodes anywhere in the tree.
5. **Catalog deny-list** — SYSCAT/SYSIBM/... schema references rejected.
6. **Function deny-list** — dynamic-SQL style functions rejected.
7. **Complexity limits** — AST size, joins, subqueries, IN-list length.
8. **Row-limit advisory** — warns when no FETCH FIRST/LIMIT is present; the
                         executor (M2) appends a hard row cap + timeout anyway.

Defense in depth continues outside this gate: read-only Db2 account, row/timeout
caps at execution, parameterized app queries, prompt-injection screening and
audit logging.
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.schemas.sql import AppliedPolicy, SqlValidateResponse, Violation
from app.security.sql_policy import SqlPolicy

logger = logging.getLogger(__name__)

_ROW_LIMIT_RE = re.compile(
    r"\b(FETCH\s+FIRST|LIMIT|ROWNUM|TOP)\b", re.IGNORECASE
)

# Node types that must never appear inside an accepted statement.
_FORBIDDEN_NODE_TYPES: tuple[type[exp.Expression], ...] = tuple(
    node
    for node in (
        getattr(exp, name, None)
        for name in (
            "Insert",
            "Update",
            "Delete",
            "Merge",
            "Create",
            "Drop",
            "Alter",
            "TruncateTable",
            "Grant",
            "Revoke",
            "Command",
            "Transaction",
            "Commit",
            "Rollback",
            "Into",
            "Lock",
        )
    )
    if node is not None
)


@lru_cache(maxsize=1)
def resolve_dialect() -> tuple[str, str]:
    """Resolve the sqlglot dialect, preferring the official IBM Db2 plugin.

    Returns ``(dialect_key, source_description)``. The plugin registers the
    ``db2`` dialect as a sqlglot entry point (``db2_sqlglot`` import).
    """
    try:
        import db2_sqlglot  # noqa: F401  — registers the "db2" dialect

        if "db2" in sqlglot.Dialect.classes:
            logger.info("SQL dialect: db2 (db2-sqlglot-dialect plugin)")
            return "db2", "db2-sqlglot-dialect"
    except ImportError:
        logger.warning(
            "db2-sqlglot-dialect not installed — falling back to the generic "
            "sqlglot dialect (validation stays fail-closed)."
        )
    if "db2" in sqlglot.Dialect.classes:
        return "db2", "sqlglot"
    return "", "sqlglot-generic"


class SqlGlotValidator:
    """Deterministic, offline SQL validator implementing :class:`SqlValidator`."""

    def __init__(self, policy: SqlPolicy | None = None) -> None:
        self.policy = policy or SqlPolicy()
        self._dialect, self._dialect_source = resolve_dialect()

    # ------------------------------------------------------------------
    def validate(self, sql: str) -> SqlValidateResponse:
        violations: list[Violation] = []
        warnings: list[Violation] = []
        statement_type: str | None = None
        normalized_sql: str | None = None

        def deny(code: str, message: str) -> None:
            violations.append(Violation(code=code, message=message, severity="error"))

        def warn(code: str, message: str) -> None:
            warnings.append(Violation(code=code, message=message, severity="warning"))

        # Layer 1 — input hygiene --------------------------------------
        if not sql or not sql.strip():
            deny("empty_statement", "SQL input is empty.")
            return self._result(violations, warnings, statement_type, normalized_sql)
        if "\x00" in sql:
            deny("null_byte", "SQL contains a NUL byte.")
            return self._result(violations, warnings, statement_type, normalized_sql)
        if len(sql) > self.policy.max_sql_length:
            deny(
                "max_length_exceeded",
                f"SQL exceeds the maximum length of {self.policy.max_sql_length} characters.",
            )
            return self._result(violations, warnings, statement_type, normalized_sql)
        if any(ord(ch) < 32 and ch not in "\t\n\r" for ch in sql):
            deny("control_characters", "SQL contains control characters.")
            return self._result(violations, warnings, statement_type, normalized_sql)

        # Layer 2 — parse gate (fail-closed) ---------------------------
        try:
            parsed = [
                node
                for node in sqlglot.parse(sql, dialect=self._dialect)
                if node is not None
            ]
        except SqlglotError as exc:
            deny(
                "parse_error",
                f"SQL could not be parsed as Db2 SQL ({type(exc).__name__}).",
            )
            return self._result(violations, warnings, statement_type, normalized_sql)

        if not parsed:
            deny("empty_statement", "SQL contains no statement.")
            return self._result(violations, warnings, statement_type, normalized_sql)

        # Layer 3 — single statement ------------------------------------
        if len(parsed) > 1:
            deny(
                "multiple_statements",
                f"Exactly one statement is allowed; found {len(parsed)}.",
            )
            return self._result(violations, warnings, statement_type, normalized_sql)

        root = parsed[0]
        statement_type = type(root).__name__

        # Layer 4 — statement allow-list (SELECT only) ------------------
        if statement_type.upper() not in self.policy.allowed_statements:
            deny(
                "statement_not_allowed",
                f"Statement type {statement_type} is not allowed; only "
                f"{', '.join(self.policy.allowed_statements)} is permitted.",
            )

        # Layer 5 — forbidden nodes anywhere in the tree -----------------
        for node in root.walk():
            if type(node) in _FORBIDDEN_NODE_TYPES:
                deny(
                    "forbidden_construct",
                    f"Construct {type(node).__name__} is forbidden inside a query.",
                )
                break
        if root.args.get("into") is not None:
            deny("select_into", "SELECT ... INTO is not permitted.")
        if root.args.get("locks"):
            deny("for_update", "FOR UPDATE locking reads are not permitted.")

        # Layer 6 — system catalog / schema deny-list --------------------
        denied = set(self.policy.denied_schemas)
        for table in root.find_all(exp.Table):
            for part in (table.args.get("db"), table.args.get("catalog")):
                name = part.name.upper() if isinstance(part, exp.Expression) else ""
                if name and name in denied:
                    deny(
                        "catalog_access",
                        f"Access to system schema '{name}' is restricted.",
                    )

        # Layer 7 — denied functions -------------------------------------
        denied_funcs = set(self.policy.denied_functions)
        for func in root.find_all(exp.Func):
            fname = (func.name or "").upper()
            if fname in denied_funcs:
                deny("denied_function", f"Function '{fname}' is not permitted.")

        # Layer 8 — complexity limits -------------------------------------
        node_count = sum(1 for _ in root.walk())
        if node_count > self.policy.max_ast_nodes:
            deny(
                "ast_too_large",
                f"Query has {node_count} AST nodes; limit is {self.policy.max_ast_nodes}.",
            )
        joins = sum(1 for _ in root.find_all(exp.Join))
        if joins > self.policy.max_joins:
            deny(
                "too_many_joins",
                f"Query has {joins} joins; limit is {self.policy.max_joins}.",
            )
        nested_selects = sum(1 for _ in root.find_all(exp.Select)) - (
            1 if isinstance(root, exp.Select) else 0
        )
        if nested_selects > self.policy.max_subqueries:
            deny(
                "too_many_subqueries",
                f"Query has {nested_selects} nested selects; limit is "
                f"{self.policy.max_subqueries}.",
            )
        for in_clause in root.find_all(exp.In):
            values = in_clause.args.get("expressions") or []
            if len(values) > self.policy.max_in_list:
                deny(
                    "in_list_too_large",
                    f"IN list has {len(values)} values; limit is {self.policy.max_in_list}.",
                )
                break

        # Row-limit advisory ---------------------------------------------
        if (
            self.policy.enforce_row_limit
            and not violations
            and not _ROW_LIMIT_RE.search(sql)
        ):
            warn(
                "missing_row_limit",
                "No FETCH FIRST/LIMIT clause found; the executor applies a hard "
                f"row cap of {self.policy.max_rows}.",
            )

        if not violations and statement_type:
            normalized_sql = root.sql(dialect=self._dialect)

        return self._result(violations, warnings, statement_type, normalized_sql)

    # ------------------------------------------------------------------
    def _result(
        self,
        violations: list[Violation],
        warnings: list[Violation],
        statement_type: str | None,
        normalized_sql: str | None,
    ) -> SqlValidateResponse:
        return SqlValidateResponse(
            valid=not violations,
            statement_type=statement_type,
            dialect=self._dialect or "generic",
            normalized_sql=normalized_sql,
            violations=violations,
            warnings=warnings,
            policy=AppliedPolicy(
                max_rows=self.policy.max_rows,
                timeout_ms=self.policy.query_timeout_ms,
                enforce_row_limit=self.policy.enforce_row_limit,
            ),
        )
