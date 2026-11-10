"""
Evidence ledger models ensuring traceability of every assertion.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    source: str  # e.g., "SYSCAT.COLUMNS", "SYSCAT.REFERENCES", "SYSCAT.INDEXES", "SCHEMA_ANALYZER"
    observation: str
    type: str  # "catalog_metadata", "declared_relationship", "naming_pattern", "structural_constraint"


class EvidenceClaim(BaseModel):
    claim: str
    evidence: List[EvidenceItem] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    status: str  # "verified_fact", "metadata_supported", "ai_hypothesis", "unverified_assumption"
    verified_by_engine: bool = False
    referenced_tables: List[str] = Field(default_factory=list)
    referenced_columns: List[str] = Field(default_factory=list)
    discrepancies: List[str] = Field(default_factory=list)
