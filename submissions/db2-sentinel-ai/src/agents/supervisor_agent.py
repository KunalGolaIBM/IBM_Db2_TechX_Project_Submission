"""
Supervisor & Human-in-the-Loop Approval Agent for Db2 Sentinel AI.
Executes authoritative enforcement actions: account freezes, SAR filings,
and immutable cryptographic audit trail commits in IBM Db2.
"""

import uuid
from datetime import datetime
from typing import Dict, Any

from src.agents.state import SentinelState
from src.db.queries import freeze_account, save_sar_filing, append_audit_trail


class SupervisorAgent:
    """Supervises workflow decisions, authorizes account freezes, and signs audit logs."""

    def __init__(self):
        self.name = "SupervisorAgent"

    def run(self, state: SentinelState, auto_approve: bool = True) -> SentinelState:
        rec_action = state.get("recommended_action", "CLEAR_ALERT")
        tx = state.get("transaction_data", {})
        tx_id = tx.get("TX_ID", "")
        sender_id = tx.get("SENDER_ID", "")
        receiver_id = tx.get("RECEIVER_ID", "")
        score = state.get("risk_score", 0)
        narrative = state.get("sar_narrative", "")
        alert_id = state.get("alert_id", f"ALT-{tx_id[-6:]}")

        filing_ref = f"SAR-DB2-{datetime.utcnow().strftime('%Y%m%d')}-{tx_id[-6:]}-{uuid.uuid4().hex[:4]}"

        if rec_action == "CLEAR_ALERT":
            state["supervisor_decision"] = "APPROVED_CLEARANCE"
            state["supervisor_notes"] = "Transaction vetted and cleared. Low risk profile verified."
            log_msg = f"Alert {alert_id} cleared by supervisor."
        elif rec_action == "FREEZE_AND_FILE_SAR":
            if auto_approve:
                # 1. Execute Account Freeze in Db2
                freeze_account(receiver_id, f"Db2 Sentinel Automated Risk Freeze: Score {score}/100", self.name)
                # 2. File Official Regulatory SAR in Db2
                sar_id = f"SAR-{datetime.utcnow().strftime('%H%M%S')}-{uuid.uuid4().hex[:4]}"
                save_sar_filing(
                    sar_id=sar_id,
                    alert_id=alert_id,
                    filing_ref=filing_ref,
                    primary_suspect=tx.get("RECEIVER_NAME", receiver_id),
                    narrative=narrative,
                    risk_score=score,
                    filed_by=self.name,
                )
                state["supervisor_decision"] = "APPROVED_ENFORCEMENT"
                state["supervisor_notes"] = f"Account {receiver_id} frozen in Db2. Official SAR filed ({filing_ref})."
                log_msg = f"CRITICAL ACTION EXECUTED: Account {receiver_id} FROZEN. SAR filed to Db2."
            else:
                state["supervisor_decision"] = "PENDING_HUMAN_REVIEW"
                state["supervisor_notes"] = "High-risk case queued for human compliance officer sign-off."
                log_msg = f"Alert {alert_id} queued for human officer review."
        else:
            state["supervisor_decision"] = "ENHANCED_MONITORING"
            state["supervisor_notes"] = "Transaction flagged for 30-day enhanced surveillance."
            log_msg = f"Alert {alert_id} placed under enhanced monitoring."

        # Cryptographic Audit Signature
        sig = append_audit_trail(
            self.name,
            "SUPERVISOR_DECISION",
            {
                "tx_id": tx_id,
                "decision": state["supervisor_decision"],
                "notes": state["supervisor_notes"],
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        state["audit_signature"] = sig

        state["agent_logs"].append({
            "agent": self.name,
            "message": log_msg,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return state
