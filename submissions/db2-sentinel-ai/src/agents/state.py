"""
State definitions for the Db2 Sentinel AI LangGraph Multi-Agent Workflow.
"""

from typing import TypedDict, List, Dict, Any, Optional


class SentinelState(TypedDict):
    """Execution state shared across all agents in the LangGraph workflow."""

    # Context & Case IDs
    thread_id: str
    step_num: int
    alert_id: str
    tx_id: str
    transaction_data: Dict[str, Any]

    # Forensic Findings
    risk_score: int
    screening_flags: List[str]
    matched_sanctions: List[Dict[str, Any]]
    matched_typologies: List[Dict[str, Any]]
    circular_loops: List[Dict[str, Any]]
    structuring_evidence: Dict[str, Any]

    # Reasoning and Agent Traces
    agent_logs: List[Dict[str, str]]  # list of {agent: str, message: str, timestamp: str}

    # Regulatory Output
    sar_narrative: str
    recommended_action: str  # 'FREEZE_AND_FILE_SAR', 'ENHANCED_DUE_DILIGENCE', 'CLEAR_ALERT'
    supervisor_decision: str  # 'APPROVED', 'REJECTED', 'PENDING'
    supervisor_notes: str
    audit_signature: Optional[str]
