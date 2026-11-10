#!/usr/bin/env python3
"""
End-to-End Demonstration Runner for Db2Sentinel AI.
Executes the full workflow:
  1. Seed controlled demonstration telemetry.
  2. Run the deterministic cybersecurity detection engine.
  3. Formulate correlated incident.
  4. Execute LangGraph multi-agent investigation.
  5. Present risk score breakdown and executive incident report.
  6. Simulate human-in-the-loop DBA approval.
"""
import sys
import json
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from src.backend.app.database import db_manager
from src.backend.app.services.detection_service import DetectionEngine
from src.workflows.security_workflow import execute_incident_investigation

def main():
    print("=" * 70)
    print("Db2Sentinel AI — End-to-End Enterprise Investigation Walkthrough")
    print("=" * 70)

    # Step 1: Seed Demonstration Telemetry
    print("\n[STEP 1] Ingesting Telemetry into IBM Db2...")
    db_manager.seed_demo_data()
    events = db_manager.get_events(limit=20)
    print(f"✅ Ingested {len(events)} events (Active engine: {db_manager.active_mode})")

    # Step 2: Run Detection Engine
    print("\n[STEP 2] Running Cybersecurity Detection Rules...")
    engine = DetectionEngine(db_manager)
    alerts = engine.run_detection()
    print(f"✅ Detection completed: {len(alerts)} alerts generated:")
    for a in alerts:
        print(f"   • [{a.get('severity')}] {a.get('alert_name')} (Risk Score: {a.get('risk_score')})")

    # Step 3: Create Incident
    inc_id = "INC-2026-0884"
    print(f"\n[STEP 3] Correlating Alerts into Security Incident: {inc_id}...")
    db_manager.insert_incident({
        "incident_id": inc_id,
        "title": "Compromised Account: Suspicious Off-Hours Financial Data Exfiltration",
        "description": "Multi-stage attack sequence: brute force attempts, off-hours connection, 28k rows extracted from CUSTOMER_FINANCIAL_RECORDS, and catalog reconnaissance.",
        "severity": "CRITICAL",
        "risk_score": 84.5,
        "status": "INVESTIGATING",
        "assigned_to": "REPORT_USER"
    })
    print(f"✅ Incident {inc_id} created in database.")

    # Step 4: Execute LangGraph Multi-Agent Investigation
    print("\n[STEP 4] Launching LangGraph Multi-Agent Investigation Workflow...")
    print("   Agents: Detection ➔ Evidence ➔ Investigation ➔ Risk ➔ Response ➔ Report")
    investigation_state = execute_incident_investigation(
        incident_id=inc_id,
        target_username="REPORT_USER",
        target_ip="198.51.100.44",
        events=events,
        alerts=alerts
    )
    print(f"✅ Workflow Status: {investigation_state.get('workflow_status')}")

    # Step 5: Display Findings & Risk Breakdown
    risk = investigation_state.get("risk_evaluation", {})
    print(f"\n[STEP 5] Risk Evaluation & Evidence Provenance:")
    print(f"   • Composite Risk Score: {risk.get('risk_score')}/100 [{risk.get('severity')}]")
    print(f"   • Formula: {risk.get('formula')}")
    print(f"   • MITRE ATT&CK Tactics: {', '.join(investigation_state.get('mitre_tactics', []))}")
    print("\n   Factual Evidence Dossier:")
    for f in investigation_state.get("factual_findings", [])[:4]:
        print(f"     - {f}")

    # Step 6: Human-in-the-Loop Governance
    print("\n[STEP 6] Human Governance Checkpoint:")
    print("   ⚠️ SENSITIVE REMEDIATION PAUSED AT CHECKPOINT GATE")
    for act in investigation_state.get("recommended_actions", []):
        print(f"   • Proposed Action: {act['action_type']} -> {act['target']}")
        print(f"     SQL: {act['proposed_sql']}")

    app_id = db_manager.insert_approval({
        "incident_id": inc_id,
        "proposed_action": "TERMINATE SESSION & LOCK DB2 CREDENTIALS FOR REPORT_USER",
        "requested_by": "Response Agent",
        "approval_status": "PENDING"
    })

    print(f"\n   [SecOps Admin Review] Simulating DBA Approval for request {app_id}...")
    db_manager.update_approval(app_id, "APPROVED", "Lead Database Administrator", "Verified exfiltration attack sequence.")
    db_manager.log_audit("CONTAINMENT_APPROVED", "Lead DBA", f"Executed approval {app_id}")
    print(f"✅ ACTION APPROVED: Session terminated and audit committed to IBM Db2 table SENTINEL_AUDIT_LOG.")

    print("\n" + "=" * 70)
    print("✅ Walkthrough Demonstration Completed Successfully!")
    print("=" * 70)

if __name__ == "__main__":
    main()
