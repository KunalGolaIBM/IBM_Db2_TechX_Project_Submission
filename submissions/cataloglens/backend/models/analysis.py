"""
Analysis and Investigation models for CatalogLens.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from .relationship import RelationshipEdge
from .evidence import EvidenceClaim


class ColumnRole(BaseModel):
    column_name: str
    role_description: str
    significance: str  # "PRIMARY_IDENTIFIER", "FOREIGN_LINK", "BUSINESS_METRIC", "STATUS_CODE", "AUDIT"


class TableUnderstanding(BaseModel):
    table_name: str
    likely_business_purpose: str
    important_columns: List[ColumnRole] = Field(default_factory=list)
    relationships_summary: List[str] = Field(default_factory=list)
    likely_business_workflow: str
    evidence: List[EvidenceClaim] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    verification_questions: List[str] = Field(default_factory=list)
    is_ai_generated: bool = False
    model_used: Optional[str] = None
    generated_at: str = ""


class WorkflowGroup(BaseModel):
    workflow_id: str
    name: str
    description: str
    tables: List[str] = Field(default_factory=list)
    sequence_steps: List[str] = Field(default_factory=list)
    supporting_relationships: List[RelationshipEdge] = Field(default_factory=list)
    confidence: float = 0.85
    uncertainties: List[str] = Field(default_factory=list)


class DependencyImpact(BaseModel):
    entity: str
    entity_type: str  # "TABLE", "COLUMN", "VIEW"
    relationship_kind: str  # "DIRECT_FOREIGN_KEY", "INFERRED_REFERENCE", "VIEW_DEPENDENCY", "INDIRECT_CHILD"
    impact_level: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    description: str


class DependencyInvestigation(BaseModel):
    target_object: str  # e.g., "ORD_HDR" or "ORD_HDR.CUSTOMER_ID"
    object_type: str    # "TABLE" or "COLUMN"
    direct_dependencies: List[DependencyImpact] = Field(default_factory=list)
    indirect_dependencies: List[DependencyImpact] = Field(default_factory=list)
    verified_relationships: List[RelationshipEdge] = Field(default_factory=list)
    potential_impact_areas: List[str] = Field(default_factory=list)
    impact_severity: str = "MEDIUM"  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    evidence: List[EvidenceClaim] = Field(default_factory=list)
    recommended_manual_checks: List[str] = Field(default_factory=list)
    investigated_at: str = ""
