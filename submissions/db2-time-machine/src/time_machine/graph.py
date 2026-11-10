"""LangGraph wiring: Detective -> Historian -> Diff -> Verifier -> (retry | Reporter)."""
from __future__ import annotations

import queue
import threading
from typing import Iterator, Optional

from langgraph.graph import END, START, StateGraph

from .agents import (Context, State, detective, diff, historian, reporter, route_after_verifier, verifier)
from .config import Settings
from .llm import LLM


def build_graph():
    g = StateGraph(State)
    g.add_node("detective", detective)
    g.add_node("historian", historian)
    g.add_node("diff", diff)
    g.add_node("verifier", verifier)
    g.add_node("reporter", reporter)
    g.add_edge(START, "detective")
    g.add_edge("detective", "historian")
    g.add_edge("historian", "diff")
    g.add_edge("diff", "verifier")
    g.add_conditional_edges("verifier", route_after_verifier, {"detective": "detective", "reporter": "reporter"})
    g.add_edge("reporter", END)
    return g.compile()


_GRAPH = None


def graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def investigate(repo, question: str, *, llm: Optional[LLM] = None, settings: Optional[Settings] = None,
                since: Optional[str] = None, until: Optional[str] = None, hours: Optional[float] = None,
                emit=lambda event: None) -> dict:
    """Run one investigation and return the incident report."""
    settings = settings or Settings.from_env()
    llm = llm or LLM.from_settings(settings)
    ctx = Context(repo=repo, llm=llm, settings=settings, emit=emit)
    emit({"type": "start", "run_id": ctx.run_id, "llm": llm.label, "question": question})
    ctx.audit("system", "investigation started", detail={"question": question[:300], "llm": llm.label})
    state = {"run_id": ctx.run_id, "question": question, "since": since, "until": until, "hours": hours}
    result = graph().invoke(state, config={"configurable": {"ctx": ctx},
                                            "recursion_limit": 12 + 5 * settings.max_iterations})
    ctx.audit("system", "investigation finished", detail=f"status={result['report']['verdict']['status']}")
    return result["report"]


def stream_investigation(repo, question: str, **kwargs) -> Iterator[dict]:
    """Yield live events (agent steps, hypotheses, audit rows, final report) from a background run."""
    events: "queue.Queue[Optional[dict]]" = queue.Queue()

    def worker():
        try:
            investigate(repo, question, emit=events.put, **kwargs)
        except Exception as exc:  # surfaced to the UI instead of dying silently
            events.put({"type": "error", "message": f"{type(exc).__name__}: {str(exc)[:300]}"})
        finally:
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()
    while True:
        item = events.get()
        if item is None:
            break
        yield item
