"""
Relationship models: Declared (verified facts) vs Inferred (evidence-backed hypotheses).
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    DECLARED = "DECLARED"  # Established by SYSCAT.REFERENCES
    INFERRED = "INFERRED"  # Discovered via naming/type/structural patterns


class VerificationStatus(str, Enum):
    VERIFIED_FACT = "VERIFIED_FACT"        # Backed by catalog foreign key
    METADATA_SUPPORTED = "METADATA_SUPPORTED"  # Supported by high naming/type correlation
    HYPOTHESIS_UNVERIFIED = "HYPOTHESIS_UNVERIFIED"  # Preliminary candidate
    REJECTED = "REJECTED"              # Disproved by schema mismatch


class RelationshipEdge(BaseModel):
    id: str
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    relationship_type: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    evidence_notes: List[str] = Field(default_factory=list)
    constraint_name: Optional[str] = None
    verification_status: VerificationStatus

    @property
    def is_fact(self) -> bool:
        return self.relationship_type == RelationshipType.DECLARED
