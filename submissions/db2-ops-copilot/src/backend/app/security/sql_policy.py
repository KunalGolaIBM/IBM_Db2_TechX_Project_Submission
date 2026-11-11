"""SQL security policy — the rule set every generated query must satisfy.

Planned restrictions (implemented as an initial baseline in M1; enforced for
real in M2 when execution against Db2 is enabled):

1. SELECT-only execution (single statement).
2. Single-statement enforcement (AST parse, no stacked queries).
3. AST-based parsing (sqlglot + official db2-sqlglot-dialect plugin).
4. DDL and DML blocked (root statement type allow-list + forbidden node scan).
5. System catalog access restricted (SYSCAT/SYSIBM/... deny-list, configurable).
6. Query limits: max length, AST size, joins, subqueries, row cap, timeout.
7. Parameterized values for all application-owned queries (audit, schema,
   health) — user/LLM SQL is executed read-only with row cap + timeout.
8. Read-only Db2 account (db2ro) — least privilege, no DDL/DML grants.
9. Prompt-injection defense on the natural-language side (see injection.py).

sqlglot parsing is ONE layer, not the whole boundary: defense in depth also
includes the read-only DB account, row/timeout caps, catalog deny-list and
audit logging (see docs/ARCHITECTURE.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True, slots=True)
class SqlPolicy:
    """Immutable policy value object."""

    allowed_statements: tuple[str, ...] = ("SELECT",)
    max_sql_length: int = 5000
    max_ast_nodes: int = 500
    max_subqueries: int = 6
    max_joins: int = 8
    max_in_list: int = 200
    max_rows: int = 100
    query_timeout_ms: int = 10000
    enforce_row_limit: bool = True
    denied_schemas: tuple[str, ...] = (
        "SYSCAT",
        "SYSIBM",
        "SYSSTAT",
        "SYSPROC",
        "SYSIBMADM",
        "SYSIBMSECURITY",
        "SYSTOOLS",
    )
    # Dangerous functions blocked regardless of context (Db2 dynamic SQL etc.)
    denied_functions: tuple[str, ...] = (
        "EXECUTEDIMMEDIATE",
        "ADMIN_CMD",
        "ADMIN_TASK",
    )
    # Extra hard denials regardless of configuration.
    forbidden_keywords: tuple[str, ...] = (
        "INSERT",
        "UPDATE",
        "DELETE",
        "MERGE",
        "CREATE",
        "DROP",
        "ALTER",
        "TRUNCATE",
        "GRANT",
        "REVOKE",
        "CALL",
        "EXECUTE",
        "DECLARE",
        "SET",
        "BEGIN",
        "COMMIT",
        "ROLLBACK",
        "IMPORT",
        "EXPORT",
        "LOAD",
        "RENAME",
        "COMMENT",
        "CONNECT",
        "ATTACH",
        "QUIESCE",
        "START",
        "STOP",
        "BIND",
        "REBIND",
        "RUN",
    )

    @classmethod
    def from_settings(cls, settings) -> "SqlPolicy":
        """Build a policy from the application settings."""
        return cls(
            max_sql_length=settings.sql_max_length,
            max_ast_nodes=settings.sql_max_ast_nodes,
            max_subqueries=settings.sql_max_subqueries,
            max_joins=settings.sql_max_joins,
            max_in_list=settings.sql_max_in_list,
            max_rows=settings.sql_max_rows,
            query_timeout_ms=settings.sql_query_timeout_ms,
            enforce_row_limit=settings.sql_enforce_row_limit,
            denied_schemas=tuple(settings.denied_schemas_list),
        )

    def with_overrides(self, **changes) -> "SqlPolicy":
        return replace(self, **changes)


DEFAULT_POLICY = SqlPolicy()
