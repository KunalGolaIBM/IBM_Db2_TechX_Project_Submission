"""
Graph Risk & Network Topology Agent for Db2 Sentinel AI.
Executes recursive SQL queries in IBM Db2 to uncover circular fund routing,
multi-hop layering chains, and money mule network convergence.
"""

from datetime import datetime
from typing import Dict, Any

from src.agents.state import SentinelState
from src.db.queries import detect_circular_routing_paths, append_audit_trail


class GraphRiskAgent:
    """Analyzes transaction graph topologies and circular routing cycles."""

    def __init__(self):
        self.name = "GraphRiskAgent"

    def run(self, state: SentinelState) -> SentinelState:
        tx = state.get("transaction_data", {})
        sender_id = tx.get("SENDER_ID", "")
        tx_id = tx.get("TX_ID", "")

        # Execute Db2 Recursive CTE query to trace circular routing
        cycles = detect_circular_routing_paths(sender_id, max_depth=4)

        current_score = state.get("risk_score", 30)
        if cycles:
            # Significant layering indicator
            current_score = max(current_score, 92)
            log_msg = f"CIRCULAR ROUTING DETECTED: {len(cycles)} closed fund loop(s) identified starting at {sender_id}."
        else:
            log_msg = f"Network graph traversal completed in Db2. No closed circular loops detected from {sender_id}."

        state["circular_loops"] = cycles
        state["risk_score"] = min(current_score, 100)

        state["agent_logs"].append({
            "agent": self.name,
            "message": log_msg,
            "timestamp": datetime.utcnow().isoformat(),
        })

        append_audit_trail(
            self.name,
            "GRAPH_CYCLE_ANALYSIS",
            {"tx_id": tx_id, "sender_id": sender_id, "cycles_found": len(cycles)},
        )

        return state
