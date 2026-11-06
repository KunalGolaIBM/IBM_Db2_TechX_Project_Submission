"""
Forensic Investigator Agent for Db2 Sentinel AI.
Executes vector similarity search on IBM Db2 for AML typologies,
retrieves historical account velocity, and gathers transactional evidence.
"""

from datetime import datetime
from typing import Dict, Any

from src.agents.state import SentinelState
from src.db.connection import get_db_manager
from src.db.queries import detect_velocity_and_structuring, append_audit_trail
from src.utils.embeddings import get_embedding_service


class ForensicInvestigatorAgent:
    """Performs deep database forensics and semantic vector analysis."""

    def __init__(self):
        self.name = "ForensicInvestigatorAgent"
        self.db = get_db_manager()
        self.emb_service = get_embedding_service()

    def run(self, state: SentinelState) -> SentinelState:
        tx = state.get("transaction_data", {})
        tx_id = tx.get("TX_ID", "UNKNOWN")
        memo = tx.get("MEMO", "")
        sender_id = tx.get("SENDER_ID", "")
        receiver_id = tx.get("RECEIVER_ID", "")

        # 1. Semantic Vector Search against Db2 AML Typologies
        query_vector = self.emb_service.embed_text(memo)
        matched_typologies = self.db.vector_search_typologies(
            query_vector=query_vector,
            top_k=2,
            min_similarity=0.25,
        )

        # 2. Window Function Aggregation for Historical Velocity & Structuring
        structuring_evidence = detect_velocity_and_structuring(receiver_id)

        # Score Adjustment
        current_score = state.get("risk_score", 30)
        if matched_typologies:
            top_match = matched_typologies[0]
            current_score = max(current_score, 70 + int(top_match["SIMILARITY"] * 25))

        if structuring_evidence.get("is_structuring_suspect"):
            current_score = max(current_score, 85)

        state["matched_typologies"] = matched_typologies
        state["structuring_evidence"] = structuring_evidence
        state["risk_score"] = min(current_score, 100)

        log_msg = (
            f"Forensic queries executed in Db2. "
            f"Vector matches: {[t['TITLE'] for t in matched_typologies]}. "
            f"Structuring cluster suspect: {structuring_evidence.get('is_structuring_suspect')}."
        )
        state["agent_logs"].append({
            "agent": self.name,
            "message": log_msg,
            "timestamp": datetime.utcnow().isoformat(),
        })

        append_audit_trail(
            self.name,
            "FORENSIC_DB2_ANALYSIS",
            {
                "tx_id": tx_id,
                "matched_typologies": [t["CODE"] for t in matched_typologies],
                "structuring_cluster": structuring_evidence.get("is_structuring_suspect"),
            },
        )

        return state
