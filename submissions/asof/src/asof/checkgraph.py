"""The check as a LangGraph state graph, with one agentic step.

    extract -> retrieve (Db2) -> judge + checks -> [investigate: agent with Db2 tools] -> decide
       ^                                                                                  |
       +------------------------- rewrite (once, then a full re-check) <-------------------+
                                                                                          v
                                                         finalize: record in the Db2 ledger (always)
    any error -> fail_closed -> finalize

What the model decides and what it does not:
- The edges are fixed and chosen from deterministic state (verdicts, the pass number, errors).
  No model decides whether the rule check, the re-check or the ledger write happens.
- The one agentic node, `investigate`, runs only when a claim matched no clause. A tool-calling
  model searches Db2 again with its own queries (as-of search, a clause's dated versions), at
  most 3 tool calls over at most 2 rounds. Whatever it finds is only new evidence: the uncovered
  claims go back through the same judge, verbatim-quote rule and deterministic rule check.
  It can turn NOT_COVERED into SUPPORTED or CONTRADICTED only through those checks, and if it
  fails, the claims stay NOT_COVERED (which can only escalate or rewrite, never release).
- Every other failure routes to `fail_closed`: ESCALATED with a holding reply.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.graph import END, START, StateGraph

from . import db
from .gate import (
    HOLDING_REPLY,
    ClaimOutcome,
    Gate,
    GateRequest,
    GateResult,
    TooManyClaims,
    pool_of,
    references,
    unchecked_details,
)
from .llm import LLMError
from .prompts import investigate_messages
from .redact import redact
from .retriever import RetrievedClause, clauses_as_of

log = logging.getLogger(__name__)

MAX_TOOL_CALLS = 3
MAX_ROUNDS = 2
SQL_VERSIONS = ("SELECT VERSION_LABEL, BUS_START, BUS_END, CHANGE_NOTE FROM POLICY_CLAUSE "
                "WHERE CLAUSE_ID = ? AND DOC_ID = ? ORDER BY BUS_START")


class CheckState(TypedDict, total=False):
    question: str  # redacted
    text: str  # what this pass checks: the redacted draft, then the rewrite
    pass_no: int
    claims: list
    per_claim: list
    pool: dict
    outcomes: list
    first: list
    second: list
    rewrite: str | None
    decision: str
    reason: str
    final: str
    error: str | None
    investigation: list
    tool_calls_left: int
    unchecked: list  # details in the text that no extracted claim stated


class _Tools:
    """The agent's Db2 tools, bound to one check's date and policy document."""

    def __init__(self, gate: Gate, as_of: date, doc_id: str):
        self.gate, self.as_of, self.doc_id = gate, as_of, doc_id
        self.found: dict[str, RetrievedClause] = {}

    def search_policy(self, query: str) -> str:
        """Search the policy clauses in force on the customer's date by meaning."""
        vec = self.gate.embeddings.embed_query(query[:400])
        conn = self.gate.connect()
        try:
            hits = clauses_as_of(conn, vec, self.as_of, self.doc_id, self.gate.k, schema=self.gate.schema)
        finally:
            conn.close()
        for c in hits:
            self.found.setdefault(c.clause_id, c)
        return json.dumps([{"clause_id": c.clause_id, "version": c.version_label, "title": c.title,
                            "text": c.clause_text[:300]} for c in hits])

    def clause_versions(self, clause_id: str) -> str:
        """List every dated version of one policy clause (to see whether it changed around a date)."""
        conn = self.gate.connect()
        try:
            db.use_schema(conn, self.gate.schema)
            rows = db.query(conn, SQL_VERSIONS, (clause_id[:32], self.doc_id))
        finally:
            conn.close()
        return json.dumps([{"version": v, "from": str(f), "to": "open" if t.year >= 9999 else str(t), "note": n}
                           for v, f, t, n in rows])

    def as_langchain(self) -> list[StructuredTool]:
        return [StructuredTool.from_function(self.search_policy), StructuredTool.from_function(self.clause_versions)]


