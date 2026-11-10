"""Typed definition of the shared LangGraph workflow state.

The state is a flat dictionary that is passed from node to node.  Each
agent reads the keys it needs, writes its own output keys, and returns the
(updated) dictionary.  All keys are optional except the initial `reading_id`
required to start the workflow.
"""

from typing import TypedDict, List, Dict, Any, Optional


class WorkflowState(TypedDict, total=False):

    # Input from FastAPI
    reading_id: int

    # Monitoring Agent outputs
    sensor: Dict[str, Any]
    shipment: Dict[str, Any]
    product: Dict[str, Any]
    temperature_status: str
    temperature_deviation: float
    is_violation: bool

    # Incident Agent outputs
    incident_id: Optional[int]
    incident_created: bool
    severity: Optional[str]

    # Risk Assessment Agent outputs
    risk_assessment_id: Optional[int]
    risk_score: Optional[float]
    risk_level: Optional[str]
    risk_explanation: Optional[str]

    # CrewAI analysis. Explanatory only; it does not replace risk_score.
    crew_analysis: Optional[Dict[str, Any]]
    crew_status: Optional[str]
    crew_error: Optional[str]
    risk_reused: bool

    # Recommendation Agent outputs
    recommendations: List[Dict[str, Any]]
    recommendation_ids: List[int]
    recommendations_generated: bool

    # Workflow metadata
    stage: str
    error: Optional[str]
    status: str  # RUNNING, SUCCESS, SKIPPED, FAILED