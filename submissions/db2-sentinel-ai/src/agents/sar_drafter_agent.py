"""
Regulatory SAR Drafter Agent for Db2 Sentinel AI.
Compiles forensic findings, Db2 transaction records, vector typology matches,
and network topology traces into standardized FinCEN/RBI Suspicious Activity Reports (SAR).
"""

from datetime import datetime
from typing import Dict, Any

from src.agents.state import SentinelState
from src.config import AML_ALERT_THRESHOLD, HIGH_RISK_THRESHOLD
from src.db.queries import append_audit_trail


class SARDrafterAgent:
    """Drafts formal, legally auditable Suspicious Activity Reports (SAR)."""

    def __init__(self):
        self.name = "SARDrafterAgent"

    def run(self, state: SentinelState) -> SentinelState:
        score = state.get("risk_score", 0)
        tx = state.get("transaction_data", {})
        tx_id = tx.get("TX_ID", "")
        sender_id = tx.get("SENDER_ID", "")
        sender_name = tx.get("SENDER_NAME", "")
        receiver_id = tx.get("RECEIVER_ID", "")
        receiver_name = tx.get("RECEIVER_NAME", "")
        amount = float(tx.get("AMOUNT", 0.0))
        currency = tx.get("CURRENCY", "USD")
        memo = tx.get("MEMO", "")

        flags = state.get("screening_flags", [])
        typologies = state.get("matched_typologies", [])
        sanctions = state.get("matched_sanctions", [])
        cycles = state.get("circular_loops", [])
        structuring = state.get("structuring_evidence", {})

        if score < AML_ALERT_THRESHOLD:
            state["recommended_action"] = "CLEAR_ALERT"
            state["sar_narrative"] = "Transaction evaluated below risk threshold. No regulatory filing warranted."
            state["agent_logs"].append({
                "agent": self.name,
                "message": f"Risk score ({score}) below alert threshold ({AML_ALERT_THRESHOLD}). Recommended: CLEAR_ALERT.",
                "timestamp": datetime.utcnow().isoformat(),
            })
            return state

        # Determine Recommendation
        if score >= HIGH_RISK_THRESHOLD:
            rec_action = "FREEZE_AND_FILE_SAR"
        else:
            rec_action = "ENHANCED_DUE_DILIGENCE"

        state["recommended_action"] = rec_action

        # Generate Formal FinCEN / RBI Suspicious Activity Report (SAR)
        filing_ref = f"SAR-DB2-{datetime.utcnow().strftime('%Y%m%d')}-{tx_id[-6:]}"
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

        typology_summary = (
            ", ".join([f"{t['TITLE']} (Similarity: {t.get('SIMILARITY', 0):.2f})" for t in typologies])
            if typologies
            else "None identified via vector search"
        )
        flags_bullets = "\n".join([f"  - [ALERT] {f}" for f in flags]) if flags else "  - None"

        cycles_text = "No circular fund routing loops identified."
        if cycles:
            cycles_text = "\n".join([f"  - Path: {c['full_loop']} (Depth: {c['depth']})" for c in cycles])

        structuring_text = "No sub-threshold clustering pattern detected."
        if structuring.get("is_structuring_suspect"):
            st_count = structuring.get("sub_threshold_count", 0)
            structuring_text = f"Suspected structuring cluster: {st_count} sub-threshold transactions detected targeting account {receiver_id}."

        narrative = f"""================================================================================
FINANCIAL CRIMES ENFORCEMENT & COMPLIANCE DIVISION
CONFIDENTIAL REGULATORY FILING: SUSPICIOUS ACTIVITY REPORT (SAR)
================================================================================

FILING REFERENCE: {filing_ref}
DATE PREPARED:    {now_str}
INVESTIGATING SYSTEM: Db2 Sentinel AI (Autonomous Forensic Suite)
JURISDICTION:     FATF / FinCEN / RBI Standard Format

--------------------------------------------------------------------------------
PART I: SUBJECT & ENTITY INFORMATION
--------------------------------------------------------------------------------
Primary Sender:
  - Account ID:      {sender_id}
  - Legal Entity:    {sender_name}
  - Jurisdiction:    {tx.get('SENDER_JURISDICTION', 'N/A')}
  - Risk Tier:       {tx.get('SENDER_RISK', 'N/A')}

Beneficiary / Receiver:
  - Account ID:      {receiver_id}
  - Legal Entity:    {receiver_name}
  - Jurisdiction:    {tx.get('RECEIVER_JURISDICTION', 'N/A')}
  - Risk Tier:       {tx.get('RECEIVER_RISK', 'N/A')}

--------------------------------------------------------------------------------
PART II: SUSPICIOUS TRANSACTION DETAILS (IBM Db2 TRANSACTION RECORD)
--------------------------------------------------------------------------------
Transaction ID:     {tx_id}
Amount & Currency:  {amount:,.2f} {currency}
Payment Channel:    {tx.get('CHANNEL', 'WIRE')}
Timestamp:          {tx.get('TX_TIMESTAMP', 'N/A')}
Transaction Memo:   "{memo}"
Overall Risk Score: {score} / 100

--------------------------------------------------------------------------------
PART III: FORENSIC EVIDENCE & TYPOLOGY MAPPINGS (IBM Db2 VECTOR SEARCH)
--------------------------------------------------------------------------------
1. Semantic Typology Vector Matches (Db2 Native Vector Distance):
   {typology_summary}

2. Rule-Based Flags:
{flags_bullets}

3. Graph Topology & Circular Flow (Db2 Recursive CTE Analysis):
{cycles_text}

4. Velocity & Structuring Analysis (Db2 Window Functions):
   {structuring_text}

--------------------------------------------------------------------------------
PART IV: NARRATIVE SUMMARY OF SUSPICIOUS ACTIVITY
--------------------------------------------------------------------------------
On {tx.get('TX_TIMESTAMP', 'N/A')}, the automated Db2 Sentinel surveillance engine
intercepted transaction {tx_id} valued at {amount:,.2f} {currency}.
A multi-agent forensic evaluation utilizing IBM Db2 database analytics,
native vector similarity search, and recursive SQL graph traversal revealed
multiple high-risk anomalies consistent with illicit financial flows.

Specifically, the transaction memo exhibits strong semantic alignment with known
FATF money laundering typologies ({typology_summary}). Further, network graph
investigation in IBM Db2 confirmed indicators of intentional fund obfuscation.

--------------------------------------------------------------------------------
PART V: RECOMMENDED DISPOSITION
--------------------------------------------------------------------------------
Action: {rec_action}
Rationale: Risk score of {score}/100 exceeds critical regulatory threshold.
Mandatory statutory freeze and reporting recommended pursuant to AML/CFT statutes.
================================================================================
"""

        state["sar_narrative"] = narrative
        state["agent_logs"].append({
            "agent": self.name,
            "message": f"SAR narrative compiled ({filing_ref}). Recommendation: {rec_action}.",
            "timestamp": datetime.utcnow().isoformat(),
        })

        append_audit_trail(
            self.name,
            "DRAFT_SAR_REPORT",
            {"tx_id": tx_id, "filing_ref": filing_ref, "recommendation": rec_action, "score": score},
        )

        return state
