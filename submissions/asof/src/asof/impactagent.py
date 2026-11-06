"""The change-impact agent: after a policy change, draft corrected help-centre answers.

    find (CHANGE_IMPACT) -> for each stale help-centre answer:
        look up (agent with Db2 tools) -> draft (rewrite from the clause in force) ->
        check (the full check graph, on the date the answer went stale) -> store (ADD_SUGGESTION)

A LangGraph graph like the check itself. The agent only gathers context and drafts; it never
publishes. Every draft goes through the full check on the date it must hold from, and only a
draft the check released (PASS or CORRECTED) can later be approved, by the policy editor, through
DECIDE_SUGGESTION. Approval does not rewrite history: the old answer keeps the dates before the
change, and the correction covers the dates after it.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from . import db, policy
from .checkgraph import MAX_TOOL_CALLS, _Tools, tool_loop
from .gate import Gate, GateRequest
from .llm import LLMError
from .prompts import impact_messages
from .retriever import RetrievedClause

log = logging.getLogger(__name__)

MAX_ANSWERS = 10  # per run: each costs a draft plus a full check
SQL_IN_FORCE = ("SELECT CLAUSE_ID, AREA, TITLE, VERSION_LABEL, CLAUSE_TEXT, RULE_JSON, BUS_START, BUS_END, SYS_START "
                "FROM POLICY_CLAUSE FOR BUSINESS_TIME AS OF ? WHERE CLAUSE_ID = ?")


class ImpactState(TypedDict, total=False):
    targets: list  # stale help-centre answers still to handle
    current: dict
    results: list


def _clause_in_force(conn, clause_id: str, on: date, schema: str) -> RetrievedClause | None:
    import json

    db.use_schema(conn, schema)
    rows = db.query(conn, SQL_IN_FORCE, (on, clause_id))
    if not rows:
        return None
    r = rows[0]
    return RetrievedClause(r[0], r[1], r[2], r[3], r[4], json.loads(r[5]), r[6], r[7], r[8], 0.0)


def draft_fixes(gate: Gate, clause_id: str) -> list[dict[str, Any]]:
    """Run the agent for one changed clause. Returns one record per stale help-centre answer."""

    def find(state: ImpactState) -> dict[str, Any]:
        conn = gate.connect()
        try:
            impact = policy.change_impact(conn, clause_id, gate.schema)
            pending = {s["answer_id"] for s in policy.suggestions(conn, clause_id, gate.schema) if s["status"] == "PENDING"}
            targets = []
            for row in impact:
                if (row["kind"] == "PUBLISHED" and row["status"] == "NEEDS_REVIEW" and row["stale_from"]
                        and row["ref_id"] not in pending):  # a draft already waits for the editor
                    answer = policy.published_answer(conn, row["ref_id"], gate.schema)
                    changed = _clause_in_force(conn, clause_id, row["stale_from"], gate.schema)
                    if answer and changed:
                        targets.append({"answer": answer, "stale_from": row["stale_from"], "changed": changed})
        finally:
            conn.close()
        return {"targets": targets[:MAX_ANSWERS], "results": []}

    def next_target(state: ImpactState) -> dict[str, Any]:
        return {"current": state["targets"][0], "targets": state["targets"][1:]}

    def handle(state: ImpactState) -> dict[str, Any]:
        t = state["current"]
        answer, changed, stale_from = t["answer"], t["changed"], t["stale_from"]
        record: dict[str, Any] = {"answer_id": answer["answer_id"], "stale_from": stale_from,
                                  "based_on_version": changed.version_label}
        try:
            # 1. Look up what else the answer relies on (agent with Db2 tools, bounded).
            tools = _Tools(gate, stale_from, answer["doc_id"])
            (_, system), (_, human) = impact_messages(stale_from, answer["question"], answer["answer_text"], changed.view())
            trace, _ = tool_loop(gate, [SystemMessage(system), HumanMessage(human)], tools, MAX_TOOL_CALLS, 1,
                                 {changed.clause_id})
            context = [changed] + [c for cid, c in tools.found.items() if cid != changed.clause_id]
            # 2. Draft from the clause text in force from the stale date (the check's own rewrite step).
            problems = [(answer["answer_text"][:300], "STALE",
                         f"written from {clause_id} {answer['cited_version']}; {changed.version_label} applies from "
                         f"{stale_from.isoformat()}")]
            draft = gate._rewrite_from(answer["question"], answer["answer_text"], stale_from, context, problems)
            # 3. The full check, on the date the answer must hold from. It records its own ledger row.
            checked = gate.check(GateRequest(answer["question"], draft, stale_from, answer["doc_id"], "faq"))
            text = checked.final_answer if checked.decision in ("PASS", "CORRECTED") else draft
            # 4. Store as a pending suggestion; only the policy editor can publish it.
            conn = gate.connect()
            try:
                sid = policy.add_suggestion(conn, answer["answer_id"], clause_id, stale_from, changed.version_label, text,
                                            checked.decision, checked.ledger_id, trace, gate.schema)
            finally:
                conn.close()
            record.update(suggestion_id=sid, check_decision=checked.decision, check_reason=checked.reason_code,
                          check_ledger_id=checked.ledger_id, text=text, agent_trace=trace)
        except (LLMError, db.DatabaseError) as exc:
            log.warning("could not draft a fix for %s: %s", answer["answer_id"], exc)
            record.update(error=str(exc)[:300])
        return {"results": state["results"] + [record]}

    g = StateGraph(ImpactState)
    g.add_node("find", find)
    g.add_node("next_target", next_target)
    g.add_node("handle", handle)
    g.add_edge(START, "find")
    more = lambda s: "next_target" if s.get("targets") else END  # noqa: E731
    g.add_conditional_edges("find", more, ["next_target", END])
    g.add_edge("next_target", "handle")
    g.add_conditional_edges("handle", more, ["next_target", END])
    out = g.compile().invoke({}, {"recursion_limit": 5 + 3 * MAX_ANSWERS})
    return out.get("results", [])
