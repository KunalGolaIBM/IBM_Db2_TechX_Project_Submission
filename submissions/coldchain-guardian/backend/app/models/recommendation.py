"""Pydantic models for Recommendation API responses and requests."""

from pydantic import BaseModel, Field
from typing import Optional

class RecommendationBase(BaseModel):
    incident_id: int = Field(..., description="ID of the incident this recommendation refers to")
    action: str = Field(..., description="Human‑readable action suggestion")
    justification: str = Field(..., description="Why this action is suggested")
    priority: int = Field(..., ge=1, description="Priority rank, 1 = highest")

class RecommendationCreate(RecommendationBase):
    pass

class RecommendationOut(RecommendationBase):
    recommendation_id: int = Field(..., description="Database primary key")
    approval_status: Optional[str] = Field(None, description="APPROVED / REJECTED / None")
    created_at: str = Field(..., description="Timestamp of creation")

class RecommendationApproval(BaseModel):
    status: str = Field(..., description="APPROVED or REJECTED")
