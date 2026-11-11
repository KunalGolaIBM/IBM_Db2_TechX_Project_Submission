"""SQL guard service — validation + execution preparation (M2.6).

``validate()`` is the public gate used by ``POST /api/v1/sql/validate`` and the
chat pipeline.

``prepare_for_execution()`` is step 2 of the execution path (M2.6):

1. validate (fail-closed gate),
2. **prepare** — apply the deterministic hard row cap here,
3. explain (best-effort dry-run),
4. execute under the read-only account with a session timeout,
5. record in APP.QUERY_EXECUTIONS (+ audit rejections).

Row-cap strategy (``SQL_ENFORCE_ROW_LIMIT``):

- Already-capped statements (``FETCH FIRST n ROWS ONLY`` with ``n <=
  max_rows``) pass through untouched — re-wrapping would only add cost.
- Anything else is wrapped as::

      SELECT * FROM (<validated sql>) AS _COPILOT_Q
      [ORDER BY ...] FETCH FIRST <max_rows> ROWS ONLY

  The top-level ORDER BY is moved *outside* the subselect during the wrap
  (sqlglot AST), because Db2 restricts ORDER BY inside subselects — the
  generated statement is then re-validated through the same gate before use.

The transport-level ``fetchmany(max_rows + 1)`` cap in the database adapter
remains as the second, independent layer.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from app.adapters.sql_validator.sqlglot_validator import (
    SqlGlotValidator,
    resolve_dialect,
)
from app.schemas.sql import SqlValidateResponse
from app.security.sql_policy import SqlPolicy

logger = logging.getLogger(__name__)

_FETCH_FIRST_RE = re.compile(r"\bFETCH\s+FIRST\s+(\d+)\s+ROW", re.IGNORECASE)

_WRAP_ALIAS = "_COPILOT_Q"


@dataclass(frozen=True, slots=True)
class PreparedQuery:
    """A validated statement ready for the execution layer."""

    sql: str
    row_limit: int
    row_limit_applied: bool  # True when the hard-cap wrap was added
    warnings: tuple[str, ...] = ()


class SqlGuardService:
    def __init__(self, validator: SqlGlotValidator) -> None:
        self._validator = validator

    @property
    def policy(self) -> SqlPolicy:
        return self._validator.policy

    def validate(self, sql: str) -> SqlValidateResponse:
        return self._validator.validate(sql)

    # -- M2.6 ------------------------------------------------------------
    def prepare_for_execution(self, sql: str) -> PreparedQuery:
        """Apply the deterministic hard row cap to an already-validated SQL.

        Fail-soft by design: if the wrap cannot be built (should be
        impossible — the SQL passed the same dialect's gate milliseconds
        ago), the ORIGINAL statement is returned unchanged. The adapter's
        ``fetchmany(max_rows + 1)`` still bounds the result, so rows can
        never exceed the policy even without the wrap.
        """
        policy = self.policy
        if not policy.enforce_row_limit:
            return PreparedQuery(sql=sql, row_limit=policy.max_rows, row_limit_applied=False)

        existing = _FETCH_FIRST_RE.search(sql)
        if existing and int(existing.group(1)) <= policy.max_rows:
            # Already capped at or below the policy limit — leave it alone.
            return PreparedQuery(sql=sql, row_limit=policy.max_rows, row_limit_applied=False)

        try:
            wrapped = self._wrap_with_row_cap(sql, policy.max_rows)
        except (SqlglotError, ValueError) as exc:
            logger.warning(
                "row-cap wrap failed (%s); executing the validated statement "
                "as-is — the adapter fetch cap still bounds the result",
                type(exc).__name__,
            )
            return PreparedQuery(sql=sql, row_limit=policy.max_rows, row_limit_applied=False)

        # Defense in depth: the generated statement must pass the same gate.
        revalidation = self._validator.validate(wrapped)
        if not revalidation.valid:
            codes = ", ".join(v.code for v in revalidation.violations)
            logger.warning(
                "row-cap wrap failed re-validation (%s); executing the "
                "validated statement as-is — adapter fetch cap still applies",
                codes,
            )
            return PreparedQuery(
                sql=sql,
                row_limit=policy.max_rows,
                row_limit_applied=False,
                warnings=(f"row_cap_wrap_skipped: {codes}",),
            )
        return PreparedQuery(
            sql=wrapped,
            row_limit=policy.max_rows,
            row_limit_applied=True,
            warnings=tuple(w.message for w in revalidation.warnings),
        )

    @staticmethod
    def _wrap_with_row_cap(sql: str, max_rows: int) -> str:
        """Wrap ``sql`` so the server itself can never return more rows.

        The top-level ORDER BY is relocated to the outer query — Db2
        restricts ORDER BY inside subselects, and the outer position keeps
        result ordering identical while the FETCH FIRST cap applies to the
        final, ordered rows.
        """
        dialect, _ = resolve_dialect()
        tree = sqlglot.parse_one(sql, dialect=dialect)
        if tree is None:
            raise ValueError("empty parse tree")
        order = tree.args.pop("order", None)
        outer = exp.select("*").from_(tree.subquery(alias=_WRAP_ALIAS))
        if order is not None:
            outer.set("order", order)
        outer = outer.limit(max_rows)
        return outer.sql(dialect=dialect)
