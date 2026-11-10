import datetime
import time
from typing import Dict, Any
from app.agents.state import SentinelAgentState
from app.database.db2_connector import db_connector
from app.services.watsonx_service import watsonx_service

def event_monitoring_agent(state: SentinelAgentState) -> Dict[str, Any]:
    """Agent 1: Event Monitoring Agent.
    Monitors login records, access logs, and security events from IBM Db2.
    Identifies high-velocity anomalies and burst failures requiring investigation.
    """
    start_time = time.time()
    user_id = state.get("user_id")
    lookback_hours = state.get("lookback_hours", 24)

    # 1. Fetch user account details from IBM Db2 if not present
    user_account = state.get("user_account")
    if not user_account:
        rows = db_connector.execute_query(
            "SELECT * FROM USER_ACCOUNTS WHERE user_id = ?", (user_id,)
        )
        if rows:
            user_account = rows[0]
        else:
            user_account = {
                "user_id": user_id,
                "username": "unknown",
                "full_name": "Unknown Personnel",
                "role": "Unknown",
                "department": "Unknown",
                "security_clearance": "UNCLASSIFIED"
            }

    # 2. Retrieve recent login events from Db2
    logins = db_connector.execute_query(
        "SELECT * FROM LOGIN_EVENTS WHERE user_id = ? ORDER BY timestamp DESC LIMIT 50",
        (user_id,)
    )

    # 3. Retrieve recent resource access records from Db2
    accesses = db_connector.execute_query(
        "SELECT * FROM ACCESS_LOGS WHERE user_id = ? ORDER BY timestamp DESC LIMIT 50",
        (user_id,)
    )

    total_logins = len(logins)
    failed_logins = sum(1 for l in logins if l.get("status") == "FAILURE")
    successful_logins = sum(1 for l in logins if l.get("status") == "SUCCESS")
    failure_rate = (failed_logins / total_logins) if total_logins > 0 else 0.0

    # Look for rapid failed login bursts
    has_burst_failures = failed_logins >= 5
    distinct_ips = list(set(l.get("ip_address") for l in logins if l.get("ip_address")))
    distinct_devices = list(set(l.get("device_name") for l in logins if l.get("device_name")))

    # Assess off-hours activity (e.g. 23:00 - 05:00)
    unusual_time_events = []
    for l in logins:
        ts_str = l.get("timestamp", "")
        try:
            # Parse timestamp if available
            dt = datetime.datetime.fromisoformat(ts_str.replace("Z", ""))
            if dt.hour < 6 or dt.hour > 22:
                unusual_time_events.append(l.get("event_id"))
        except Exception:
            pass

    monitoring_summary = (
        f"Event Monitoring Agent analysed {total_logins} authentication events and {len(accesses)} resource access records from Db2. "
        f"Detected {failed_logins} failed login attempts ({failure_rate*100:.1f}% failure rate) across {len(distinct_ips)} distinct IP addresses. "
    )
    if has_burst_failures:
        monitoring_summary += f"CRITICAL ANOMALY: Authentication failure surge detected ({failed_logins} failures). Triggering full behavioral investigation."
    else:
        monitoring_summary += "Authentication activity within nominal thresholds."

    findings = {
        "agent": "Event Monitoring Agent",
        "total_logins": total_logins,
        "failed_logins": failed_logins,
        "successful_logins": successful_logins,
        "failure_rate": round(failure_rate, 2),
        "distinct_ips": distinct_ips,
        "distinct_devices": distinct_devices,
        "has_burst_failures": has_burst_failures,
        "unusual_time_count": len(unusual_time_events),
        "summary": monitoring_summary,
        "status": "SUSPICIOUS" if (has_burst_failures or failure_rate > 0.4) else "NOMINAL"
    }

    execution_log = {
        "agent": "Event Monitoring Agent",
        "stage": 1,
        "status": "COMPLETED",
        "duration_ms": round((time.time() - start_time) * 1000, 2),
        "action": f"Scanned {total_logins} login events and {len(accesses)} access logs in IBM Db2.",
        "findings_preview": monitoring_summary
    }

    logs = state.get("agent_execution_logs", [])
    logs.append(execution_log)

    return {
        "user_account": user_account,
        "raw_logins": logins,
        "raw_accesses": accesses,
        "event_monitoring_findings": findings,
        "agent_execution_logs": logs
    }