def tool_loop(gate: Gate, messages: list, tools: _Tools, left: int, pass_no: int,
              known: set[str]) -> tuple[list[dict[str, Any]], int]:
    """Let the model call the Db2 tools: at most `left` calls over at most MAX_ROUNDS rounds.

    Returns the trace (one entry per call, or one error entry) and the calls left. Clauses the
    searches surface accumulate in `tools.found`; `known` marks the ones already retrieved.
    """
    trace: list[dict[str, Any]] = []
    by_name = {t.name: t for t in tools.as_langchain()}
    try:
        for _ in range(MAX_ROUNDS):
            if left <= 0:
                break
            msg: AIMessage = gate.llm.tool_round(messages, list(by_name.values()))
            calls = [c for c in (msg.tool_calls or []) if c.get("name") in by_name][:left]
            if not calls:
                break
            messages.append(AIMessage(content=msg.content or "", tool_calls=calls))
            for call in calls:
                before = set(tools.found)
                output = by_name[call["name"]].invoke(call.get("args") or {})
                returned = sorted(set(tools.found) - before)
                trace.append({"pass": pass_no, "tool": call["name"],
                              "args": {k: str(v)[:120] for k, v in (call.get("args") or {}).items()},
                              "returned": returned,  # clauses this call surfaced
                              "new": [c for c in returned if c not in known]})  # not retrieved before
                messages.append(ToolMessage(content=str(output)[:4000], tool_call_id=call.get("id") or call["name"]))
            left -= len(calls)
    except (LLMError, db.DatabaseError, ValueError) as exc:
        # The agent is an extra look, never a gate: if it fails, the caller carries on without it.
        log.warning("agent tool loop stopped: %s", exc)
        trace.append({"pass": pass_no, "tool": None, "error": str(exc)[:200]})
    return trace, left


def build(gate: Gate, req: GateRequest, deadline_at: float | None = None):
    """Compile the graph for one request (nodes close over the gate and the request).
    `deadline_at` (time.monotonic()) is when the check's budget runs out: no node starts after it."""
    domain = gate.domain(req.doc_id)  # from the validated doc_id, never from the model

    def guarded(fn):
        def node(state: CheckState) -> dict[str, Any]:
            if deadline_at is not None and time.monotonic() > deadline_at:
                log.warning("check failed closed: its %.0f s budget ran out before %s", gate.deadline_s, fn.__name__)
                return {"error": f"the check's {gate.deadline_s:.0f} s budget ran out", "reason": "ERROR_FAIL_CLOSED"}
            try:
                return fn(state)
            except TooManyClaims as exc:
                return {"error": str(exc), "reason": "TOO_MANY_CLAIMS"}
            except (LLMError, db.DatabaseError) as exc:
                log.warning("check failed closed (%s): %s", type(exc).__name__, exc)
                return {"error": str(exc)[:300], "reason": "ERROR_FAIL_CLOSED"}
            except Exception as exc:  # noqa: BLE001 - anything unexpected must still fail closed
                log.exception("check failed closed on an unexpected error")
                return {"error": type(exc).__name__, "reason": "ERROR_FAIL_CLOSED"}
        node.__name__ = fn.__name__
        return node

    def extract(state: CheckState) -> dict[str, Any]:
        return {"claims": gate.extract(state["question"], state["text"], domain), "per_claim": [], "pool": {},
                "outcomes": []}

    def retrieve(state: CheckState) -> dict[str, Any]:
        per_claim = gate.retrieve(state["claims"], req.as_of, req.doc_id)
        return {"per_claim": per_claim, "pool": pool_of(per_claim)}

    def judge(state: CheckState) -> dict[str, Any]:
        return {"outcomes": gate.judge(state["claims"], state["per_claim"], state["pool"], req.as_of, domain=domain)}

    def investigate(state: CheckState) -> dict[str, Any]:
        outcomes: list[ClaimOutcome] = list(state["outcomes"])
        open_idx = [i for i, o in enumerate(outcomes) if o.verdict == "NOT_COVERED"]
        tools = _Tools(gate, req.as_of, req.doc_id)
        (_, system), (_, human) = investigate_messages(req.as_of, [outcomes[i].text for i in open_idx],
                                                      [c.view() for c in state["pool"].values()],
                                                      domain.investigate_system)
        steps, left = tool_loop(gate, [SystemMessage(system), HumanMessage(human)], tools,
                                state.get("tool_calls_left", MAX_TOOL_CALLS), state["pass_no"], set(state["pool"]))
        trace = list(state.get("investigation", [])) + steps
        new = {cid: c for cid, c in tools.found.items() if cid not in state["pool"]}
        if not new:
            return {"investigation": trace, "tool_calls_left": left}
        pool = {**state["pool"], **new}
        claims = [state["claims"][i] for i in open_idx]
        found = [list(state["per_claim"][i]) + list(new.values()) for i in open_idx]
        rejudged = gate.judge(claims, found, pool, req.as_of, numbers=[outcomes[i].claim_no for i in open_idx],
                              domain=domain)
        for i, o in zip(open_idx, rejudged, strict=True):
            outcomes[i] = o
        return {"outcomes": outcomes, "pool": pool, "investigation": trace, "tool_calls_left": left}

    def decide(state: CheckState) -> dict[str, Any]:
        outcomes = state.get("outcomes", [])
        unchecked = unchecked_details(state["text"], [c.text for c in outcomes], state["question"])
        if state["pass_no"] == 1:
            decision, reason, final = gate._decide(outcomes, req.draft_answer, unchecked)
            return {"first": outcomes, "decision": decision, "reason": reason, "final": final, "unchecked": unchecked}
        if outcomes and all(c.verdict == "SUPPORTED" for c in outcomes) and not unchecked:
            return {"second": outcomes, "decision": "CORRECTED", "reason": "CORRECTED_FROM_CLAUSES",
                    "final": state["rewrite"] + references(outcomes)}
        return {"second": outcomes, "decision": "ESCALATED", "reason": "CORRECTION_FAILED", "final": HOLDING_REPLY,
                "unchecked": unchecked}

    def rewrite(state: CheckState) -> dict[str, Any]:
        text = gate._rewrite(state["question"], state["text"], req.as_of, state["first"], domain)
        return {"rewrite": text, "text": text, "pass_no": 2}

    def fail_closed(state: CheckState) -> dict[str, Any]:
        out: dict[str, Any] = {"decision": "ESCALATED", "reason": state.get("reason") or "ERROR_FAIL_CLOSED",
                               "final": HOLDING_REPLY}
        if state["pass_no"] == 1 and not state.get("first"):  # keep what was judged before the failure as evidence
            out["first"] = state.get("outcomes", [])
        return out

    # ---- routing: deterministic, from state only ----------------------------------------------
    def after(step: str):
        def route(state: CheckState) -> str:
            if state.get("error"):
                return "fail_closed"
            if step == "extract":
                return "retrieve" if state["claims"] else "decide"
            if step == "judge":
                wants = gate.investigate and state.get("tool_calls_left", MAX_TOOL_CALLS) > 0 and any(
                    o.verdict == "NOT_COVERED" for o in state["outcomes"])
                return "investigate" if wants else "decide"
            if step == "decide":
                return "rewrite" if state["decision"] == "REWRITE" and state["pass_no"] == 1 else END
            return {"retrieve": "judge", "investigate": "decide", "rewrite": "extract"}[step]
        return route

    g = StateGraph(CheckState)
    for name, fn in (("extract", extract), ("retrieve", retrieve), ("judge", judge), ("investigate", investigate),
                     ("decide", decide), ("rewrite", rewrite)):
        g.add_node(name, guarded(fn))
    g.add_node("fail_closed", fail_closed)
    g.add_edge(START, "extract")
    g.add_conditional_edges("extract", after("extract"), ["retrieve", "decide", "fail_closed"])
    g.add_conditional_edges("retrieve", after("retrieve"), ["judge", "fail_closed"])
    g.add_conditional_edges("judge", after("judge"), ["investigate", "decide", "fail_closed"])
    g.add_conditional_edges("investigate", after("investigate"), ["decide", "fail_closed"])
    g.add_conditional_edges("decide", after("decide"), ["rewrite", "fail_closed", END])
    g.add_conditional_edges("rewrite", after("rewrite"), ["extract", "fail_closed"])
    g.add_edge("fail_closed", END)
    return g.compile()


