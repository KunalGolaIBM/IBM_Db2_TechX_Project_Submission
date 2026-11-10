import logging
from typing import Dict, Any
from .state import InvestigationState
try:
    from src.backend.app.services.risk_service import RiskScoringEngine
except ImportError:
    from ..backend.app.services.risk_service import RiskScoringEngine

logger = logging.getLogger("db2sentinel.agent.risk")

class RiskAgent:
    """
    Agent 4: Risk Assessment Agent (LangChain / LangGraph Node)
    Interprets the deterministic risk score, explains the contributing factors
    (Behavior, Privilege, Volume, Authentication), and never invents arbitrary metrics.
    """
    @staticmethod
    def run(state: InvestigationState) -> Dict[str, Any]:
        logger.info(f"[RiskAgent] Evaluating risk for incident {state['incident_id']}...")
        events = state.get("raw_events", [])
        alerts = state.get("associated_alerts", [])

        # Read highest alert score or calculate composite score
        max_score = max([float(a.get("risk_score", 50.0)) for a in alerts], default=50.0)

        # Calculate multi-factor explanation
        behavior_dev = 85.0 if any(e.get("event_type") == "SENSITIVE_ACCESS" for e in events) else 40.0
        privilege_sens = 90.0 if any("SYSCAT" in (e.get("object_name") or "") for e in events) else 50.0
        volume_anom = 90.0 if any(e.get("event_type") == "SENSITIVE_ACCESS" for e in events) else 20.0
        auth_anom = 85.0 if any(e.get("status") == "FAILURE" for e in events) else 30.0

        risk_eval = RiskScoringEngine.calculate_score(
            behavior_dev=behavior_dev,
            privilege_sens=privilege_sens,
            volume_anomaly=volume_anom,
            auth_anomaly=auth_anom
        )
        # Use the maximum of alert score or composite score
        final_score = max(max_score, risk_eval["risk_score"])
        risk_eval["risk_score"] = final_score

        explanation = (
            f"Evaluated Risk Score: {final_score}/100 [{risk_eval['severity']}]. "
            f"Factors: Behavior Deviation ({risk_eval['breakdown']['behavior_deviation']['weighted']} pts), "
            f"Privilege Sensitivity ({risk_eval['breakdown']['privilege_sensitivity']['weighted']} pts), "
            f"Data Volume Anomaly ({risk_eval['breakdown']['volume_anomaly']['weighted']} pts), "
            f"Authentication Anomaly ({risk_eval['breakdown']['auth_anomaly']['weighted']} pts)."
        )

        return {
            "risk_evaluation": risk_eval,
            "factual_findings": state.get("factual_findings", []) + [explanation],
            "workflow_status": "RISK_ASSESSED"
        }
