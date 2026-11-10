"""CrewAI collaborative analysis for an existing cold-chain incident.

LangGraph calls this after the deterministic risk assessment. The crew explains
the incident and suggests actions. It does not insert incidents, risk
assessments, or recommendations. The numeric risk score in workflow state is
left unchanged.

When no LLM credential is configured, or the provider call fails, a fallback
is built only from values already present in the workflow state.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SuggestedAction(BaseModel):
    action: str
    justification: str
    priority: int = Field(ge=1, le=3)


class CrewFindings(BaseModel):
    summary: str
    risk_analyst: str
    domain_expert: str
    recommendation_specialist: str
    potential_product_damage: str
    possible_causes: List[str]
    containment_measures: List[str]
    suggested_actions: List[SuggestedAction]


def _text(value: Any, default: str = "unknown") -> str:
    if value is None or value == "":
        return default
    return str(value)


def _context_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    product = state.get("product") if isinstance(state.get("product"), dict) else {}
    shipment = state.get("shipment") if isinstance(state.get("shipment"), dict) else {}
    sensor = state.get("sensor") if isinstance(state.get("sensor"), dict) else {}
    sensitivity = product.get("sensitivity") or product.get("sensitivity_level")
    return {
        "incident_id": state.get("incident_id"),
        "severity": state.get("severity"),
        "risk_assessment_id": state.get("risk_assessment_id"),
        "deterministic_risk_score": state.get("risk_score"),
        "deterministic_risk_level": state.get("risk_level"),
        "deterministic_explanation": state.get("risk_explanation"),
        "temperature_deviation": state.get("temperature_deviation"),
        "temperature_status": state.get("temperature_status"),
        "product_name": product.get("product_name"),
        "product_category": product.get("product_category"),
        "sensitivity": sensitivity,
        "min_temperature": product.get("min_temperature"),
        "max_temperature": product.get("max_temperature"),
        "shipment_id": shipment.get("shipment_id") or sensor.get("shipment_id"),
        "vehicle_id": shipment.get("vehicle_id"),
        "source_location": shipment.get("source_location"),
        "destination_location": shipment.get("destination_location"),
        "shipment_status": shipment.get("shipment_status"),
        "reading_id": sensor.get("reading_id") or state.get("reading_id"),
        "temperature": sensor.get("temperature"),
        "humidity": sensor.get("humidity"),
        "recorded_at": sensor.get("recorded_at"),
    }


def build_fallback_analysis(state: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Explain the incident from stored workflow facts when CrewAI cannot run."""
    ctx = _context_payload(state)
    deviation = ctx["temperature_deviation"]
    sensitivity = _text(ctx["sensitivity"])
    level = _text(ctx["deterministic_risk_level"])
    score = _text(ctx["deterministic_risk_score"])
    product = _text(ctx["product_name"], "the product")
    summary = (
        f"Deterministic risk score {score} ({level}) remains the authoritative score. "
        f"{product} sensitivity is {sensitivity} and the temperature deviation is {deviation}°C."
    )
    risk_analyst = (
        f"The monitoring result is {_text(ctx['temperature_status'])}. "
        f"Severity is {_text(ctx['severity'])}. "
        f"Stored explanation: {_text(ctx['deterministic_explanation'], 'not available')}."
    )
    domain_expert = (
        f"Permitted range is {_text(ctx['min_temperature'])}°C to {_text(ctx['max_temperature'])}°C. "
        f"Observed temperature is {_text(ctx['temperature'])}°C on reading {_text(ctx['reading_id'])}. "
        "Likely operational causes include refrigeration drift, a door-open event, or a sensor fault. "
        "Confirm the cause from the vehicle log before moving the shipment."
    )
    specialist = (
        "Corrective actions below are suggestions for a human reviewer. "
        "They are not approved and are not new database recommendations."
    )
    actions = [
        {
            "action": "Inspect refrigeration equipment",
            "justification": "The reading is outside the permitted product range.",
            "priority": 1,
        },
        {
            "action": "Contact logistics operator",
            "justification": "The operator must confirm containment while the shipment is still moving.",
            "priority": 2,
        },
    ]
    if str(ctx["severity"]).upper() in {"HIGH", "CRITICAL"} or level in {"HIGH", "CRITICAL"}:
        actions.append(
            {
                "action": "Quarantine shipment pending expert assessment",
                "justification": "The deterministic risk level is elevated.",
                "priority": 1,
            }
        )
    return {
        "source": "deterministic_fallback",
        "available": False,
        "reused": False,
        "summary": summary,
        "risk_analyst": risk_analyst,
        "domain_expert": domain_expert,
        "recommendation_specialist": specialist,
        "potential_product_damage": (
            f"{product} may be damaged if the {deviation}°C excursion continues "
            f"outside {_text(ctx['min_temperature'])}°C to {_text(ctx['max_temperature'])}°C."
        ),
        "possible_causes": [
            "Refrigeration equipment drift",
            "Door left open during handling",
            "Sensor calibration or placement fault",
        ],
        "containment_measures": [
            "Restore the shipment to the permitted temperature range",
            "Hold the product for quality review before release",
        ],
        "suggested_actions": actions,
        "message": reason,
        "deterministic_risk_score": ctx["deterministic_risk_score"],
        "deterministic_risk_level": ctx["deterministic_risk_level"],
    }