def run_check(gate: Gate, req: GateRequest) -> GateResult:
    """One check, start to ledger. Recording happens even when the graph failed closed."""
    started = time.monotonic()
    getattr(gate.llm, "begin_check", lambda: None)()  # per-check usage, e.g. provider fallback
    q, d = redact(req.question), redact(req.draft_answer)
    state: CheckState = {"question": q.text, "text": d.text, "pass_no": 1, "first": [], "second": [],
                         "rewrite": None, "error": None, "investigation": [], "tool_calls_left": MAX_TOOL_CALLS}
    try:
        state = build(gate, req, started + gate.deadline_s).invoke(state, {"recursion_limit": 25})
    except Exception as exc:  # noqa: BLE001 - the graph itself failing must still fail closed
        log.exception("check graph failed")
        state = {**state, "decision": "ESCALATED", "reason": "ERROR_FAIL_CLOSED", "final": HOLDING_REPLY,
                 "error": type(exc).__name__}
    result = GateResult(str(uuid.uuid4()), state["decision"], state["reason"], state["final"],
                        state.get("first", []), state.get("second", []), state.get("rewrite"),
                        int((time.monotonic() - started) * 1000), gate.llm.info, error=state.get("error"),
                        investigation=state.get("investigation", []), unchecked=state.get("unchecked", []))
    gate._record(req, q.text, d.text, result, q.counts, d.counts)
    return result
