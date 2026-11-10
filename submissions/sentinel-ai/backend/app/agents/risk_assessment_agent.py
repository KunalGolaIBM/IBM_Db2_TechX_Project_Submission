import time
from typing import Dict, Any
from app.agents.state import SentinelAgentState
from app.services.watsonx_service import watsonx_service

def risk_assessment_agent(state: SentinelAgentState) -> Dict[str, Any]:
    """Agent 4: Risk Assessment Agent.
    Combines outputs of Agents 1-3.
    Computes mathematical risk score (0-100), assigns severity level (Low, Medium, High, Critical),
    and generates an explainable AI security reasoning narrative.
    """
    start_time = time.time()
    event_findings = state.get("event_monitoring_findings", {})
    behaviour_findings = state.get("behaviour_analysis_findings", {})
    threat_findings = state.get("threat_intel_findings", {})
    user_account = state.get("user_account", {})

    # Component 1: Auth Failure Velocity (max 30 pts)
    failed_logins = event_findings.get("failed_logins", 0)
    failure_score = min(30, int(failed_logins * 2.0))

    # Component 2: Device & Geographic Novelty (max 30 pts)
    unfamiliar_devices = behaviour_findings.get("unfamiliar_devices", [])
    unusual_ips = behaviour_findings.get("unusual_ips", [])
    device_score = 0
    if unfamiliar_devices:
        device_score += 18
    if unusual_ips:
        device_score += 12
    device_score = min(30, device_score)

    # Component 3: Resource Classification & Sensitivity (max 25 pts)
    restricted_count = behaviour_findings.get("restricted_accesses_count", 0)
    user_clearance = user_account.get("security_clearance", "UNCLASSIFIED")
    resource_score = 0
    if restricted_count > 0:
        resource_score = 20
        if user_clearance == "TOP_SECRET":
            resource_score += 5  # Compromise of TOP_SECRET account is higher risk
    resource_score = min(25, resource_score)

    # Component 4: MITRE Technique Convergence (max 15 pts)
    mitre_count = len(threat_findings.get("mitre_techniques", []))
    mitre_score = min(15, mitre_count * 5)

    # Composite Risk Score (0 - 100)
    total_risk_score = failure_score + device_score + resource_score + mitre_score
    total_risk_score = max(0, min(100, total_risk_score))

    # Determine Severity Level
    if total_risk_score >= 90:
        severity = "CRITICAL"
    elif total_risk_score >= 70:
        severity = "HIGH"
    elif total_risk_score >= 40:
        severity = "MEDIUM"
    else:
        severity = "LOW"

    # Generate Explainable AI Reasoning via IBM watsonx.ai
    prompt = (
        f"Explain cybersecurity risk assessment for user '{user_account.get('full_name')}' (Clearance: {user_clearance}). "
        f"Telemetry: {failed_logins} failed logins, {len(unfamiliar_devices)} unfamiliar devices ({', '.join(unfamiliar_devices)}), "
        f"{restricted_count} restricted asset accesses, mapped to MITRE techniques: {', '.join(threat_findings.get('technique_ids', []))}. "
        f"Computed Risk Score: {total_risk_score}/100 [{severity}]."
    )
    system_context = (
        "You are the SENTINEL AI Risk Assessment Agent operating within a Defence Security Operations Centre. "
        "Provide a crisp, rigorous, and explainable intelligence rationale for this risk assessment."
    )
    
    ai_reasoning = watsonx_service.generate_text(prompt, system_context)

    # Structured explainable breakdown
    score_breakdown = {
        "authentication_velocity_score": f"{failure_score}/30",
        "device_anomaly_score": f"{device_score}/30",
        "resource_sensitivity_score": f"{resource_score}/25",
        "mitre_convergence_score": f"{mitre_score}/15",
        "composite_risk_score": f"{total_risk_score}/100"
    }

    summary = (
        f"Risk Assessment Agent assigned severity level '{severity}' with a composite risk score of {total_risk_score}/100. "
        f"Primary drivers: {failure_score} pts from auth velocity, {device_score} pts from device novelty, "
        f"{resource_score} pts from classified asset exposure."
    )

    findings = {
        "agent": "Risk Assessment Agent",
        "risk_score": total_risk_score,
        "severity": severity,
        "score_breakdown": score_breakdown,
        "ai_reasoning": ai_reasoning,
        "summary": summary
    }

    execution_log = {
        "agent": "Risk Assessment Agent",
        "stage": 4,
        "status": "COMPLETED",
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "action": f"Calculated risk score {total_risk_score}/100 -> Severity: {severity}.",
        "findings_preview": summary
    }

    logs = state.get("agent_execution_logs", [])
    logs.append(execution_log)

    return {
        "risk_assessment_findings": findings,
        "agent_execution_logs": logs
    }

