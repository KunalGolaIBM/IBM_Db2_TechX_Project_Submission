from pydantic import BaseModel, Field
from typing import List, Optional
from app.schemas.opportunity import OpportunityResponse

class MatchExplanation(BaseModel):
    eligibility_met: bool = Field(..., description="Whether academic criteria matches")
    skills_overlap: List[str] = Field(default_factory=list, description="Directly matched skills")
    domain_match: bool = Field(False, description="Whether domain aligns with preferences")
    deadline_status: str = Field("open", description="open, closing_soon, or ongoing")
    summary: str = Field(..., description="Transparent, human-readable match rationale")

class RecommendationItem(BaseModel):
    opportunity: OpportunityResponse
    match_score: float = Field(..., ge=0.0, le=100.0, description="Composite relevance score (0-100%)")
    explanation: MatchExplanation

class RecommendationRequest(BaseModel):
    user_id: Optional[str] = None
    limit: int = Field(6, ge=1, le=50)
    include_ai_explanation: bool = True

class RecommendationResponse(BaseModel):
    count: int
    recommendations: List[RecommendationItem]
    model_used: str = "IBM Db2 Eligibility & Vector Scoring"

