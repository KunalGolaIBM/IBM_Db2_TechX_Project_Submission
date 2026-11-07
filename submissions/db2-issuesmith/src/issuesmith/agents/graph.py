"""IssueSmith agent graph (LangGraph).

sanitizer -> triage -> retriever -> deduplicator -> writer -> critic --(fail, rounds left)--> writer
                                                                  \\--(pass or out of rounds)--> publisher

Every node is timed and logged to Db2 (AGENT_RUNS), and every intermediate
artefact (incident, evidence, embedding, draft per round) is stored in Db2.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TypedDict

from langchain_core.embeddings import Embeddings
from langgraph.graph import END, StateGraph

from .. import critic as critic_mod
from .. import issue_writer
from ..github_client import keywords_from
from ..llm import BaseLLM
from ..log_parser import build_signature, classify, extract_environment, extract_evidence
from ..sanitizer import sanitize

log = logging.getLogger(__name__)


class IssueState(TypedDict, total=False):
    # inputs
    raw_log: str
    source_name: str
    user_steps: str
    reproducibility: str
    # produced by agents
    incident_id: int
    sanitized_log: str
    redactions: dict
    redaction_count: int
    category: str
    confidence: float
    environment: dict
    evidence: list[dict]
    signature: str
    kb_context: list[dict]
    similar: list[dict]
    github_matches: list[dict]
    duplicate_of: int | None
    narrative: dict
    title: str
    body: str
    generated_by: str
    critic: dict
    round: int
    trace: list[dict]


@dataclass
class Services:
    repo: Any                     # Db2Repository (or a test double with the same methods)
    embeddings: Embeddings
    llm: BaseLLM
    kb: Any = None                # KnowledgeBase or None
    github_search: Callable[[list[str]], list[dict]] | None = None
    max_rounds: int = 2
    duplicate_distance: float = 0.12
    trace_sink: list = field(default_factory=list)


def _timed(services: Services, agent: str, fn: Callable[[IssueState], dict]) -> Callable[[IssueState], dict]:
    def wrapper(state: IssueState) -> dict:
        t0 = time.perf_counter()
        status, detail, update = "OK", "", {}
        try:
            update = fn(state) or {}
            detail = update.pop("_detail", "")
        except Exception as exc:
            status, detail = "ERROR", f"{type(exc).__name__}: {exc}"
            log.exception("Agent %s failed", agent)
            raise
        finally:
            ms = int((time.perf_counter() - t0) * 1000)
            incident_id = update.get("incident_id") or state.get("incident_id")
            try:
                services.repo.log_agent_run(incident_id, agent, status, detail, ms)
            except Exception as log_exc:  # auditing must never break the pipeline
                log.warning("Could not log agent run: %s", log_exc)
            entry = {"agent": agent, "status": status, "detail": detail, "ms": ms}
            services.trace_sink.append(entry)
        update["trace"] = list(state.get("trace", [])) + [entry]
        return update

    return wrapper


def build_graph(services: Services):
    repo, emb, llm = services.repo, services.embeddings, services.llm

    # 1. Sanitizer: deterministic redaction BEFORE anything is stored or sent to a model.
    def sanitizer(state: IssueState) -> dict:
        result = sanitize(state["raw_log"])
        incident_id = repo.create_incident(state.get("source_name", "pasted-log"), result.text, result.total)
        kinds = ", ".join(f"{k}={v}" for k, v in sorted(result.counts.items())) or "nothing sensitive found"
        return {
            "incident_id": incident_id,
            "sanitized_log": result.text,
            "redactions": result.counts,
            "redaction_count": result.total,
            "round": 0,
            "_detail": f"incident #{incident_id}; redacted {result.total} value(s): {kinds}",
        }

    # 2. Triage: evidence extraction, environment, classification, embedding stored as Db2 VECTOR.
    def triage(state: IssueState) -> dict:
        text = state["sanitized_log"]
        found = extract_evidence(text)
        evidence = [e.as_dict() for e in found]
        env = extract_environment(text)
        category, confidence = classify(found)
        signature = build_signature(category, found)
        vector = emb.embed_query(signature)
        repo.update_classification(state["incident_id"], category, confidence, env, signature, vector)
        repo.add_evidence(state["incident_id"], evidence)
        return {
            "category": category, "confidence": confidence, "environment": env,
            "evidence": evidence, "signature": signature,
            "_detail": f"{category} ({confidence:.0%}); {len(evidence)} evidence line(s); {len(env)} env field(s)",
        }

    # 3. Retriever: knowledge base (DB2VS vector search) + existing GitHub issues.
    def retriever(state: IssueState) -> dict:
        query = state["signature"]
        kb = services.kb.search(query, k=3) if services.kb is not None else []
        gh: list[dict] = []
        if services.github_search is not None:
            labels = " ".join(e["label"] for e in state["evidence"] if e["kind"] != "OBSERVATION")
            gh = services.github_search(keywords_from(labels, limit=4))
        return {"kb_context": kb, "github_matches": gh,
                "_detail": f"{len(kb)} knowledge doc(s) from Db2, {len(gh)} GitHub match(es)"}

    # 4. Deduplicator: Db2 stored procedure FIND_SIMILAR_INCIDENTS (VECTOR_DISTANCE, COSINE).
    def deduplicator(state: IssueState) -> dict:
        similar = repo.find_similar(state["incident_id"])
        dup = None
        if similar and similar[0]["DISTANCE"] <= services.duplicate_distance and similar[0]["CATEGORY"] == state["category"]:
            dup = int(similar[0]["INCIDENT_ID"])
            repo.set_status(state["incident_id"], "DUPLICATE", dup)
        best = f"closest #{similar[0]['INCIDENT_ID']} at {similar[0]['DISTANCE']:.3f}" if similar else "no earlier incidents"
        return {"similar": similar, "duplicate_of": dup,
                "_detail": f"{best}" + (f"; flagged as duplicate of #{dup}" if dup else "")}

    # 5. Writer: LLM narrative (or rule-based fallback) + deterministic facts.
    def writer(state: IssueState) -> dict:
        rnd = state.get("round", 0) + 1
        feedback = state.get("critic", {}).get("feedback", []) if rnd > 1 else []
        narrative, by = issue_writer.write_narrative(
            llm, state["category"], state["evidence"], state["environment"], state.get("kb_context", []),
            state.get("user_steps", ""), feedback,
        )
        user_steps = [s.strip(" -*0123456789.)") for s in state.get("user_steps", "").splitlines() if s.strip()]
        steps = user_steps or issue_writer.DEFAULT_STEPS.get(state["category"], [
            "Open the environment shown above.", "Repeat the action that produced the log.",
            "Review the Db2 Extension output channel."])
        title, body = issue_writer.render_issue(
            narrative, state["environment"], state["evidence"], steps, not user_steps,
            state.get("reproducibility", ""), state.get("similar", []), state.get("github_matches", []),
            state.get("redaction_count", 0), state["incident_id"],
        )
        return {"narrative": narrative, "title": title, "body": body, "generated_by": by, "round": rnd,
                "_detail": f"round {rnd} by {by}" + (f" (LLM error: {narrative['_llm_error']})" if "_llm_error" in narrative else "")}

    # 6. Critic: checklist + evidence-boundary + secret scan; every round is saved in Db2.
    def critic(state: IssueState) -> dict:
        verdict = critic_mod.review(state["title"], state["body"], state["narrative"],
                                    state["sanitized_log"], state["environment"])
        final = verdict["passed"] or state["round"] >= services.max_rounds
        repo.save_draft(state["incident_id"], state["round"], state["title"], state["body"], verdict["score"],
                        verdict, state["generated_by"], is_final=final)
        status = "passed" if verdict["passed"] else "failed: " + "; ".join(verdict["feedback"])
        return {"critic": verdict, "_detail": f"score {verdict['score']:.0f}/100, {status}"}

    def route_after_critic(state: IssueState) -> str:
        if state["critic"]["passed"] or state["round"] >= services.max_rounds:
            return "publisher"
        return "writer"

    # 7. Publisher: finalise status (posting to GitHub happens only after human approval in the UI).
    def publisher(state: IssueState) -> dict:
        if not state.get("duplicate_of"):
            repo.set_status(state["incident_id"], "DRAFTED")
        return {"_detail": "draft ready for human review" + (
            f" (possible duplicate of #{state['duplicate_of']})" if state.get("duplicate_of") else "")}

    g = StateGraph(IssueState)
    for name, fn in [("sanitizer", sanitizer), ("triage", triage), ("retriever", retriever),
                     ("deduplicator", deduplicator), ("writer", writer), ("critic", critic),
                     ("publisher", publisher)]:
        g.add_node(name, _timed(services, name, fn))
    g.set_entry_point("sanitizer")
    g.add_edge("sanitizer", "triage")
    g.add_edge("triage", "retriever")
    g.add_edge("retriever", "deduplicator")
    g.add_edge("deduplicator", "writer")
    g.add_edge("writer", "critic")
    g.add_conditional_edges("critic", route_after_critic, {"writer": "writer", "publisher": "publisher"})
    g.add_edge("publisher", END)
    return g.compile()


def run_pipeline(services: Services, raw_log: str, source_name: str = "pasted-log",
                 user_steps: str = "", reproducibility: str = "") -> IssueState:
    graph = build_graph(services)
    return graph.invoke({"raw_log": raw_log, "source_name": source_name, "user_steps": user_steps,
                         "reproducibility": reproducibility, "trace": []})
