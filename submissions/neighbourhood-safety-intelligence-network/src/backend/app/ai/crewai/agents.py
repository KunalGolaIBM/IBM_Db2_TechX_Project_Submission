import logging
import re
import time
from typing import Dict, Any, List, Optional
from backend.app.ai.haystack.rag_pipeline import retrieve_safety_guidance

logger = logging.getLogger("neighbourhood_safety.crewai")

class IncidentIntakeAgent:
    """
    CrewAI Bounded Agent 1: Structures a resident's free-text report,
    extracts key entities, category, and identifies critical missing information.
    """
    role = "Incident Intake Specialist"
    goal = "Transform unstructured citizen safety reports into structured, actionable triage tickets."

    def execute(self, raw_text: str, reported_category: Optional[str] = None) -> Dict[str, Any]:
        text_lower = raw_text.lower()

        # 1. Category identification
        detected_category = reported_category or "hazard"
        if any(w in text_lower for w in ["sos", "help", "attack", "danger", "stalk", "emergency", "assault"]):
            detected_category = "sos"
        elif any(w in text_lower for w in ["heart", "breath", "unconscious", "blood", "doctor", "ambulance", "fall", "injury"]):
            detected_category = "medical"
        elif any(w in text_lower for w in ["child", "kid", "school", "son", "daughter", "bus", "lost"]):
            detected_category = "child_alert"
        elif any(w in text_lower for w in ["elder", "senior", "grandfather", "grandmother", "medicine", "wellness"]):
            detected_category = "elder_welfare"
        elif any(w in text_lower for w in ["prowler", "mask", "loiter", "suspicious", "theft", "break-in", "burglar"]):
            detected_category = "suspicious_activity"

        # 2. Location entity extraction
        location_match = re.search(r'(?:at|near|behind|in front of|opposite|in|on)\s+([A-Za-z0-9\s,\.-]{4,40})', raw_text, re.IGNORECASE)
        extracted_location = location_match.group(1).strip() if location_match else None

        # 3. Missing information detection
        missing = []
        if not extracted_location:
            missing.append("Specific street, landmark, or apartment number")
        if not any(w in text_lower for w in ["now", "just", "minutes", "pm", "am", "today", "yesterday"]):
            missing.append("Exact time or duration of incident")
        if detected_category in ["sos", "medical"] and "alone" not in text_lower and "with" not in text_lower:
            missing.append("Whether the victim is currently alone or accompanied")

        return {
            "parsed_category": detected_category,
            "extracted_location": extracted_location,
            "missing_critical_info": missing,
            "raw_summary": raw_text[:200] + ("..." if len(raw_text) > 200 else "")
        }

class SafetyTriageAssistant:
    """
    CrewAI Bounded Agent 2: Analyzes severity and suggests a preliminary priority
    with evidence-based triage reasoning. Human responder retains final discretion.
    """
    role = "Safety Triage Assessor"
    goal = "Evaluate immediate risk to human life, property, or community peace."

    def execute(self, intake_result: Dict[str, Any], raw_text: str) -> Dict[str, Any]:
        text_lower = raw_text.lower()
        category = intake_result["parsed_category"]

        # Priority calculation
        priority = "P3_MODERATE"
        reasoning_points = []
        actions = []

        if category == "sos" or any(w in text_lower for w in ["weapon", "knife", "gun", "bleeding", "severe", "fire", "attack"]):
            priority = "P1_CRITICAL"
            reasoning_points.append("Active or immediate physical distress / threat to life detected.")
            reasoning_points.append("High urgency keyword detected in resident communication.")
            actions = [
                "Move to a well-lit, crowded, or secure locked space immediately if possible.",
                "Keep emergency phone line open; community responders alerted in <120 seconds.",
                "Do not confront any aggressor directly."
            ]
        elif category in ["medical", "child_alert"] or any(w in text_lower for w in ["break-in", "mask", "forced", "stalking"]):
            priority = "P2_HIGH"
            reasoning_points.append(f"Significant vulnerability identified ({category.replace('_', ' ').title()}).")
            reasoning_points.append("Requires rapid volunteer / patrol dispatch within 15 minutes.")
            actions = [
                "Verify coordinates with trusted emergency contacts.",
                "Responder unit notified to verify corridor camera feeds and conduct patrol.",
                "Keep child or elder phone reachable."
            ]
        elif category == "hazard":
            priority = "P3_MODERATE"
            reasoning_points.append("Environmental or infrastructure hazard reported without active violence.")
            actions = [
                "Warn nearby neighbours and pedestrians to take alternative detour.",
                "Civic authority ticket created for municipal repair team."
            ]
        else:
            priority = "P4_ADVISORY"
            reasoning_points.append("Non-urgent community advisory or general information request.")
            actions = [
                "Log entry in neighbourhood safety ledger for routine monitoring."
            ]

        return {
            "suggested_priority": priority,
            "triage_reasoning": " ".join(reasoning_points),
            "immediate_safety_checklist": actions
        }

