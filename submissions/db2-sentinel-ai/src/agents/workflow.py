"""
LangGraph Multi-Agent Workflow Orchestrator for Db2 Sentinel AI.
Constructs and compiles the cyclical agent state machine, persists checkpoints to IBM Db2,
and manages execution routing from transaction interception to regulatory filing.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from src.agents.state import SentinelState
from src.agents.screening_agent import ScreeningAgent
from src.agents.investigator_agent import ForensicInvestigatorAgent
from src.agents.graph_risk_agent import GraphRiskAgent
from src.agents.sar_drafter_agent import SARDrafterAgent
from src.agents.supervisor_agent import SupervisorAgent
from src.db.checkpointer import Db2AgentCheckpointer
from src.db.queries import get_transaction_by_id


class SentinelWorkflow:
    """Orchestrates multi-agent execution pipeline with Db2 state persistence."""

    def __init__(self):
        self.screening_agent = ScreeningAgent()
        self.investigator_agent = ForensicInvestigatorAgent()
        self.graph_risk_agent = GraphRiskAgent()
        self.sar_drafter_agent = SARDrafterAgent()
        self.supervisor_agent = SupervisorAgent()
        self.checkpointer = Db2AgentCheckpointer()
        self._compiled_graph = None
        self._try_build_langgraph()

    def _try_build_langgraph(self):
        """Attempts to build and compile the native LangGraph StateGraph."""
        try:
            from langgraph.graph import StateGraph, START, END

            workflow = StateGraph(SentinelState)

            # Define Nodes
            workflow.add_node("screening", self.screening_agent.run)
            workflow.add_node("investigation", self.investigator_agent.run)
            workflow.add_node("graph_risk", self.graph_risk_agent.run)
            workflow.add_node("sar_drafting", self.sar_drafter_agent.run)
            workflow.add_node("supervisor", lambda s: self.supervisor_agent.run(s, auto_approve=True))

            # Define Linear / Conditional Flow
            workflow.add_edge(START, "screening")
            workflow.add_edge("screening", "investigation")
            workflow.add_edge("investigation", "graph_risk")
            workflow.add_edge("graph_risk", "sar_drafting")
            workflow.add_edge("sar_drafting", "supervisor")
            workflow.add_edge("supervisor", END)

            self._compiled_graph = workflow.compile()
        except Exception:
            self._compiled_graph = None

    def run_investigation(
        self,
        tx_id: str,
        alert_id: Optional[str] = None,
        auto_approve: bool = True,
    ) -> SentinelState:
        """
        Executes an end-to-end multi-agent investigation on a transaction.
        Persists state checkpoints to IBM Db2 at each transition.
        """
        tx = get_transaction_by_id(tx_id)
        if not tx:
            raise ValueError(f"Transaction ID '{tx_id}' not found in Db2.")

        thread_id = f"sentinel-{tx_id}-{uuid.uuid4().hex[:6]}"
        initial_alert_id = alert_id or f"ALT-{tx_id[-6:]}"

        state: SentinelState = {
            "thread_id": thread_id,
            "step_num": 0,
            "alert_id": initial_alert_id,
            "tx_id": tx_id,
            "transaction_data": tx,
            "risk_score": 0,
            "screening_flags": [],
            "matched_sanctions": [],
            "matched_typologies": [],
            "circular_loops": [],
            "structuring_evidence": {},
            "agent_logs": [],
            "sar_narrative": "",
            "recommended_action": "",
            "supervisor_decision": "",
            "supervisor_notes": "",
            "audit_signature": None,
        }

        # Step 1: Screening Node
        state["step_num"] = 1
        state = self.screening_agent.run(state)
        self.checkpointer.save_checkpoint(thread_id, 1, self.screening_agent.name, state)

        # Step 2: Forensic Investigator Node
        state["step_num"] = 2
        state = self.investigator_agent.run(state)
        self.checkpointer.save_checkpoint(thread_id, 2, self.investigator_agent.name, state)

        # Step 3: Graph Risk Node
        state["step_num"] = 3
        state = self.graph_risk_agent.run(state)
        self.checkpointer.save_checkpoint(thread_id, 3, self.graph_risk_agent.name, state)

        # Step 4: SAR Drafter Node
        state["step_num"] = 4
        state = self.sar_drafter_agent.run(state)
        self.checkpointer.save_checkpoint(thread_id, 4, self.sar_drafter_agent.name, state)

        # Step 5: Supervisor Approval Node
        state["step_num"] = 5
        state = self.supervisor_agent.run(state, auto_approve=auto_approve)
        self.checkpointer.save_checkpoint(thread_id, 5, self.supervisor_agent.name, state)

        return state
