"""Multi-agent incident briefing: a CrewAI Crew running IBM Granite locally through Ollama.

Agents
  * Triage Analyst   - summarises the report and the risk in plain language.
  * Protocol Advisor - turns the approved protocols into numbered next actions, citing them. It uses
                       IBM's DB2VectorSearchTool (crewai-tools) over the protocol passages in Db2.

Trust rules
  * The rule-based triage priority stays authoritative; the crew only explains and advises.
  * Retrieved passages are placed in the task context (RAG), and the answer is checked: it must cite
    at least one retrieved protocol title, otherwise it is marked ungrounded.
  * Everything runs on the local Ollama server, so resident text never leaves the machine.
"""
import os
import time
from typing import Any, Dict, List, Optional

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402

from backend.app.ai.haystack.rag_pipeline import retrieve_safety_guidance  # noqa: E402
from backend.app.core.config import settings  # noqa: E402


def granite_embedding(text: str) -> List[float]:
    """IBM Granite embedding through the local Ollama server (used by IBM's Db2 CrewAI tool)."""
    import ollama
    client = ollama.Client(host=settings.OLLAMA_HOST, timeout=settings.LLM_TIMEOUT_SECONDS)
    return list(client.embed(model=settings.OLLAMA_EMBED_MODEL, input=[text]).embeddings[0])


def protocol_search_tool():
    """IBM's `DB2VectorSearchTool` (crewai-tools) over the protocol passages stored in Db2, with
    Granite embeddings instead of the tool's default OpenAI ones, and the calibrated distance cutoff."""
    from crewai_tools import DB2VectorSearchTool

    from backend.app.ai.haystack.rag_pipeline import MAX_DISTANCE, PASSAGE_TABLE
    from backend.app.database.db2_adapter import Db2Adapter

    table = f"{settings.DB2_SCHEMA}.{PASSAGE_TABLE}" if settings.DB2_SCHEMA else PASSAGE_TABLE
    return DB2VectorSearchTool(
        connection_string=Db2Adapter().build_connection_string(),
        table_name=table, vector_column="embedding", return_columns=["content"],
        limit=3, distance_metric="COSINE", max_distance=MAX_DISTANCE,
        custom_embedding_fn=granite_embedding,
        description="Search the approved neighbourhood safety protocols stored in IBM Db2 (vector search).",
    )


def format_protocols(results: List[Dict[str, Any]]) -> str:
    if not results:
        return "No approved protocol matched."
    return "\n".join(f"[{i}] {r['title']} ({r['source']}): {r.get('cited_passage') or r['excerpt'][:300]}"
                     for i, r in enumerate(results, start=1))


def granite_llm() -> LLM:
    return LLM(model=f"ollama/{settings.OLLAMA_CHAT_MODEL}", base_url=settings.OLLAMA_HOST,
               temperature=0.1, timeout=settings.LLM_TIMEOUT_SECONDS)


def build_crew(report: str, triage: Dict[str, Any], protocols: List[Dict[str, Any]]) -> Crew:
    llm = granite_llm()
    analyst = Agent(
        role="Triage Analyst",
        goal="Explain an incident report and its risk to a volunteer responder in plain words.",
        backstory="You work in a neighbourhood safety control room. You are calm, factual and brief, "
                  "and you never invent details that are not in the report.",
        llm=llm, allow_delegation=False, verbose=False, max_iter=2,
    )
    advisor = Agent(
        role="Protocol Advisor",
        goal="Give responders the next actions from the approved safety protocols only, citing them.",
        backstory="You know the neighbourhood's approved safety protocols, which are stored in IBM Db2. "
                  "You only recommend actions those protocols support, and you name the protocol you used.",
        llm=llm, tools=[protocol_search_tool()], allow_delegation=False, verbose=False, max_iter=3,
    )
    summary = Task(
        description=(f"Incident report: \"{report}\"\n"
                     f"Rule-based triage: category {triage['parsed_category']}, priority {triage['suggested_priority']}. "
                     f"Reasoning: {triage['triage_reasoning']}\n"
                     "Write 2 short sentences: what happened and why it matters. Do not change the priority."),
        expected_output="Two sentences, plain English.",
        agent=analyst,
    )
    advice = Task(
        description=("Approved protocol passages retrieved from IBM Db2:\n"
                     f"{format_protocols(protocols)}\n\n"
                     "Write exactly 3 numbered next actions for the responder, based only on these protocols "
                     "(use the Db2 vector search tool if you need more). End with 'Source:' and the protocol title you used."),
        expected_output="Three numbered actions followed by a 'Source:' line naming a protocol title.",
        agent=advisor,
        context=[summary],
    )
    return Crew(agents=[analyst, advisor], tasks=[summary, advice], process=Process.sequential, verbose=False)


def is_grounded(text: str, protocols: List[Dict[str, Any]]) -> bool:
    lowered = text.lower()
    return any(p["title"].lower() in lowered for p in protocols)


def run_briefing(report: str, triage: Dict[str, Any], protocols: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Run the crew. Raises on LLM/Ollama failure so the API can degrade to the rule-based result."""
    protocols = protocols if protocols is not None else retrieve_safety_guidance(
        report, incident_type=triage["parsed_category"])["results"]
    started = time.time()
    crew = build_crew(report, triage, protocols)
    result = crew.kickoff()
    summary_text = (crew.tasks[0].output.raw if crew.tasks[0].output else "").strip()
    advice_text = (result.raw or "").strip()
    return {
        "summary": summary_text,
        "advice": advice_text,
        "grounded": is_grounded(advice_text, protocols),
        "cited_protocols": [p["title"] for p in protocols],
        "model": settings.OLLAMA_CHAT_MODEL,
        "agents": [a.role for a in crew.agents],
        "duration_sec": round(time.time() - started, 2),
    }
