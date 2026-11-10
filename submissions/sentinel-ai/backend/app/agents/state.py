from typing import TypedDict, List, Dict, Any, Optional

class SentinelAgentState(TypedDict):
    incident_id: str
    user_id: str
    user_account: Dict[str, Any]
    lookback_hours: int
    raw_logins: List[Dict[str, Any]]
    raw_accesses: List[Dict[str, Any]]
    
    # Agent 1 Outputs
    event_monitoring_findings: Dict[str, Any]
    
    # Agent 2 Outputs
    behaviour_analysis_findings: Dict[str, Any]
    
    # Agent 3 Outputs
    threat_intel_findings: Dict[str, Any]
    
    # Agent 4 Outputs
    risk_assessment_findings: Dict[str, Any]
    
    # Agent 5 Outputs
    incident_response_findings: Dict[str, Any]
    
    # Workflow tracking
    agent_execution_logs: List[Dict[str, Any]]
    status: str

