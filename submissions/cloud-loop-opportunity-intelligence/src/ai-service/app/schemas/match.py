from pydantic import BaseModel, Field
from typing import Optional, List
from app.schemas.opportunity import OpportunityResponse

class MatchRequest(BaseModel):
    skills: List[str] = Field(..., min_length=1, description="Student technical skills")
    interests: Optional[List[str]] = Field(default_factory=list, description="Career domains or areas of interest")
    year: Optional[str] = Field(None, description="Academic year or graduation batch (e.g. 2026, 3rd year)")
    limit: int = Field(6, ge=1, le=20, description="Max matches to return")

class MatchResultItem(BaseModel):
    opportunity: OpportunityResponse
    match_percentage: float
    why: str
    explanation_mode: str = Field("deterministic", description="'llm' or 'deterministic'")
    matched_skills: List[str] = Field(default_factory=list)

class MatchResponse(BaseModel):
    total_matches: int
    explanation_mode: str
    matches: List[MatchResultItem]
