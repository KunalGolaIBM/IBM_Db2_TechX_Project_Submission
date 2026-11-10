"""
LangGraph State Definition for CatalogLens Investigation Workflow.
Maintains state across the 6-step agentic investigation pipeline.
Passes typed metadata, evidence claims, AI hypotheses, and validation results.
"""
from typing import Any, Dict, List, Optional, TypedDict
from ..models.schema import DbSchemaMetadata
from ..models.relationship import RelationshipEdge
from ..models.evidence import EvidenceClaim
from ..models.analysis import TableUnderstanding


class InvestigationState(TypedDict):
    # Inputs
    schema_name: str
    selected_table: str
    investigation_question: Optional[str]
    use_demo: bool

    # Retrieved & Structured Metadata
    metadata: Optional[DbSchemaMetadata]
    declared_relationships: List[RelationshipEdge]
    inferred_relationships: List[RelationshipEdge]
    table_evidence_ledger: List[EvidenceClaim]

    # AI Reasoning
    ai_understanding: Optional[TableUnderstanding]

    # Deterministic Validation
    validated_evidence: List[EvidenceClaim]
    discrepancies: List[str]

    # Final Output
    final_report: Optional[Dict[str, Any]]
    errors: List[str]
