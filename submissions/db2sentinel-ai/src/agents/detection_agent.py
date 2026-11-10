import logging
from typing import Dict, Any
from .state import InvestigationState

logger = logging.getLogger("db2sentinel.agent.detection")

class DetectionAgent:
    """
    Agent 1: Detection Agent (LangChain / LangGraph Node)
    Analyzes normalized Db2 security telemetry to identify active rule breaches,
    correlate associated alerts, and establish initial incident scope.
    """
    @staticmethod
    def run(state: InvestigationState) -> Dict[str, Any]:
        logger.info(f"[DetectionAgent] Processing incident {state['incident_id']}...")
        events = state.get("raw_events", [])
        alerts = state.get("associated_alerts", [])

        findings = []
        rules_triggered = set()

        for a in alerts:
            rule_name = a.get("alert_name", "Unknown Rule")
            rules_triggered.add(rule_name)
            findings.append(f"Triggered alert: {rule_name} (Score: {a.get('risk_score')})")

        finding_summary = (
            f"Detected {len(rules_triggered)} distinct security violations across {len(events)} events. "
            f"Active rules: {', '.join(rules_triggered)}."
        )

        return {
            "factual_findings": state.get("factual_findings", []) + [finding_summary],
            "workflow_status": "DETECTION_COMPLETE"
        }
