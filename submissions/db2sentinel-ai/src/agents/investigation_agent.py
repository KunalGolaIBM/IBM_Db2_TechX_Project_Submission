import logging
from typing import Dict, Any, List
from .state import InvestigationState

logger = logging.getLogger("db2sentinel.agent.investigation")

class InvestigationAgent:
    """
    Agent 3: Investigation Agent (LangChain / LangGraph Node)
    Synthesizes correlated evidence into attack vectors, distinguishes verified
    factual findings from inferred hypotheses, and maps techniques to MITRE ATT&CK.
    """
    @staticmethod
    def run(state: InvestigationState) -> Dict[str, Any]:
        logger.info(f"[InvestigationAgent] Formulating attack hypotheses for incident {state['incident_id']}...")
        events = state.get("raw_events", [])
        hypotheses = []
        mitre_tactics = []

        has_failed_auth = any(e.get("event_type") == "AUTHENTICATION" and e.get("status") == "FAILURE" for e in events)
        has_off_hours = any("off-hours" in (e.get("raw_details") or "").lower() for e in events)
        has_sensitive_access = any(e.get("event_type") == "SENSITIVE_ACCESS" or "FINANCIAL" in (e.get("object_name") or "") for e in events)
        has_priv_recon = any(e.get("event_type") == "PRIVILEGE_RECON" or "SYSCAT" in (e.get("object_name") or "") for e in events)

        if has_failed_auth and has_off_hours:
            hypotheses.append("Hypothesis 1: Initial access via compromised credential spray or brute-force from untrusted external subnet.")
            mitre_tactics.append("T1110_Brute_Force")

        if has_priv_recon:
            hypotheses.append("Hypothesis 2: Adversary performed database discovery against SYSCAT catalog to inspect DBA authorities.")
            mitre_tactics.append("T1087_Account_Discovery")

        if has_sensitive_access:
            hypotheses.append("Hypothesis 3: Bulk data exfiltration attempted against sensitive financial ledger tables.")
            mitre_tactics.append("T1213_Data_from_Information_Repositories")

        if not hypotheses:
            hypotheses.append("Hypothesis: Isolated operational anomaly without confirmed multi-stage adversary indicators.")

        return {
            "attack_hypotheses": hypotheses,
            "mitre_tactics": list(set(mitre_tactics)),
            "workflow_status": "INVESTIGATION_COMPLETE"
        }
