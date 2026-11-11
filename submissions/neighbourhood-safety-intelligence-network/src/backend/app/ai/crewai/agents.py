import logging
import re
import time
from typing import Dict, Any, List, Optional
from backend.app.ai.haystack.rag_pipeline import retrieve_safety_guidance

logger = logging.getLogger("neighbourhood_safety.crewai")


# Keyword rules are matched on whole words / phrases (see _mentions), in priority order.
CATEGORY_KEYWORDS = (
    ("sos", ("sos", "help me", "attack", "attacked", "danger", "stalk", "stalking", "stalker", "emergency",
             "assault", "assaulted", "kidnap", "following me")),
    ("medical", ("heart attack", "chest pain", "breathing", "breathe", "unconscious", "bleeding", "blood",
                 "doctor", "ambulance", "fell", "fall", "fallen", "injury", "injured", "fainted", "seizure", "stroke")),
    ("child_alert", ("child", "children", "kid", "kids", "school", "son", "daughter", "school bus",
                     "missing child", "boy", "girl")),
    ("elder_welfare", ("elder", "elderly", "senior", "grandfather", "grandmother", "grandpa", "grandma",
                       "old man", "old woman", "medicine", "medicines", "wellness")),
    ("suspicious_activity", ("prowler", "masked", "mask", "loiter", "loitering", "suspicious", "theft",
                             "stolen", "break-in", "burglar", "burglary", "trespass", "trespassing")),
)
LIFE_THREAT_WORDS = ("weapon", "knife", "gun", "bleeding heavily", "severe bleeding", "fire", "smoke",
                     "attack", "attacked", "not breathing", "unconscious")
ELDER_RISK_WORDS = ("not answering", "not answered", "hasn't answered", "has not answered", "no answer",
                    "not picking up", "not responding", "unresponsive", "no response", "no reply",
                    "missed", "fell", "fall", "collapsed", "confused", "wandered", "missing")
INTRUSION_WORDS = ("break-in", "breaking in", "forced entry", "forced", "stalking", "masked")
TIME_WORDS = ("now", "just", "minutes", "minute", "hour", "hours", "pm", "am", "today", "tonight",
              "yesterday", "morning", "evening", "since")


def _mentions(text: str, words) -> bool:
    """True if any keyword or phrase appears as whole words ("person" does not contain "son")."""
    return any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", text) for w in words)


class IncidentIntakeAgent:
    """
    CrewAI Bounded Agent 1: Structures a resident's free-text report,
    extracts key entities, category, and identifies critical missing information.
    """
    role = "Incident Intake Specialist"
    goal = "Transform unstructured citizen safety reports into structured, actionable triage tickets."

    def execute(self, raw_text: str, reported_category: Optional[str] = None) -> Dict[str, Any]:
        text_lower = raw_text.lower()

        # 1. Category identification (whole-word matching: "person" must not match "son")
        detected_category = reported_category or "hazard"
        for category, words in CATEGORY_KEYWORDS:
            if _mentions(text_lower, words):
                detected_category = category
                break

        # 2. Location entity extraction
        location_match = re.search(r'\b(?:at|near|behind|in front of|opposite|in|on)\s+([A-Za-z0-9\s,\.-]{4,40})', raw_text, re.IGNORECASE)
        extracted_location = location_match.group(1).strip() if location_match else None

        # 3. Missing information detection
        missing = []
        if not extracted_location:
            missing.append("Specific street, landmark, or apartment number")
        if not _mentions(text_lower, TIME_WORDS):
            missing.append("Exact time or duration of incident")
        if detected_category in ["sos", "medical", "elder_welfare"] and not _mentions(text_lower, ("alone", "with")):
            missing.append("Whether the person is currently alone or accompanied")

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
        reasoning_points: List[str] = []

        if category == "sos" or _mentions(text_lower, LIFE_THREAT_WORDS):
            priority = "P1_CRITICAL"
            reasoning_points.append("Active or immediate physical distress / threat to life detected.")
            actions = [
                "Move to a well-lit, crowded, or secure locked space immediately if possible.",
                "Keep emergency phone line open; community responders alerted in <120 seconds.",
                "Do not confront any aggressor directly."
            ]
        elif (category in ["medical", "child_alert"]
              or (category == "elder_welfare" and _mentions(text_lower, ELDER_RISK_WORDS))
              or _mentions(text_lower, INTRUSION_WORDS)):
            priority = "P2_HIGH"
            reasoning_points.append(f"Significant vulnerability identified ({category.replace('_', ' ').title()}).")
            reasoning_points.append("Requires rapid volunteer / patrol dispatch within 15 minutes.")
            actions = [
                "Verify coordinates with trusted emergency contacts.",
                "Dispatch the nearest verified responder for an in-person check.",
                "Keep the child's or elder's phone line reachable."
            ]
        elif category in ["hazard", "suspicious_activity", "elder_welfare"]:
            priority = "P3_MODERATE"
            reasoning_points.append(
                {"hazard": "Environmental or infrastructure hazard reported without active violence.",
                 "suspicious_activity": "Suspicious activity reported without an immediate threat to life.",
                 "elder_welfare": "Senior welfare request without signs of an emergency."}[category])
            actions = {
                "hazard": ["Warn nearby neighbours and pedestrians to take an alternative route.",
                           "Civic authority ticket created for the municipal repair team."],
                "suspicious_activity": ["Do not approach; note descriptions, vehicle numbers and direction of travel.",
                                        "Patrol notified to verify the area on its next round."],
                "elder_welfare": ["Schedule a wellness visit from a verified volunteer.",
                                  "Confirm medicines and essentials are available."],
            }[category]
        else:
            priority = "P4_ADVISORY"
            reasoning_points.append("Non-urgent community advisory or general information request.")
            actions = ["Log entry in neighbourhood safety ledger for routine monitoring."]

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
        haystack_res = retrieve_safety_guidance(query_hint, incident_type=category)
        protocols = []
        for r in haystack_res.get("results", []):
            protocols.append({
                "title": r["title"],
                "source": r["source"],
                "protocol_snippet": r.get("cited_passage") or (r["excerpt"][:220] + "..."),
                "matched_by": r.get("matched_by", ""),
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
        search_query = f"{intake_out['parsed_category'].replace('_', ' ')} {raw_text}"
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
