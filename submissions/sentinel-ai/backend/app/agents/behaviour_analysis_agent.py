import time
from typing import Dict, Any, List
from app.agents.state import SentinelAgentState

# Known registered defence devices per user
KNOWN_BASELINE_DEVICES = {
    "USR-101": ["DEF-SEC-LAPTOP-101"],
    "USR-102": ["CYBER-TERMINAL-09"],
    "USR-103": ["LAB-SEC-WORKSTATION"],
    "USR-104": ["LOG-DESK-04"],
    "USR-105": ["DIA-INTEL-MAC-01"]
}

# Known regular internal subnets
MILITARY_INTERNAL_SUBNETS = ["10.240.", "10.110.", "10.150.", "10.200.", "10.180."]

def behaviour_analysis_agent(state: SentinelAgentState) -> Dict[str, Any]:
    """Agent 2: Behaviour Analysis Agent.
    Compares current activities against historical baseline profiles.
    Detects unfamiliar devices, unusual foreign IPs, and anomalous resource access.
    """
    start_time = time.time()
    user_id = state.get("user_id", "")
    user_account = state.get("user_account", {})
    raw_logins = state.get("raw_logins", [])
    raw_accesses = state.get("raw_accesses", [])

    baseline_devices = KNOWN_BASELINE_DEVICES.get(user_id, ["DEF-SEC-LAPTOP-101"])
    clearance = user_account.get("security_clearance", "UNCLASSIFIED")

    anomalies: List[Dict[str, Any]] = []
    unfamiliar_devices: List[str] = []
    unusual_ips: List[str] = []
    restricted_accesses: List[Dict[str, Any]] = []

    # 1. Device and IP Analysis
    for login in raw_logins:
        device = login.get("device_name", "")
        ip = login.get("ip_address", "")
        status = login.get("status", "")

        # Check for device novelty
        if device and device not in baseline_devices and device not in unfamiliar_devices:
            unfamiliar_devices.append(device)
            anomalies.append({
                "type": "UNFAMILIAR_DEVICE",
                "severity": "HIGH",
                "detail": f"Successful login from unregistered host '{device}' (Baseline permits: {', '.join(baseline_devices)}).",
                "event_id": login.get("event_id")
            })

        # Check for non-military external IP
        is_internal = any(ip.startswith(prefix) for prefix in MILITARY_INTERNAL_SUBNETS)
        if not is_internal and ip not in unusual_ips:
            unusual_ips.append(ip)
            anomalies.append({
                "type": "EXTERNAL_FOREIGN_IP",
                "severity": "HIGH",
                "detail": f"Access initiated from unauthenticated external/foreign IP address '{ip}' (Location: {login.get('location', 'Unknown')}).",
                "event_id": login.get("event_id")
            })

    # 2. Resource Access Deviation Analysis
    for access in raw_accesses:
        res_class = access.get("classification_level", "UNCLASSIFIED")
        res_name = access.get("resource_name", "")
        res_id = access.get("resource_id", "")
        acc_status = access.get("status", "")

        # Check if resource classification exceeds clearance or is sensitive WARPLAN / CRYPTO
        is_sensitive = any(keyword in res_name.upper() for keyword in ["WARPLAN", "NUCLEAR", "CRYPTO", "CIPHER", "TOPSECRET", "BALLISTIC"])
        if is_sensitive or (res_class == "TOP_SECRET" and clearance != "TOP_SECRET"):
            restricted_accesses.append(access)
            anomalies.append({
                "type": "SENSITIVE_RESOURCE_ACCESS",
                "severity": "CRITICAL" if is_sensitive else "HIGH",
                "detail": f"Anomalous access attempt to restricted asset '{res_name}' [{res_class}] ({access.get('access_type')} - {acc_status}).",
                "resource_id": res_id
            })

    # 3. Calculate Baseline Deviation Score (0 - 100)
    deviation_score = 0
    if unfamiliar_devices:
        deviation_score += 35
    if unusual_ips:
        deviation_score += 25
    if restricted_accesses:
        deviation_score += 35
    if state.get("event_monitoring_findings", {}).get("has_burst_failures"):
        deviation_score += 15
    deviation_score = min(deviation_score, 100)

    summary = (
        f"Behaviour Analysis Agent identified {len(anomalies)} behavioral anomalies. "
        f"Baseline deviation score calculated at {deviation_score}/100. "
    )
    if unfamiliar_devices:
        summary += f"Unfamiliar device(s) detected: {', '.join(unfamiliar_devices)}. "
    if unusual_ips:
        summary += f"External anomalous IP(s): {', '.join(unusual_ips)}. "
    if restricted_accesses:
        summary += f"Unusual access to {len(restricted_accesses)} restricted defence resource(s)."

    findings = {
        "agent": "Behaviour Analysis Agent",
        "baseline_devices": baseline_devices,
        "unfamiliar_devices": unfamiliar_devices,
        "unusual_ips": unusual_ips,
        "restricted_accesses_count": len(restricted_accesses),
        "anomalies": anomalies,
        "deviation_score": deviation_score,
        "summary": summary
    }

    execution_log = {
        "agent": "Behaviour Analysis Agent",
        "stage": 2,
        "status": "COMPLETED",
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "action": f"Evaluated behavioral baseline. Found {len(unfamiliar_devices)} unfamiliar devices and {len(anomalies)} anomalies.",
        "findings_preview": summary
    }

    logs = state.get("agent_execution_logs", [])
    logs.append(execution_log)

    return {
        "behaviour_analysis_findings": findings,
        "agent_execution_logs": logs
    }

