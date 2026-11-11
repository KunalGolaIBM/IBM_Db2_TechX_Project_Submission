"""Approved maintenance actions: a closed set of templates, never free-form SQL.

The agent cannot hand SQL to the database. It can only *propose* one of the
action types below with validated identifiers; a human approves; and at
execution time the statement is **re-rendered from the structured parameters**
and compared with what the human saw (tamper check) before it is allowed
through a strict allow-list regex.

None of these statements pass the free-form SQL gate (it is SELECT-only) —
that is deliberate and tested: the approval path is the *only* route to them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.core.errors import AppError
from app.dba.specs import is_reserved_schema, normalize_identifier

ActionType = Literal["runstats", "create_index"]
Risk = Literal["low", "medium", "high"]


class ActionError(AppError):
    code = "INVALID_ACTION"
    status_code = 422


@dataclass(frozen=True, slots=True)
class ActionSpec:
    type: str
    title: str
    risk: Risk
    description: str
    impact: str
    params: tuple[str, ...]


ACTIONS: dict[str, ActionSpec] = {
    "runstats": ActionSpec(
        type="runstats",
        title="Collect table statistics (RUNSTATS)",
        risk="low",
        description="Refreshes optimizer statistics for one table and its indexes.",
        impact=(
            "Reads the whole table; short-lived load. Changes no data. "
            "Cached access plans may be re-optimized afterwards."
        ),
        params=("schema", "table"),
    ),
    "create_index": ActionSpec(
        type="create_index",
        title="Create an index",
        risk="medium",
        description="Creates a single-column index on one table.",
        impact=(
            "Locks/scans the table while the index is built and adds write "
            "overhead. Reversible with DROP INDEX (not automated)."
        ),
        params=("schema", "table", "column"),
    ),
}

_ID = r"[A-Z_][A-Z0-9_$#@]{0,127}"
# Strict allow-list: the ONLY statements an approval can ever execute.
_ALLOWED: tuple[re.Pattern[str], ...] = (
    re.compile(rf"CREATE INDEX {_ID}\.{_ID} ON {_ID}\.{_ID} \({_ID}\)"),
    re.compile(
        rf"CALL SYSPROC\.ADMIN_CMD\('RUNSTATS ON TABLE {_ID}\.{_ID} "
        r"WITH DISTRIBUTION AND DETAILED INDEXES ALL'\)"
    ),
)
_FORBIDDEN_WORDS = re.compile(
    r"\b(DROP|DELETE|TRUNCATE|ALTER|UPDATE|INSERT|MERGE|GRANT|REVOKE|"
    r"FORCE|DEACTIVATE|RESTORE|EXPORT|IMPORT|LOAD|REORG)\b"
)


@dataclass(frozen=True, slots=True)
class PreparedAction:
    type: str
    params: dict[str, str]
    statement: str
    spec: ActionSpec


def index_name_for(table: str, column: str) -> str:
    return f"IDX_{table}_{column}"[:128]


def _normalize(action_type: str, params: dict[str, Any]) -> dict[str, str]:
    spec = ACTIONS.get(action_type)
    if spec is None:
        raise ActionError(
            f"Unsupported action type '{action_type}'.",
            detail={"supported": sorted(ACTIONS)},
        )
    supplied = dict(params or {})
    extra = sorted(set(supplied) - set(spec.params))
    missing = sorted(set(spec.params) - set(supplied))
    if extra or missing:
        raise ActionError(
            f"Action '{action_type}' takes exactly: {', '.join(spec.params)}.",
            detail={"unexpected": extra, "missing": missing},
        )
    try:
        normalized = {name: normalize_identifier(name, supplied[name]) for name in spec.params}
    except AppError as exc:
        raise ActionError(exc.message, detail=exc.detail) from exc
    if is_reserved_schema(normalized["schema"]):
        raise ActionError(
            "Maintenance actions on system schemas are not allowed.",
            detail={"param": "schema"},
        )
    return normalized


def render_statement(action_type: str, params: dict[str, Any]) -> str:
    """Render the one statement for ``action_type`` (identifiers validated)."""
    p = _normalize(action_type, params)
    if action_type == "runstats":
        return (
            "CALL SYSPROC.ADMIN_CMD('RUNSTATS ON TABLE "
            f"{p['schema']}.{p['table']} WITH DISTRIBUTION AND DETAILED INDEXES ALL')"
        )
    return (
        f"CREATE INDEX {p['schema']}.{index_name_for(p['table'], p['column'])} "
        f"ON {p['schema']}.{p['table']} ({p['column']})"
    )


def prepare_action(
    action_type: str,
    params: dict[str, Any],
    stored_statement: str | None = None,
) -> PreparedAction:
    """Re-validate an action right before execution (fail-closed).

    1. type + parameter set + identifiers + schema policy,
    2. statement re-rendered from the parameters,
    3. must equal the statement the human approved (``stored_statement``),
    4. must fully match the allow-list and contain no forbidden verb.
    """
    normalized = _normalize(action_type, params)
    statement = render_statement(action_type, normalized)
    if stored_statement is not None and stored_statement != statement:
        raise ActionError(
            "The stored statement does not match the approved action parameters.",
            detail={"reason": "statement_mismatch"},
        )
    if ";" in statement or _FORBIDDEN_WORDS.search(statement.upper()):
        raise ActionError("The rendered statement contains a forbidden construct.")
    if not any(rx.fullmatch(statement) for rx in _ALLOWED):
        raise ActionError("The rendered statement is not on the action allow-list.")
    return PreparedAction(
        type=action_type,
        params=normalized,
        statement=statement,
        spec=ACTIONS[action_type],
    )
