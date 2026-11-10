import time
import uuid
from typing import Dict, Any, List
from app.agents.state import SentinelAgentState
from app.services.watsonx_service import watsonx_service

def incident_response_agent(state: SentinelAgentState) -> Dict[str, Any]:
    """Agent 5: Incident Response Agent.
    Generates tailored defensive actions, containment playbooks, and incident reports.
    MANDATORY GOVERNANCE: All proposed defensive actions are strictly marked PENDING_APPROVAL.
    """
    start_time = time.time()
    user_id = state.get("user_id", "")
    user_account = state.get("user_account", {})
    risk_findings = state.get("risk_assessment_findings", {})
    threat_findings = state.get("threat_intel_findings", {})
    behaviour_findings = state.get("behaviour_analysis_findings", {})
    event_findings = state.get("event_monitoring_findings", {})

    severity = risk_findings.get("severity", "LOW")
    risk_score = risk_findings.get("risk_score", 0)
    unfamiliar_devices = behaviour_findings.get("unfamiliar_devices", [])
    unusual_ips = behaviour_findings.get("unusual_ips", [])

    recommended_actions: List[Dict[str, Any]] = []

    # Tailored recommendations based on findings & severity
    if severity in ["CRITICAL", "HIGH"]:
        recommended_actions.append({
            "recommendation_id": f"REC-{uuid.uuid4().hex[:8].upper()}",
            "action_type": "LOCK_ACCOUNT",
            "priority": "CRITICAL",
            "description": f"Temporarily lock account {user_account.get('email', user_id)} across Defence Active Directory and LDAP realms.",
            "status": "PENDING_APPROVAL",
            "requires_approval": True,
            "target": user_account.get("username", user_id)
        })
        recommended_actions.append({
            "recommendation_id": f"REC-{uuid.uuid4().hex[:8].upper()}",
            "action_type": "REVOKE_SESSIONS",
            "priority": "CRITICAL",
            "description": f"Terminate all active OAuth2 tokens, Kerberos tickets, and VPN sessions associated with {user_id}.",
            "status": "PENDING_APPROVAL",
            "requires_approval": True,
            "target": "All Active Sessions"
        })

    if unfamiliar_devices or unusual_ips:
        target_ip = unusual_ips[0] if unusual_ips else "Unknown Endpoint"
        recommended_actions.append({
            "recommendation_id": f"REC-{uuid.uuid4().hex[:8].upper()}",
            "action_type": "ISOLATE_ENDPOINT",
            "priority": "HIGH",
            "description": f"Dispatch NAC boundary rule to quarantine workstation/IP '{target_ip}' and block traffic to perimeter firewalls.",
            "status": "PENDING_APPROVAL",
            "requires_approval": True,
            "target": target_ip
        })

    if severity in ["CRITICAL", "HIGH", "MEDIUM"]:
        recommended_actions.append({
            "recommendation_id": f"REC-{uuid.uuid4().hex[:8].upper()}",
            "action_type": "FORCE_MFA_RESET",
            "priority": "HIGH",
            "description": f"Flag user identity for compulsory FIDO2/Hardware Token re-registration and mandatory password rotation.",
            "status": "PENDING_APPROVAL",
            "requires_approval": True,
            "target": user_account.get("email", user_id)
        })
        recommended_actions.append({
            "recommendation_id": f"REC-{uuid.uuid4().hex[:8].upper()}",
            "action_type": "AUDIT_CLASSIFIED_ACCESS",
            "priority": "MEDIUM",
            "description": "Trigger digital forensics audit on all classified repository read/write operations during the incident window.",
            "status": "PENDING_APPROVAL",
            "requires_approval": True,
            "target": "Defence Cryptographic Audit Vault"
        })

    # Generate Detailed Incident Report in Markdown
    report_markdown = f"""# SENTINEL AI INCIDENT INTELLIGENCE REPORT
**Incident ID:** {state.get('incident_id', 'INC-PENDING')}
**Target Account:** {user_account.get('full_name')} (`{user_account.get('email')}`)
**Department & Role:** {user_account.get('department')} — {user_account.get('role')}
**Security Clearance:** {user_account.get('security_clearance')}
**Risk Severity:** **{severity}** (Composite Risk Score: **{risk_score}/100**)
**Classification:** {threat_findings.get('threat_classification', 'N/A')}

---

### 1. Executive Summary
The SENTINEL AI Agentic Framework detected and correlated multiple suspicious security events indicating potential account compromise. The correlation engine linked {event_findings.get('failed_logins', 0)} failed authentication attempts with successful ingress from an unfamiliar device, followed by anomalous access to high-classification defence resources.

### 2. Multi-Agent Analysis Findings
- **Agent 1 (Event Monitoring):** {event_findings.get('summary')}
- **Agent 2 (Behaviour Analysis):** {behaviour_findings.get('summary')}
- **Agent 3 (Threat Intelligence):** {threat_findings.get('summary')}
- **Agent 4 (Risk Assessment):** {risk_findings.get('summary')}

### 3. MITRE ATT&CK Matrix Mapping
{chr(10).join([f"- **{t['id']} ({t['name']})**: *{t['tactic']}* — {t['evidence']}" for t in threat_findings.get('mitre_techniques', [])]) if threat_findings.get('mitre_techniques') else "- No specific adversary techniques confirmed."}

### 4. Explainable AI Defense Rationale (IBM watsonx.ai)
{risk_findings.get('ai_reasoning', 'Analysis complete.')}

### 5. Recommended Defensive Playbook (Human Approval Required)
{chr(10).join([f"- [{a['priority']}] **{a['action_type']}**: {a['description']} *(Status: {a['status']})*" for a in recommended_actions])}

> **GOVERNANCE MANDATE:** In accordance with Defence Organization Safety Protocol, zero automatic containment actions have been executed. Authorization is pending senior Cyber Operations Commander review.
"""

    summary = (
        f"Incident Response Agent compiled {len(recommended_actions)} defensive recommendations "
        f"and completed executive report synthesis. All response actions are queued for human approval."
    )

    findings = {
        "agent": "Incident Response Agent",
        "recommended_actions": recommended_actions,
        "incident_report_markdown": report_markdown,
        "summary": summary
    }

    execution_log = {
        "agent": "Incident Response Agent",
        "stage": 5,
        "status": "COMPLETED",
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "action": f"Generated {len(recommended_actions)} human-gated response actions and Markdown intelligence report.",
        "findings_preview": summary
    }

    logs = state.get("agent_execution_logs", [])
    logs.append(execution_log)

    return {
        "incident_response_findings": findings,
        "agent_execution_logs": logs,
        "status": "ANALYSIS_COMPLETE"
    }