def _llm():
    """Build a CrewAI LLM from environment variables, or return None.

    Returns None when CrewAI is unavailable, no credential is configured, or the
    provider client cannot be constructed (missing SDK, malformed proxy, invalid
    key), so the caller falls back to deterministic analysis instead of failing.
    """
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    crew_key = os.getenv("CREWAI_API_KEY")
    configured_model = (os.getenv("CREWAI_MODEL") or os.getenv("GEMINI_MODEL") or "").strip()

    try:
        from crewai import LLM
    except Exception:
        return None

    try:
        if gemini_key:
            model_name = configured_model or "gemini/gemini-2.0-flash"
            if "/" not in model_name:
                model_name = f"gemini/{model_name}"
            return LLM(model=model_name, api_key=gemini_key, temperature=0.2)

        if openai_key or (crew_key and (not configured_model or configured_model.startswith(("openai/", "gpt")))):
            model_name = configured_model or "openai/gpt-4o-mini"
            if "/" not in model_name:
                model_name = f"openai/{model_name}"
            return LLM(model=model_name, api_key=openai_key or crew_key, temperature=0.2)

        if crew_key and configured_model:
            return LLM(model=configured_model, api_key=crew_key, temperature=0.2)
    except Exception:
        return None

    return None


def _load_stored_analysis(incident_id: int) -> Optional[Dict[str, Any]]:
    from app.database.db import execute_query_one

    row = execute_query_one(
        """
        SELECT DETAILS
        FROM AUDIT_LOGS
        WHERE INCIDENT_ID = ?
          AND AGENT_NAME = 'CrewAI'
          AND ACTION_TAKEN = 'crew_analysis'
        ORDER BY TIMESTAMP DESC
        FETCH FIRST 1 ROW ONLY
        """,
        (incident_id,),
    )
    if not row or not row.get("details"):
        return None
    try:
        parsed = json.loads(row["details"])
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    parsed["reused"] = True
    parsed["source"] = parsed.get("source") or "crewai"
    return parsed


def _store_analysis(incident_id: int, analysis: Dict[str, Any]) -> None:
    from app.database.audit import log_action

    payload = json.dumps(analysis, default=str)
    if len(payload) > 30000:
        payload = payload[:30000]
    log_action(
        agent_name="CrewAI",
        action_taken="crew_analysis",
        details=payload,
        incident_id=incident_id,
    )


def _findings_from_result(result: Any) -> Dict[str, Any]:
    pydantic_obj = getattr(result, "pydantic", None)
    if pydantic_obj is not None:
        if hasattr(pydantic_obj, "model_dump"):
            return pydantic_obj.model_dump()
        return dict(pydantic_obj)

    json_dict = getattr(result, "json_dict", None)
    if isinstance(json_dict, dict) and json_dict:
        return json_dict

    raw = getattr(result, "raw", None)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {
                "summary": raw.strip(),
                "risk_analyst": "",
                "domain_expert": "",
                "recommendation_specialist": "",
                "potential_product_damage": "",
                "possible_causes": [],
                "containment_measures": [],
                "suggested_actions": [],
            }
    return {}


