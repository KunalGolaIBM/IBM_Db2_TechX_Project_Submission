from typing import TypedDict, List, Dict, Any, Optional

class InvestigationState(TypedDict):
    """
    Typed shared state schema for LangGraph multi-agent security investigation.
    Maintains complete evidence lineage, agent hypotheses, risk calculations,
    and human governance approval tokens.
    """
    incident_id: str
    target_username: str
    target_ip: str
    raw_events: List[Dict[str, Any]]
    associated_alerts: List[Dict[str, Any]]
    evidence_dossier: List[Dict[str, Any]]
    mitre_tactics: List[str]
    attack_hypotheses: List[str]
    factual_findings: List[str]
    risk_evaluation: Dict[str, Any]
    investigation_reports: List[Dict[str, Any]]
    recommended_actions: List[Dict[str, Any]]
    human_approval_required: bool
    human_approval_status: str  # PENDING, APPROVED, REJECTED
    approval_id: Optional[str]
    workflow_status: str        # IN_PROGRESS, AWAITING_APPROVAL, COMPLETED, FAILED
    error: Optional[str]
