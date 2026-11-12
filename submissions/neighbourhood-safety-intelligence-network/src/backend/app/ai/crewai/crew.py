"""Multi-agent incident briefing: a CrewAI Crew running IBM Granite locally through Ollama.

Agents
  * Triage Analyst   - summarises the report and the risk in plain language.
  * Protocol Advisor - turns the approved protocols into numbered next actions, citing them. It has
                       a CrewAI tool that searches the protocol passages stored in IBM Db2
                       (Haystack hybrid search: BM25 + Db2 VECTOR_DISTANCE).

Trust rules
  * The rule-based triage priority stays authoritative; the crew only explains and advises.
  * Retrieved passages are placed in the task context (RAG), and the answer is checked: it must cite
    at least one retrieved protocol title, otherwise it is marked ungrounded.
  * Everything runs on the local Ollama server, so resident text never leaves the machine.
"""
import os
import time
from typing import Any, Dict, List, Optional, Type

os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import LLM, Agent, Crew, Process, Task  # noqa: E402
from crewai.tools import BaseTool  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.app.ai.haystack.rag_pipeline import retrieve_safety_guidance  # noqa: E402
from backend.app.core.config import settings  # noqa: E402


class ProtocolSearchInput(BaseModel):
    query: str = Field(..., description="What to look up, e.g. 'elderly person not answering phone'")


class Db2ProtocolSearchTool(BaseTool):
    """CrewAI tool backed by the Haystack hybrid pipeline over IBM Db2."""
    name: str = "db2_protocol_search"
    description: str = ("Search the approved neighbourhood safety protocols stored in IBM Db2. "
                        "Returns the best matching protocol titles with the exact passage that matched.")
    args_schema: Type[BaseModel] = ProtocolSearchInput

    def _run(self, query: str) -> str:
        return format_protocols(retrieve_safety_guidance(query)["results"])


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
        llm=llm, tools=[Db2ProtocolSearchTool()], allow_delegation=False, verbose=False, max_iter=3,
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
                     "(use the db2_protocol_search tool if you need more). End with 'Source:' and the protocol title you used."),
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
