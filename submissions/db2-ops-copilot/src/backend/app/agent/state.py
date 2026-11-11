"""Typed graph state shared by the LangGraph engine and the built-in runner.

Nodes return *partial updates*. Keys in :data:`REDUCED_KEYS` are append-only
(LangGraph reducer ``operator.add``); every other key is replaced. The
built-in runner applies exactly the same rule (:func:`apply_update`), which is
what makes the two engines interchangeable and testable for parity.

Everything in the state is plain JSON-serializable data, so a run can be
returned over the API, audited and replayed from its trace.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

RunStatus = str  # completed | awaiting_approval | refused | needs_clarification | degraded | failed


class AgentState(TypedDict, total=False):
    # -- input --------------------------------------------------------------
    question: str
    session_id: str | None
    request_id: str
    mock: bool
    engine: str
    # -- intent analysis ----------------------------------------------------
    intent: str
    confidence: float
    matched: list[str]
    entities: dict[str, Any]
    # -- diagnostic plan / evidence ------------------------------------------
    plan: list[dict[str, Any]]
    cursor: int
    evidence: Annotated[list[dict[str, Any]], operator.add]
    degraded: bool
    # -- analysis ---------------------------------------------------------------
    findings: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    root_cause: dict[str, Any] | None
    proposal_specs: list[dict[str, Any]]
    # -- human approval ---------------------------------------------------------
    approvals: list[dict[str, Any]]
    # -- diagnostics / output -----------------------------------------------------
    trace: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[dict[str, Any]], operator.add]
    warnings: Annotated[list[str], operator.add]
    status: RunStatus
    fatal: bool
    reply: str
    llm_summary: str | None


REDUCED_KEYS = frozenset({"evidence", "trace", "errors", "warnings"})


def new_state(
    question: str,
    *,
    request_id: str,
    session_id: str | None,
    mock: bool,
    engine: str,
) -> AgentState:
    return AgentState(
        question=question,
        session_id=session_id,
        request_id=request_id,
        mock=mock,
        engine=engine,
        plan=[],
        cursor=0,
        evidence=[],
        findings=[],
        recommendations=[],
        root_cause=None,
        proposal_specs=[],
        approvals=[],
        trace=[],
        errors=[],
        warnings=[],
        degraded=False,
        fatal=False,
        status="running",
        llm_summary=None,
    )


def apply_update(state: AgentState, update: dict[str, Any]) -> AgentState:
    """Merge a node's partial update (reducer keys append, others replace)."""
    merged: dict[str, Any] = dict(state)
    for key, value in update.items():
        if key in REDUCED_KEYS:
            merged[key] = list(merged.get(key, [])) + list(value)
        else:
            merged[key] = value
    return merged  # type: ignore[return-value]
