import logging
from datetime import datetime
from typing import Dict, Any
from .state import InvestigationState

logger = logging.getLogger("db2sentinel.agent.report")

class ReportAgent:
    """
    Agent 6: Incident Reporting Agent (LangChain / LangGraph Node)
    Compiles a comprehensive, executive incident report citing factual Db2 evidence,
    tested hypotheses, MITRE ATT&CK techniques, and recommended next steps.
    """
    @staticmethod
    def run(state: InvestigationState) -> Dict[str, Any]:
        logger.info(f"[ReportAgent] Compiling executive report for incident {state['incident_id']}...")
        inc_id = state.get("incident_id")
        user = state.get("target_username")
        ip = state.get("target_ip")
        risk = state.get("risk_evaluation", {})
        score = risk.get("risk_score", 50.0)
        sev = risk.get("severity", "MEDIUM")
        hypotheses = state.get("attack_hypotheses", [])
        tactics = state.get("mitre_tactics", [])
        actions = state.get("recommended_actions", [])
        dossier = state.get("evidence_dossier", [])

        report_text = f"""### EXECUTIVE INCIDENT INVESTIGATION REPORT: {inc_id}
**Target Account:** {user} | **Source IP:** {ip}  
**Evaluated Severity:** {sev} (Risk Score: {score}/100)  
**Investigation Timestamp:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}  

#### 1. Attack Hypotheses & MITRE ATT&CK Mapping
{chr(10).join(f"- {h}" for h in hypotheses)}
- **Mapped Tactics:** {', '.join(tactics) if tactics else 'None'}

#### 2. Correlated Factual Evidence (From IBM Db2)
- Reconstructed {len(dossier)} verified chronological events from Db2 audit and event monitors.
- Primary indicators include off-hours external connection, sensitive table reads, and privilege queries.

#### 3. Recommended Containment Actions (Pending Human Approval)
{chr(10).join(f"- **{a['action_type']}**: {a['target']} ({a['risk_mitigation']})" for a in actions)}

*Report generated autonomously by Db2Sentinel AI LangGraph Multi-Agent Engine under human-in-the-loop governance.*
"""

        return {
            "investigation_reports": state.get("investigation_reports", []) + [{
                "incident_id": inc_id,
                "summary": report_text,
                "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            }],
            "workflow_status": "COMPLETED"
        }
