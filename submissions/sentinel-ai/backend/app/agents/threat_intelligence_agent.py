import time
from typing import Dict, Any, List
from app.agents.state import SentinelAgentState
from app.services.watsonx_service import watsonx_service

MITRE_TECHNIQUE_CATALOG = {
    "T1110.001": {
        "id": "T1110.001",
        "name": "Brute Force: Password Guessing",
        "tactic": "Credential Access",
        "matrix": "Enterprise",
        "description": "Adversaries may guess passwords to gain access to target accounts without account-specific knowledge.",
        "url": "https://attack.mitre.org/techniques/T1110/001/"
    },
    "T1078.002": {
        "id": "T1078.002",
        "name": "Valid Accounts: Domain Accounts",
        "tactic": "Defense Evasion / Persistence",
        "matrix": "Enterprise",
        "description": "Adversaries may compromise and reuse credentials of domain accounts to maintain persistent access and blend in.",
        "url": "https://attack.mitre.org/techniques/T1078/002/"
    },
    "T1530": {
        "id": "T1530",
        "name": "Data from Cloud/Restricted Repositories",
        "tactic": "Collection",
        "matrix": "Enterprise",
        "description": "Adversaries may access and extract sensitive information from internal repositories or classified storage systems.",
        "url": "https://attack.mitre.org/techniques/T1530/"
    },
    "T1021": {
        "id": "T1021",
        "name": "Remote Services",
        "tactic": "Lateral Movement",
        "matrix": "Enterprise",
        "description": "Adversaries may use Valid Accounts to log into remote services such as SSH, RDP, or VPN tunnels.",
        "url": "https://attack.mitre.org/techniques/T1021/"
    },
    "T1078": {
        "id": "T1078",
        "name": "Valid Accounts",
        "tactic": "Initial Access",
        "matrix": "Enterprise",
        "description": "Adversaries may obtain credentials of existing legitimate accounts to gain initial network entry.",
        "url": "https://attack.mitre.org/techniques/T1078/"
    }
}

def threat_intelligence_agent(state: SentinelAgentState) -> Dict[str, Any]:
    """Agent 3: Threat Intelligence Agent.
    Maps correlated anomalies directly against the MITRE ATT&CK framework.
    Assigns threat classification and produces structured intelligence evidence.
    """
    start_time = time.time()
    event_findings = state.get("event_monitoring_findings", {})
    behaviour_findings = state.get("behaviour_analysis_findings", {})

    failed_logins = event_findings.get("failed_logins", 0)
    has_burst = event_findings.get("has_burst_failures", False)
    unfamiliar_devices = behaviour_findings.get("unfamiliar_devices", [])
    unusual_ips = behaviour_findings.get("unusual_ips", [])
    anomalies = behaviour_findings.get("anomalies", [])

    matched_techniques: List[Dict[str, Any]] = []

    # 1. Check for T1110.001 (Brute Force / Password Guessing)
    if failed_logins >= 5 or has_burst:
        t = dict(MITRE_TECHNIQUE_CATALOG["T1110.001"])
        t["confidence"] = 0.94 if failed_logins >= 10 else 0.82
        t["evidence"] = f"Detected sequence of {failed_logins} failed authentication attempts within a compressed timeframe."
        matched_techniques.append(t)

    # 2. Check for T1078.002 / T1078 (Valid Accounts compromise)
    if (failed_logins >= 3 and unfamiliar_devices) or (event_findings.get("successful_logins", 0) > 0 and unfamiliar_devices):
        t = dict(MITRE_TECHNIQUE_CATALOG["T1078.002"])
        t["confidence"] = 0.91
        t["evidence"] = f"Account authenticated successfully from unfamiliar host '{unfamiliar_devices[0]}' immediately following authentication friction."
        matched_techniques.append(t)

    # 3. Check for T1530 (Data from Cloud / Restricted Repository)
    has_restricted_access = any(a.get("type") == "SENSITIVE_RESOURCE_ACCESS" for a in anomalies)
    if has_restricted_access:
        t = dict(MITRE_TECHNIQUE_CATALOG["T1530"])
        t["confidence"] = 0.88
        t["evidence"] = "Unauthorized targeting and query execution on classified defense command repositories."
        matched_techniques.append(t)

    # 4. Check for T1021 (Remote Services Lateral Movement)
    if unusual_ips:
        t = dict(MITRE_TECHNIQUE_CATALOG["T1021"])
        t["confidence"] = 0.85
        t["evidence"] = f"External network ingress detected via remote host IP {unusual_ips[0]} bypassing internal boundary segments."
        matched_techniques.append(t)

    # Threat Classification
    if len(matched_techniques) >= 3:
        threat_classification = "ADVANCED ACCOUNT COMPROMISE & LATERAL EXFILTRATION ATTEMPT"
        threat_actor_profile = "Suspected Advanced Persistent Threat (APT) utilizing automated credential stuffing transitioned to targeted manual espionage."
    elif len(matched_techniques) >= 1:
        threat_classification = "SUSPECTED CREDENTIAL SPRAY / BRUTE FORCE ACTIVITY"
        threat_actor_profile = "Opportunistic or targeted credential attack against defense domain accounts."
    else:
        threat_classification = "NOMINAL / LOW RISK TELEMETRY"
        threat_actor_profile = "Standard military domain operator activity."

    summary = (
        f"Threat Intelligence Agent classified activity as '{threat_classification}'. "
        f"Mapped {len(matched_techniques)} technique(s) in MITRE ATT&CK Enterprise Matrix: "
        f"{', '.join(t['id'] + ' (' + t['name'] + ')' for t in matched_techniques) if matched_techniques else 'None'}."
    )

    findings = {
        "agent": "Threat Intelligence Agent",
        "threat_classification": threat_classification,
        "threat_actor_profile": threat_actor_profile,
        "mitre_techniques": matched_techniques,
        "technique_ids": [t["id"] for t in matched_techniques],
        "summary": summary
    }

    execution_log = {
        "agent": "Threat Intelligence Agent",
        "stage": 3,
        "status": "COMPLETED",
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "action": f"Correlated security events with MITRE ATT&CK. Identified {len(matched_techniques)} adversary techniques.",
        "findings_preview": summary
    }

    logs = state.get("agent_execution_logs", [])
    logs.append(execution_log)

    return {
        "threat_intel_findings": findings,
        "agent_execution_logs": logs
    }

