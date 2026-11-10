import uuid
import datetime
from app.database.db2_connector import db_connector
from app.agents.graph import run_agentic_investigation

def simulate_multi_vector_compromise(target_user_id: str = "USR-101") -> dict:
    """Generates the Section 8 Attack Scenario:
    1. 15 rapid failed login attempts.
    2. 1 successful login from an unfamiliar device (Kali Linux Workstation, foreign IP).
    3. 1 restricted resource access attempt to TOP SECRET defense warplan.
    4. Triggers the 5-agent LangGraph correlation workflow.
    """
    now = datetime.datetime.now()
    adversary_ip = "198.51.100.77"
    adversary_location = "Bucharest / External Proxy Node"
    unfamiliar_device = "KALI-INTRUDER-WORKSTATION"

    # Step 1: Insert 15 failed login attempts spaced a few seconds apart
    print(f"Injecting 15 failed login attempts for {target_user_id}...")
    for i in range(15):
        event_time = now - datetime.timedelta(minutes=30) + datetime.timedelta(seconds=i * 4)
        db_connector.execute_update(
            """INSERT INTO LOGIN_EVENTS (event_id, user_id, timestamp, ip_address, device_name, device_type, location, status, failure_reason, user_agent)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'FAILURE', 'Invalid Kerberos Token / Bad Credentials', 'Python-urllib/3.11 AttackScript/2.4')""",
            (
                f"EVT-FAIL-{uuid.uuid4().hex[:6].upper()}",
                target_user_id,
                event_time.isoformat(),
                adversary_ip,
                unfamiliar_device,
                "Adversary Terminal",
                adversary_location
            )
        )

    # Step 2: Insert 1 successful login from the unfamiliar device
    success_time = now - datetime.timedelta(minutes=25)
    db_connector.execute_update(
        """INSERT INTO LOGIN_EVENTS (event_id, user_id, timestamp, ip_address, device_name, device_type, location, status, failure_reason, user_agent)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'SUCCESS', NULL, 'Mozilla/5.0 (X11; Linux x86_64) Kali/2026.1')""",
        (
            f"EVT-SUCC-{uuid.uuid4().hex[:6].upper()}",
            target_user_id,
            success_time.isoformat(),
            adversary_ip,
            unfamiliar_device,
            "Adversary Terminal",
            adversary_location
        )
    )

    # Step 3: Insert unauthorized access to restricted TOP SECRET asset
    access_time = now - datetime.timedelta(minutes=20)
    db_connector.execute_update(
        """INSERT INTO ACCESS_LOGS (log_id, user_id, timestamp, resource_id, resource_name, resource_type, access_type, status, classification_level)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            f"ACC-{uuid.uuid4().hex[:6].upper()}",
            target_user_id,
            access_time.isoformat(),
            "RES-WARPLAN-DELTA-9",
            "DEF-TOPSECRET-WARPLAN-DELTA: Hypersonic Intercept Grid",
            "Classified Strategic Repository",
            "EXPORT",
            "ALLOWED",
            "TOP_SECRET"
        )
    )

    # Step 4: Insert initial security alerts into SECURITY_ALERTS table
    db_connector.execute_update(
        """INSERT INTO SECURITY_ALERTS (alert_id, user_id, event_type, severity, description, timestamp, status)
           VALUES (?, ?, ?, ?, ?, ?, 'OPEN')""",
        (
            f"ALT-{uuid.uuid4().hex[:6].upper()}",
            target_user_id,
            "AUTHENTICATION_SPIKE",
            "HIGH",
            f"15 consecutive authentication failures detected from external IP {adversary_ip}.",
            (now - datetime.timedelta(minutes=28)).isoformat()
        )
    )
    db_connector.execute_update(
        """INSERT INTO SECURITY_ALERTS (alert_id, user_id, event_type, severity, description, timestamp, status)
           VALUES (?, ?, ?, ?, ?, ?, 'OPEN')""",
        (
            f"ALT-{uuid.uuid4().hex[:6].upper()}",
            target_user_id,
            "UNFAMILIAR_DEVICE_LOGIN",
            "HIGH",
            f"Successful logon from unregistered device '{unfamiliar_device}' via foreign IP {adversary_ip}.",
            success_time.isoformat()
        )
    )
    db_connector.execute_update(
        """INSERT INTO SECURITY_ALERTS (alert_id, user_id, event_type, severity, description, timestamp, status)
           VALUES (?, ?, ?, ?, ?, ?, 'OPEN')""",
        (
            f"ALT-{uuid.uuid4().hex[:6].upper()}",
            target_user_id,
            "SENSITIVE_RESOURCE_ACCESS",
            "CRITICAL",
            "Targeted query and EXPORT attempt on DEF-TOPSECRET-WARPLAN-DELTA.",
            access_time.isoformat()
        )
    )

    # Step 5: Automatically execute the LangGraph multi-agent correlation
    final_state = run_agentic_investigation(user_id=target_user_id, lookback_hours=24)

    return {
        "success": True,
        "message": f"Successfully simulated Section 8 attack scenario against {target_user_id} and executed LangGraph multi-agent correlation.",
        "incident_id": final_state.get("incident_id"),
        "severity": final_state.get("risk_assessment_findings", {}).get("severity"),
        "risk_score": final_state.get("risk_assessment_findings", {}).get("risk_score"),
        "mitre_techniques": final_state.get("threat_intel_findings", {}).get("technique_ids"),
        "agent_logs": final_state.get("agent_execution_logs")
    }

