"""
Screening Agent for Db2 Sentinel AI.
Performs real-time rule screening, sanctions list cross-referencing,
and rapid threshold checks against IBM Db2 ledgers.
"""

from datetime import datetime
from typing import Dict, Any

from src.agents.state import SentinelState
from src.db.queries import match_sanctions, append_audit_trail


class ScreeningAgent:
    """Evaluates transactions against strict regulatory rules and watchlists."""

    def __init__(self):
        self.name = "ScreeningAgent"

    def run(self, state: SentinelState) -> SentinelState:
        tx = state.get("transaction_data", {})
        tx_id = tx.get("TX_ID", "UNKNOWN")
        memo = tx.get("MEMO", "")
        sender_name = tx.get("SENDER_NAME", "")
        receiver_name = tx.get("RECEIVER_NAME", "")
        amount = float(tx.get("AMOUNT", 0.0))

        flags = []
        base_score = 20

        # 1. Sanctions Watchlist Screening
        sanctions_hits = match_sanctions(memo, [sender_name, receiver_name])
        if sanctions_hits:
            for s in sanctions_hits:
                flags.append(f"CRITICAL SANCTION HIT: Entity '{s['NAME']}' ({s['CATEGORY']}) matched in watchlist.")
            base_score = max(base_score, 95)

        # 2. Structuring / Sub-threshold Wire Check
        if 9000.0 <= amount <= 9999.0:
            flags.append(f"STRUCTURING INDICATOR: Amount ${amount:,.2f} is just below the $10,000 regulatory reporting threshold.")
            base_score = max(base_score, 75)

        # 3. High-Risk Jurisdiction Check
        sender_jur = tx.get("SENDER_JURISDICTION", "")
        receiver_jur = tx.get("RECEIVER_JURISDICTION", "")
        high_risk_jurisdictions = ["British Virgin Islands", "Seychelles", "UAE - Free Zone", "Russia", "Yemen / Syria"]
        if any(j in sender_jur for j in high_risk_jurisdictions) or any(j in receiver_jur for j in high_risk_jurisdictions):
            flags.append(f"SECRECY JURISDICTION: Transfer involves offshore territory ({sender_jur} -> {receiver_jur}).")
            base_score += 15

        # Update State
        state["screening_flags"] = flags
        state["matched_sanctions"] = sanctions_hits
        state["risk_score"] = min(base_score, 100)

        log_entry = {
            "agent": self.name,
            "message": f"Screening complete for {tx_id}. Score: {state['risk_score']}. Flags: {len(flags)}.",
            "timestamp": datetime.utcnow().isoformat(),
        }
        state["agent_logs"].append(log_entry)

        append_audit_trail(
            self.name,
            "SCREEN_TRANSACTION",
            {"tx_id": tx_id, "score": state["risk_score"], "flags": flags},
        )

        return state
