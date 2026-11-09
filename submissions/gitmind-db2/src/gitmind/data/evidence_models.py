"""
GitMind 2.0 — Grounded Evidence and Agent Output Models

Structured schemas for agent findings, evidence citations, and verified answers:
- Traceable artifact, commit, file, and line citations
- Grounding verification flags (VERIFIED, INFERRED, UNGROUNDED)
- Machine-auditable engineering findings
"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    INFERRED = "INFERRED"
    UNGROUNDED = "UNGROUNDED"
    UNAVAILABLE = "UNAVAILABLE"


class EvidenceReference(BaseModel):
    """A verified citation pointing to repository artifacts or historical records."""
    artifact_id: Optional[str] = Field(None, description="Db2 artifact identifier if indexed")
    artifact_type: str = Field(..., description="commit, file, function, pr, issue, doc, or test")
    commit_sha: Optional[str] = Field(None, description="Full or short commit hash")
    file_path: Optional[str] = Field(None, description="Relative file path in repository")
    start_line: Optional[int] = Field(None, description="Starting line number")
    end_line: Optional[int] = Field(None, description="Ending line number")
    source_url: Optional[str] = Field(None, description="URL or permalink if available")
    content_hash: Optional[str] = Field(None, description="SHA-256 hash of referenced content")
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.INFERRED,
        description="Verification state determined by evidence validation layer"
    )
    verification_note: Optional[str] = Field(None, description="Reason if marked ungrounded or verified")


class AgentFinding(BaseModel):
    """Structured conclusion produced by an agent with grounded evidence."""
    agent_name: str = Field(..., description="Agent name producing the finding")
    finding_type: str = Field(
        ...,
        description="Category: REGRESSION_RISK, HISTORICAL_BUG_FIX, REVERT_PRECEDENT, ARCHITECTURE_DECISION, UNRESOLVED_RECOMMENDATION"
    )
    title: str = Field(..., description="Concise title of the finding")
    summary: str = Field(..., description="Detailed explanation of the engineering finding")
    severity: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH, CRITICAL")
    evidence: List[EvidenceReference] = Field(default_factory=list, description="List of supporting evidence citations")
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations")


class VerifiedAnswer(BaseModel):
    """Final answer produced by the synthesis and evidence verification pipeline."""
    query: str
    verified_facts: List[str] = Field(default_factory=list)
    historical_inferences: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    evidence: List[EvidenceReference] = Field(default_factory=list)
    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    final_response_markdown: str = ""