def _run_crew(state: Dict[str, Any], llm: Any) -> Dict[str, Any]:
    from crewai import Agent, Crew, Process, Task

    context_json = json.dumps(_context_payload(state), default=str)
    shared_rules = (
        "Use only the JSON facts provided. Do not invent sensor readings, shipment ids, "
        "or database records. Do not change the deterministic risk score. "
        "Do not say a recommendation is approved. Suggested actions need human approval."
    )

    risk_analyst = Agent(
        role="Cold Chain Risk Analyst",
        goal="Explain temperature-deviation risk using the supplied incident facts.",
        backstory=(
            "You analyze cold-chain temperature excursions, product sensitivity, "
            "incident severity, and the authoritative deterministic risk score."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )
    domain_expert = Agent(
        role="Cold Chain Domain Expert",
        goal="Interpret temperature requirements and practical containment options.",
        backstory=(
            "You know pharmaceutical and perishable cold-chain handling, permitted "
            "temperature ranges, excursion causes, and containment measures."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )
    specialist = Agent(
        role="Recommendation Specialist",
        goal="Turn the other agents' findings into prioritized corrective actions.",
        backstory=(
            "You write practical corrective actions with clear justifications. "
            "A person must approve every action before it is carried out."
        ),
        llm=llm,
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )

    risk_task = Task(
        description=(
            f"{shared_rules}\nIncident facts:\n{context_json}\n"
            "Analyze the temperature deviation, product sensitivity, severity, "
            "and deterministic risk score. Explain potential product damage."
        ),
        expected_output="A concise risk analysis grounded in the supplied facts.",
        agent=risk_analyst,
    )
    domain_task = Task(
        description=(
            f"{shared_rules}\nUsing the risk analysis and these facts:\n{context_json}\n"
            "Evaluate cold-chain conditions, interpret the permitted range, "
            "identify possible excursion causes, and suggest containment measures."
        ),
        expected_output="Causes and containment measures grounded in the supplied facts.",
        agent=domain_expert,
        context=[risk_task],
    )
    recommendation_task = Task(
        description=(
            f"{shared_rules}\nReview the previous findings and these facts:\n{context_json}\n"
            "Produce the structured findings. Keep the deterministic score unchanged. "
            "Prioritize suggested actions from 1 (highest) to 3."
        ),
        expected_output="Structured findings with a summary and prioritized suggested actions.",
        agent=specialist,
        context=[risk_task, domain_task],
        output_pydantic=CrewFindings,
    )

    crew = Crew(
        agents=[risk_analyst, domain_expert, specialist],
        tasks=[risk_task, domain_task, recommendation_task],
        process=Process.sequential,
        verbose=False,
    )
    result = crew.kickoff()
    findings = _findings_from_result(result)
    if not findings.get("summary"):
        raise RuntimeError("CrewAI returned an empty analysis.")

    tasks_output = getattr(result, "tasks_output", None) or []
    if len(tasks_output) >= 1 and not findings.get("risk_analyst"):
        findings["risk_analyst"] = getattr(tasks_output[0], "raw", "") or ""
    if len(tasks_output) >= 2 and not findings.get("domain_expert"):
        findings["domain_expert"] = getattr(tasks_output[1], "raw", "") or ""
    if len(tasks_output) >= 3 and not findings.get("recommendation_specialist"):
        findings["recommendation_specialist"] = getattr(tasks_output[2], "raw", "") or ""

    findings["source"] = "crewai"
    findings["available"] = True
    findings["reused"] = False
    findings["message"] = None
    findings["deterministic_risk_score"] = state.get("risk_score")
    findings["deterministic_risk_level"] = state.get("risk_level")
    return findings


def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """Attach CrewAI reasoning without changing the deterministic risk score."""
    original_score = state.get("risk_score")
    original_level = state.get("risk_level")
    original_explanation = state.get("risk_explanation")
    original_assessment_id = state.get("risk_assessment_id")
    incident_id = state.get("incident_id")

    analysis: Optional[Dict[str, Any]] = None
    if isinstance(incident_id, int) and incident_id > 0:
        try:
            analysis = _load_stored_analysis(incident_id)
        except Exception:
            analysis = None

    if analysis is None:
        llm = _llm()
        if llm is None:
            analysis = build_fallback_analysis(
                state,
                "CrewAI model credentials are not configured. Set GEMINI_API_KEY, OPENAI_API_KEY, or CREWAI_API_KEY.",
            )
        else:
            try:
                analysis = _run_crew(state, llm)
                if isinstance(incident_id, int) and incident_id > 0:
                    _store_analysis(incident_id, analysis)
            except Exception as exc:
                analysis = build_fallback_analysis(state, f"CrewAI request failed: {exc}")

    state["crew_analysis"] = analysis
    state["crew_status"] = "SUCCESS" if analysis.get("source") == "crewai" else "FALLBACK"
    # Deterministic business fields stay authoritative even if a model echoed other numbers.
    state["risk_score"] = original_score
    state["risk_level"] = original_level
    state["risk_explanation"] = original_explanation
    state["risk_assessment_id"] = original_assessment_id
    return state
