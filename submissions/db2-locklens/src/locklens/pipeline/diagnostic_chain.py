"""LangChain diagnostic pipeline.

    Snapshot -> prepare_input -> apply_rules -> narrative -> finalize -> DiagnosisResult
    (RunnableLambda)  (RunnableLambda)  (RunnablePassthrough.assign)   (RunnableLambda)

What is what, so nothing is mis-described:

* The *findings* are produced by deterministic rules (``services.diagnostic_engine``).
* LangChain composes the stages (``langchain_core`` runnables). The stages are plain,
  independently tested functions.
* An LLM is involved ONLY in the optional narrative step, and only if explicitly requested and
  a local Ollama model is reachable. It receives the already-computed findings, never raw
  credentials. Any failure falls back to the deterministic narrative (``with_fallbacks``).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..config import Settings
from ..models import DiagnosisResult, Finding, Severity, Snapshot
from ..services.diagnostic_engine import Thresholds, evaluate
from ..services.lock_monitor import analyze_snapshot
from .prompts import NARRATIVE_HUMAN, NARRATIVE_SYSTEM

log = logging.getLogger(__name__)

try:  # LangChain is a hard requirement of the project, but fail softly so the UI can explain.
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableLambda, RunnablePassthrough
    LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when the dependency is missing
    LANGCHAIN_AVAILABLE = False

State = dict[str, Any]
DETERMINISTIC = "deterministic-template"


# ---- stage functions (pure, independently testable) -------------------------------------
def prepare_input(payload: State) -> State:
    """Validate the input and compute blocking relationships from the raw snapshot."""
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, Snapshot):
        raise TypeError("payload['snapshot'] must be a Snapshot")
    return {**payload, "analysis": analyze_snapshot(snapshot),
            "thresholds": payload.get("thresholds") or Thresholds()}


def apply_rules(state: State) -> list[Finding]:
    return evaluate(state["snapshot"], state["analysis"], state["thresholds"])


def deterministic_narrative_text(findings: list[Finding]) -> str:
    actionable = [f for f in findings if f.severity >= Severity.WARNING]
    if not actionable:
        top = findings[0] if findings else None
        return top.explanation if top else "No findings."
    lines = [f"{len(actionable)} finding(s) need attention:"]
    for f in actionable[:5]:
        lines.append(f"[{f.severity.name}] {f.title}. {f.recommendations[0] if f.recommendations else ''}".strip())
    return "\n".join(lines)


def deterministic_narrative(state: State) -> dict[str, str]:
    return {"text": deterministic_narrative_text(state["findings"]), "source": DETERMINISTIC}


def build_result(state: State, pipeline: str) -> DiagnosisResult:
    narrative = state.get("narrative") or deterministic_narrative(state)
    return DiagnosisResult(
        findings=state["findings"], analysis=state["analysis"], narrative=narrative["text"],
        narrative_source=narrative["source"], pipeline=pipeline,
        stages=["prepare_input", "apply_rules",
                "llm_narrative" if narrative["source"].startswith("llm:") else "deterministic_narrative",
                "finalize"])


def finalize(state: State) -> DiagnosisResult:
    """Final chain stage (single argument, as RunnableLambda expects)."""
    return build_result(state, "langchain")


def findings_to_json(state: State) -> dict[str, str]:
    payload = [f.to_dict() for f in state["findings"] if f.severity >= Severity.INFO][:12]
    return {"findings_json": json.dumps(payload, ensure_ascii=False, indent=1)}


# ---- optional local model ---------------------------------------------------------------
def build_ollama_model(settings: Settings) -> tuple[Any | None, str]:
    """Return (chat model, '') or (None, reason). Never raises; LLM use is optional."""
    try:
        from langchain_ollama import ChatOllama
    except ImportError:
        return None, "langchain-ollama is not installed (pip install langchain-ollama)"
    try:
        try:
            model = ChatOllama(model=settings.ollama_model, base_url=settings.ollama_url,
                               temperature=0, client_kwargs={"timeout": settings.llm_timeout})
        except Exception:       # older langchain-ollama without client_kwargs
            model = ChatOllama(model=settings.ollama_model, base_url=settings.ollama_url,
                               temperature=0)
        return model, ""
    except Exception as exc:
        return None, f"could not create Ollama client: {exc}"


# ---- chain assembly ---------------------------------------------------------------------
def build_pipeline(llm: Any | None = None, llm_label: str = "llm") -> Any:
    """Assemble the LangChain pipeline. ``llm`` is any LangChain chat model (optional)."""
    if not LANGCHAIN_AVAILABLE:
        raise RuntimeError("langchain-core is not installed. Run: pip install -r requirements.txt")

    if llm is None:
        narrative_step: Any = RunnableLambda(deterministic_narrative)
    else:
        prompt = ChatPromptTemplate.from_messages([("system", NARRATIVE_SYSTEM),
                                                   ("human", NARRATIVE_HUMAN)])
        llm_chain = (RunnableLambda(findings_to_json) | prompt | llm | StrOutputParser()
                     | RunnableLambda(lambda text: {"text": text.strip(), "source": f"llm:{llm_label}"}))
        fallback = RunnableLambda(
            lambda s: {**deterministic_narrative(s), "source": "deterministic-fallback: model call failed"})
        narrative_step = llm_chain.with_fallbacks([fallback])

    return (RunnableLambda(prepare_input)
            | RunnablePassthrough.assign(findings=RunnableLambda(apply_rules))
            | RunnablePassthrough.assign(narrative=narrative_step)
            | RunnableLambda(finalize))


def run_diagnostics(snapshot: Snapshot, settings: Settings, *, use_llm: bool = False,
                    llm: Any | None = None) -> DiagnosisResult:
    """Run the pipeline for ``snapshot``. ``use_llm`` requests the optional local-model narrative."""
    payload: State = {"snapshot": snapshot,
                      "thresholds": Thresholds(settings.wait_warn_seconds, settings.wait_critical_seconds)}
    if not LANGCHAIN_AVAILABLE:
        state = prepare_input(payload)
        state["findings"] = apply_rules(state)
        return build_result(state, "direct (langchain not installed)")

    reason = ""
    model = None
    if use_llm:
        model, reason = (llm, "") if llm is not None else build_ollama_model(settings)
    chain = build_pipeline(model, settings.ollama_model)
    result: DiagnosisResult = chain.invoke(payload)
    if use_llm and model is None:
        result.narrative_source = f"deterministic-fallback: {reason}"
    return result
