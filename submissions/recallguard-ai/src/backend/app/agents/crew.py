"""CrewAI integration — five specialised agents with Db2-backed tools.

Division of labour (anti-hallucination by construction):
  * Facts (IDs, quantities, locations, risk factors) come from the deterministic
    Db2 functions in deterministic.py, exposed to the agents as CrewAI tools and
    injected as structured JSON context.
  * Each CrewAI agent returns a Pydantic-validated narrative (output_pydantic).
  * The narrative is merged into the fact model; the Verification Agent then
    checks every identifier mentioned anywhere against Db2.

Requires LLM_PROVIDER + LLM_MODEL + the provider key. Without them the
orchestrator uses the DETERMINISTIC_FALLBACK mode and says so.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Type

from pydantic import BaseModel, Field

from app.core.config import Settings
from app.database import Database

log = logging.getLogger("recallguard.crew")


# ------------------------------------------------------------- narrative outputs
class InvestigationNarrative(BaseModel):
    summary: str = Field(description="2-4 sentence summary grounded ONLY in the provided facts")
    hypothesis: str = Field(description="Most likely contamination pathway, citing evidence by filename and page")
    open_questions: list[str] = Field(default_factory=list)


class SupplyChainNarrative(BaseModel):
    summary: str
    notable_gaps: list[str] = Field(default_factory=list)


class RiskNarrative(BaseModel):
    narrative: str = Field(description="Explain the score using ONLY the factor contributions given")


class RecallNarrative(BaseModel):
    summary: str
    retailer_instruction_preamble: str = Field(description="One short paragraph prepended to every simulated notice")


class VerificationNarrative(BaseModel):
    summary: str
    additional_concerns: list[str] = Field(default_factory=list)


NARRATIVES: dict[str, Type[BaseModel]] = {
    "investigation": InvestigationNarrative,
    "supply_chain": SupplyChainNarrative,
    "risk_assessment": RiskNarrative,
    "recall_planning": RecallNarrative,
    "verification": VerificationNarrative,
}

ROLES = {
    "investigation": ("Food Safety Investigation Lead",
                      "Determine the contamination source and what the laboratory evidence actually shows.",
                      "Former public-health microbiologist. Cites document and page for every claim and never infers results not written in a report."),
    "supply_chain": ("Supply Chain Traceability Analyst",
                     "Explain the IBM Db2 genealogy and distribution trace and its gaps.",
                     "Traceability engineer who trusts only Db2 query results and flags every missing record."),
    "risk_assessment": ("Risk Assessment Specialist",
                        "Explain the transparent risk score without changing it.",
                        "Quantitative risk analyst; distinguishes operational prioritisation from probability of illness."),
    "recall_planning": ("Recall Operations Planner",
                        "Communicate a targeted, prioritised recall plan to retailers.",
                        "Has run national recalls; writes short, unambiguous instructions."),
    "verification": ("Independent Verification Auditor",
                     "Challenge the recommendation and surface anything unsupported or missing.",
                     "Sceptical auditor. Never approves anything; only reports issues for the human approver."),
}

RULES = ("RULES: Use ONLY identifiers, quantities and names that appear in the FACTS JSON or in tool results. "
         "Do not invent suppliers, batch IDs, lot IDs, retailers, quantities or lab results. If information is missing, say it is missing.")


def build_llm(settings: Settings):
    from crewai import LLM

    provider, model = settings.llm_provider, settings.llm_model
    kwargs: dict[str, Any] = {"temperature": settings.llm_temperature}
    if provider == "openai":
        kwargs.update(model=f"openai/{model}", api_key=settings.openai_api_key)
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
    elif provider == "anthropic":
        kwargs.update(model=f"anthropic/{model}", api_key=settings.anthropic_api_key)
    elif provider == "gemini":
        kwargs.update(model=f"gemini/{model}", api_key=settings.gemini_api_key)
    elif provider == "watsonx":  # served through LiteLLM (pip install litellm)
        kwargs.update(model=f"watsonx/{model}", api_key=settings.watsonx_apikey, base_url=settings.watsonx_url,
                      project_id=settings.watsonx_project_id)
    elif provider == "ollama":
        kwargs.update(model=f"ollama/{model}", base_url=settings.llm_base_url or "http://localhost:11434")
    else:
        raise ValueError("LLM provider not configured")
    return LLM(**kwargs)


def build_tools(db: Database) -> list:
    """CrewAI tools that query IBM Db2 (or the labelled dev engine)."""
    from crewai.tools import BaseTool

    from app.services import evidence as ev
    from app.services.traceability import impact_analysis

    class TraceArgs(BaseModel):
        source_ref: str = Field(description="Ingredient lot ID (e.g. TOM-2026-041) or production batch ID (e.g. PB-2026-1004)")

    class Db2ImpactTool(BaseTool):
        name: str = "db2_trace_impact"
        description: str = ("Runs the IBM Db2 recursive genealogy + distribution SQL for a lot or batch and returns affected "
                            "batches, products, locations and traceability gaps as JSON.")
        args_schema: Type[BaseModel] = TraceArgs

        def _run(self, source_ref: str) -> str:
            imp = impact_analysis(db, source_ref)
            return json.dumps({"summary": imp["summary"], "batches": [{k: b[k] for k in ("batch_id", "batch_type", "product_id", "relation", "depth")} for b in imp["batches"]],
                               "locations": [{k: l[k] for k in ("loc_kind", "loc_ref", "loc_name", "units_held")} for l in imp["locations"]],
                               "data_gaps": imp["data_gaps"], "engine": imp["engine"]}, default=str)

    class SearchArgs(BaseModel):
        query: str = Field(description="Natural-language question about the evidence documents")

    class EvidenceSearchTool(BaseTool):
        name: str = "evidence_search"
        description: str = "Retrieves evidence chunks (with filename/page citations) from the Db2-backed Evidence Vault."
        args_schema: Type[BaseModel] = SearchArgs

        def _run(self, query: str) -> str:
            res = ev.search(db, query, k=5)
            return json.dumps([{"citation": r["citation"], "text": r["content"][:600]} for r in res["results"]])

    return [Db2ImpactTool(), EvidenceSearchTool()]


class CrewRunner:
    """Runs one CrewAI agent/task per pipeline step so progress can be persisted per agent."""

    def __init__(self, db: Database, settings: Settings, llm: Any = None) -> None:
        self.db, self.settings = db, settings
        self.llm = llm or build_llm(settings)
        self.tools = build_tools(db)

    def build_step(self, step: str, facts: dict[str, Any], shared_context: str):
        from crewai import Agent, Crew, Process, Task

        role, goal, backstory = ROLES[step]
        agent = Agent(role=role, goal=goal, backstory=backstory, llm=self.llm, tools=self.tools,
                      allow_delegation=False, verbose=False, max_iter=4)
        task = Task(
            description=(f"{RULES}\n\nSHARED INVESTIGATION CONTEXT:\n{shared_context}\n\n"
                         f"FACTS (from IBM Db2 queries — authoritative):\n{json.dumps(facts, default=str)[:12000]}\n\n"
                         f"Produce your {step.replace('_', ' ')} output."),
            expected_output=f"JSON matching {NARRATIVES[step].__name__}",
            agent=agent,
            output_pydantic=NARRATIVES[step],
        )
        return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)

    def run_step(self, step: str, facts: dict[str, Any], shared_context: str) -> BaseModel:
        crew = self.build_step(step, facts, shared_context)
        out = crew.kickoff()
        model = getattr(out, "pydantic", None)
        if model is None:
            raw = getattr(out, "raw", str(out))
            model = NARRATIVES[step].model_validate_json(raw)
        return model
