"""The agent graph.

    begin -> normalize -> persist_facts -> retrieve -> record_trace -> explain -> finalize
                    \\-> clarify (when nothing could be extracted)

* ``retrieve`` runs one SQL statement that filters by residency and ranks
  clauses with Db2's VECTOR_DISTANCE.
* ``record_trace`` calls SP_RECORD_TRACE, which evaluates every active
  scheme's rules against the applicant's facts inside Db2.
* ``explain`` is the only node that talks to an LLM, and it cannot alter a
  verdict - it receives them as read-only input.

LangGraph is the execution engine. A sequential fallback exists so the
project still runs in environments where the dependency cannot be
installed; the graph is the documented path.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from .. import db
from ..config import settings
from ..embeddings import embed_query, vector_literal
from ..models import RuleRow, SchemeResult
from ..rules import CATEGORY_ORDER, classify, group_by_scheme, readiness, split_parts
from . import llm

try:  # pragma: no cover - exercised only when the dependency is present
    from langgraph.graph import END, StateGraph

    HAS_LANGGRAPH = True
except Exception:  # pragma: no cover
    END = "__end__"
    StateGraph = None
    HAS_LANGGRAPH = False


class AgentState(TypedDict, total=False):
    run_id: str
    profile_id: str
    raw_text: str
    category: Optional[str]
    facts: Dict[str, Any]
    retrieval_query: str
    notes: List[str]
    retrieved: List[Dict[str, Any]]
    rules: List[Dict[str, Any]]
    results: List[Dict[str, Any]]
    counts: Dict[str, int]
    filtered_by_residency: int
    message: Optional[str]
    status: str
    error: Optional[str]
    t0: float


# ---------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------
def node_begin(state: AgentState) -> Dict[str, Any]:
    with db.connect() as conn:
        db.create_profile(conn, state["profile_id"], state["raw_text"])
        db.start_run(conn, state["run_id"], state["profile_id"],
                     settings.retriever_top_k, datetime.now())
        db.audit(conn, state["run_id"], "user", "request.received",
                 f"{len(state['raw_text'])} characters")
    return {"status": "RUNNING"}


def node_normalize(state: AgentState) -> Dict[str, Any]:
    profile = llm.normalize_profile(state["raw_text"])
    facts = dict(profile.facts)
    notes = list(profile.notes)
    if not facts:
        notes.append("no eligibility facts could be extracted")
    return {
        "facts": facts,
        "retrieval_query": profile.retrieval_query or state["raw_text"],
        "notes": notes,
    }


def node_persist_facts(state: AgentState) -> Dict[str, Any]:
    facts = state.get("facts", {})
    with db.connect() as conn:
        db.insert_facts(conn, state["profile_id"], facts, json.dumps(facts, default=str))
        db.audit(conn, state["run_id"], "agent", "profile.normalized",
                 json.dumps(facts, default=str)[:1800])
    return {}


def node_retrieve(state: AgentState) -> Dict[str, Any]:
    query_text = state.get("retrieval_query") or state["raw_text"]
    vector = vector_literal(embed_query(query_text))
    values = {
        "state": state.get("facts", {}).get("state_code"),
        "category": state.get("category"),
        "query_vec": vector,
    }
    with db.connect() as conn:
        rows = db.fetch_named(conn, "retrieval", values)
        db.audit(conn, state["run_id"], "agent", "retrieval.vector_search",
                 f"{len(rows)} clauses retrieved")
    limit = max(1, settings.retriever_top_k)
    return {"retrieved": rows[:limit]}


def node_record_trace(state: AgentState) -> Dict[str, Any]:
    with db.connect() as conn:
        rows = db.record_trace(conn, state["run_id"], state["profile_id"])
        db.audit(conn, state["run_id"], "agent", "eligibility.evaluated",
                 f"{rows} rule rows written by SP_RECORD_TRACE")
    return {}


def node_explain(state: AgentState) -> Dict[str, Any]:
    results, filtered = _collect_results(state)
    contexts = [_explain_context(item, state) for item in results]
    narratives = llm.narrate(contexts)

    with db.connect() as conn:
        for item in results:
            produced = narratives.get(item.scheme_id, {})
            item.narrative = produced.get("narrative")
            item.citations = produced.get("cited_chunk_ids", [])
            db.execute(
                conn,
                "UPDATE decision_trace SET narrative = ? WHERE run_id = ? AND scheme_id = ?",
                (item.narrative, state["run_id"], item.scheme_id),
            )
        db.audit(
            conn, state["run_id"], "agent", "decision.explained",
            f"mode={'mock' if settings.llm_is_mock else 'live'} narratives={len(narratives)}",
        )
    return {
        "results": [item.model_dump() for item in results],
        "filtered_by_residency": filtered,
    }


def node_clarify(state: AgentState) -> Dict[str, Any]:
    message = (
        "I could not read any eligibility facts from that description. "
        "Tell me your age, state, occupation, annual household income, "
        "marital status and category (SC/ST/OBC/general), and I can decide."
    )
    _finish(state, status="NEEDS_INPUT", results=[], filtered=0, message=message)
    return {"status": "NEEDS_INPUT", "message": message, "results": [], "counts": {}}


def node_finalize(state: AgentState) -> Dict[str, Any]:
    results = state.get("results", [])
    counts = _counts(results)
    _finish(state, status="COMPLETED", results=results,
            filtered=state.get("filtered_by_residency", 0), message=None)
    return {"status": "COMPLETED", "counts": counts}


def _finish(state: AgentState, status: str, results: List[Dict[str, Any]],
            filtered: int, message: Optional[str]) -> None:
    summary = {
        "counts": _counts(results),
        "filtered_by_residency": filtered,
        "llm_mode": "mock" if settings.llm_is_mock else "live",
        "model": settings.llm_model,
        "message": message,
        "schemes": [
            {
                "scheme_id": r["scheme_id"],
                "label": r["label"],
                "readiness": r["readiness"],
                "narrative": r.get("narrative"),
            }
            for r in results
        ],
    }
    with db.connect() as conn:
        db.finish_run(conn, state["run_id"], status, _elapsed(state),
                      len(results), json.dumps(summary, default=str))
        db.audit(conn, state["run_id"], "agent", f"run.{status.lower()}",
                 f"{len(results)} schemes decided")


def _elapsed(state: AgentState) -> int:
    return int((time.time() - state.get("t0", time.time())) * 1000)


def _counts(results: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"eligible": 0, "near_miss": 0, "clarify": 0, "not_eligible": 0}
    for item in results:
        key = str(item["label"]).lower()
        if key in counts:
            counts[key] += 1
    return counts


def _collect_results(state: AgentState) -> tuple[List[SchemeResult], int]:
    with db.connect() as conn:
        rows = db.fetch_named(conn, "scheme_trace", {"run_id": state["run_id"]})

    state_code = state.get("facts", {}).get("state_code")
    distance: Dict[str, float] = {}
    for chunk in state.get("retrieved", []):
        current = distance.get(chunk["scheme_id"])
        value = float(chunk["distance"])
        if current is None or value < current:
            distance[chunk["scheme_id"]] = value

    grouped = group_by_scheme([_to_rule(row) for row in rows])
    meta = {row["scheme_id"]: row for row in rows}

    results: List[SchemeResult] = []
    filtered = 0
    for scheme_id, rule_rows in grouped.items():
        info = meta[scheme_id]
        scheme_state = info.get("state_code") or "ALL"
        if state_code and scheme_state not in ("ALL", state_code):
            filtered += 1
            continue
        blocking, advisory, missing = split_parts(rule_rows)
        label = classify(rule_rows)
        results.append(
            SchemeResult(
                scheme_id=scheme_id,
                name=info["name"],
                category=info["category"],
                gov_level=info["gov_level"],
                state_code=scheme_state,
                benefit_summary=info.get("benefit_summary"),
                source_url=info.get("source_url"),
                label=label,
                readiness=readiness(rule_rows),
                rules=rule_rows,
                blocking=blocking,
                advisory=advisory,
                missing=missing,
                narrative=info.get("narrative"),
                citations=[info["chunk_id"]] if info.get("chunk_id") else [],
            )
        )

    results.sort(key=lambda item: (
        CATEGORY_ORDER.get(item.label.lower(), 9),
        -item.readiness,
        distance.get(item.scheme_id, 1.0),
    ))
    return results, filtered


def _to_rule(row: Dict[str, Any]) -> RuleRow:
    return RuleRow(
        scheme_id=row["scheme_id"],
        rule_id=int(row["rule_id"]),
        criterion_code=row["criterion_code"],
        rule_op=row["rule_op"],
        mandatory=int(row["mandatory"]),
        observed_value=row.get("observed_value"),
        verdict=row["verdict"],
        clause_ref=row["clause_ref"],
        chunk_id=row.get("chunk_id"),
        narrative=row.get("narrative"),
        chunk_text=row.get("chunk_text"),
        value_num=row.get("value_num"),
        value_text=row.get("value_text"),
    )


def _explain_context(item: SchemeResult, state: AgentState) -> Dict[str, Any]:
    clauses: List[Dict[str, Any]] = []
    seen = set()
    for chunk in state.get("retrieved", []):
        if chunk["scheme_id"] != item.scheme_id or chunk["chunk_id"] in seen:
            continue
        seen.add(chunk["chunk_id"])
        clauses.append({
            "chunk_id": chunk["chunk_id"],
            "clause_ref": chunk["clause_ref"],
            "text": chunk.get("chunk_text") or "",
        })
        if len(clauses) >= 3:
            break
    if not clauses:
        for rule in item.rules:
            if rule.chunk_id and rule.chunk_id not in seen:
                seen.add(rule.chunk_id)
                clauses.append({
                    "chunk_id": rule.chunk_id,
                    "clause_ref": rule.clause_ref,
                    "text": rule.chunk_text or "",
                })
        clauses = clauses[:3]

    return {
        "scheme_id": item.scheme_id,
        "name": item.name,
        "label": item.label,
        "benefit_summary": item.benefit_summary or "",
        "rules": [
            {
                "scheme_id": r.scheme_id,
                "rule_id": r.rule_id,
                "criterion_code": r.criterion_code,
                "verdict": r.verdict,
                "mandatory": r.mandatory,
                "observed_value": r.observed_value,
                "threshold": r.threshold_label(),
                "rule_op": r.rule_op,
                "clause_ref": r.clause_ref,
                "value_num": r.value_num,
                "value_text": r.value_text,
            }
            for r in item.rules
        ],
        "clauses": clauses,
    }


def _route_after_normalize(state: AgentState) -> str:
    return "persist_facts" if state.get("facts") else "clarify"


# ---------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------
NODES = {
    "begin": node_begin,
    "normalize": node_normalize,
    "persist_facts": node_persist_facts,
    "retrieve": node_retrieve,
    "record_trace": node_record_trace,
    "explain": node_explain,
    "clarify": node_clarify,
    "finalize": node_finalize,
}


def build_graph():
    if not HAS_LANGGRAPH:
        return None
    graph = StateGraph(AgentState)
    for name, func in NODES.items():
        graph.add_node(name, func)
    graph.set_entry_point("begin")
    graph.add_edge("begin", "normalize")
    graph.add_conditional_edges(
        "normalize", _route_after_normalize,
        {"persist_facts": "persist_facts", "clarify": "clarify"},
    )
    graph.add_edge("persist_facts", "retrieve")
    graph.add_edge("retrieve", "record_trace")
    graph.add_edge("record_trace", "explain")
    graph.add_edge("explain", "finalize")
    graph.add_edge("clarify", END)
    graph.add_edge("finalize", END)
    return graph.compile()


APP = build_graph()

SEQUENTIAL = ["begin", "normalize"]
SEQUENTIAL_TAIL = ["retrieve", "record_trace", "explain", "finalize"]


def _run_sequential(state: AgentState) -> AgentState:
    for name in SEQUENTIAL:
        state.update(NODES[name](state))
    route = _route_after_normalize(state)
    if route == "clarify":
        state.update(NODES["clarify"](state))
        return state
    state.update(NODES["persist_facts"](state))
    for name in SEQUENTIAL_TAIL:
        state.update(NODES[name](state))
    return state


def run(raw_text: str, category: Optional[str] = None) -> Dict[str, Any]:
    run_id = uuid.uuid4().hex
    state: AgentState = {
        "run_id": run_id,
        "profile_id": f"profile-{run_id[:12]}",
        "raw_text": raw_text.strip(),
        "category": category,
        "facts": {},
        "notes": [],
        "retrieved": [],
        "results": [],
        "counts": {},
        "filtered_by_residency": 0,
        "t0": time.time(),  # type: ignore[typeddict-unknown-key]
    }
    try:
        if APP is not None:
            final = APP.invoke(state)
        else:  # pragma: no cover
            final = _run_sequential(state)
    except Exception as exc:
        _mark_failed(state, exc)
        raise

    final["duration_ms"] = int((time.time() - state["t0"]) * 1000)  # type: ignore[index]
    final["engine"] = "langgraph" if APP is not None else "sequential"
    return final


def _mark_failed(state: AgentState, exc: Exception) -> None:
    try:
        with db.connect() as conn:
            db.finish_run(conn, state["run_id"], "FAILED", _elapsed(state), 0,
                          json.dumps({"error": str(exc)[:500]}))
            db.audit(conn, state["run_id"], "agent", "run.failed", str(exc)[:1500])
    except Exception:  # pragma: no cover - never mask the original error
        pass