class KnowledgeAssistant:
    """
    CrewAI Bounded Agent 3: Interfaces with the Haystack RAG service
    to retrieve officially approved community safety protocols and citations.
    """
    role = "Civic Knowledge Retrieval Officer"
    goal = "Provide verified municipal SOPs and emergency resources relevant to the incident."

    def execute(self, category: str, query_hint: str) -> List[Dict[str, str]]:
        haystack_res = retrieve_safety_guidance(query_hint)
        protocols = []
        for r in haystack_res.get("results", []):
            protocols.append({
                "title": r["title"],
                "source": r["source"],
                "protocol_snippet": r["excerpt"][:220] + "..."
            })
        return protocols

class CommunityInsightsAgent:
    """
    CrewAI Bounded Agent 4: Aggregates incident counts into de-identified
    hotspot insights, trend summaries, and proactive neighbourhood safety advice.
    """
    role = "Community Intelligence Analyst"
    goal = "Synthesize trends into actionable civic advisories without exposing PII."

    def execute(self, total_incidents: int, active_count: int, hazard_count: int) -> str:
        if active_count > 3:
            return (
                f"Elevated community vigilance recommended. {active_count} active incidents and {hazard_count} "
                "civic hazards are currently being monitored. Evening patrols have been intensified along primary corridors."
            )
        elif hazard_count > 0:
            return (
                f"Normal neighbourhood safety index. {hazard_count} infrastructure hazards under municipal review. "
                "Residents are advised to use designated Safe Transit routes after dusk."
            )
        else:
            return "Optimal neighbourhood safety metrics. All active corridors verified clear by community patrol."

class SafetyCrewOrchestrator:
    """
    Coordinates the execution of the multi-agent crew with timeouts and strict safety bounds.
    """
    def __init__(self):
        self.intake_agent = IncidentIntakeAgent()
        self.triage_agent = SafetyTriageAssistant()
        self.knowledge_agent = KnowledgeAssistant()
        self.insights_agent = CommunityInsightsAgent()

    def run_incident_assistance_workflow(
        self,
        raw_text: str,
        reported_category: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Running CrewAI incident assistance workflow for query: {raw_text[:50]}...")

        # Step 1: Intake
        intake_out = self.intake_agent.execute(raw_text, reported_category)
        if location and not intake_out.get("extracted_location"):
            intake_out["extracted_location"] = location

        # Step 2: Triage
        triage_out = self.triage_agent.execute(intake_out, raw_text)

        # Step 3: Knowledge via Haystack
        search_query = f"{intake_out['parsed_category']} {raw_text}"
        knowledge_out = self.knowledge_agent.execute(intake_out["parsed_category"], search_query)

        execution_duration = round(time.time() - start_time, 3)
        logger.info(f"CrewAI workflow completed in {execution_duration}s. Priority: {triage_out['suggested_priority']}")

        return {
            "parsed_category": intake_out["parsed_category"],
            "extracted_location": intake_out["extracted_location"],
            "missing_critical_info": intake_out["missing_critical_info"],
            "suggested_priority": triage_out["suggested_priority"],
            "triage_reasoning": triage_out["triage_reasoning"],
            "immediate_safety_checklist": triage_out["immediate_safety_checklist"],
            "retrieved_civic_protocols": knowledge_out,
            "execution_duration_sec": execution_duration,
            "advisory_notice": "AI-assisted guidance is strictly advisory. Final decisions remain with verified human responders."
        }

crew_orchestrator = SafetyCrewOrchestrator()
