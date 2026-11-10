"""
MediTwin AI — LangGraph State Definitions
Typed state objects for the workflow graph.
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from ingestion.validation import ExtractedObservation


class MediTwinState(BaseModel):
    """
    Central state object for the MediTwin LangGraph workflow.
    Tracks the full lifecycle of a request.
    """
    # Request classification
    request_type: Optional[Literal["upload", "question", "unknown"]] = None
    raw_input: str = ""

    # Patient context
    patient_id: Optional[int] = None
    patient_info: Optional[Dict[str, Any]] = None

    # Document processing (upload path)
    file_name: Optional[str] = None
    file_bytes: Optional[bytes] = None
    parsed_text: Optional[str] = None
    pages: List[Dict[str, Any]] = Field(default_factory=list)
    document_id: Optional[int] = None
    parse_status: Optional[str] = None
    parse_error: Optional[str] = None

    # Extraction (upload path)
    extracted_observations: List[Dict[str, Any]] = Field(default_factory=list)
    extraction_notes: Optional[str] = None
    validation_errors: List[str] = Field(default_factory=list)

    # Human review gate
    awaiting_review: bool = False
    review_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    observations_saved: int = 0

    # Query processing (question path)
    question: Optional[str] = None
    identified_metric: Optional[str] = None
    identified_test_code: Optional[str] = None
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None

    # Evidence retrieval
    retrieved_records: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_summary: Optional[str] = None

    # Answer generation
    generated_answer: Optional[str] = None
    evidence_cards: List[Dict[str, Any]] = Field(default_factory=list)
    answer_sources: List[Dict[str, Any]] = Field(default_factory=list)

    # Safety
    safety_passed: bool = True
    safety_notes: Optional[str] = None

    # Workflow tracking
    current_node: Optional[str] = None
    completed_nodes: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    final_response: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}

