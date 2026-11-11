from pydantic import BaseModel, Field
from typing import Optional, List
from app.schemas.opportunity import OpportunityResponse

class TrackRequest(BaseModel):
    user_id: str = Field(..., description="Clerk or Demo User ID")
    opportunity_id: str = Field(..., description="ID of opportunity to track")
    status: str = Field("None", description="Application status: None, Saved, Applied, Interviewing, Accepted, Rejected")
    bookmarked: bool = Field(False, description="Whether bookmarked")

class TrackedOpportunityItem(BaseModel):
    user_id: str
    opportunity_id: str
    status: str
    bookmarked: bool
    updated_at: Optional[str] = None
    opportunity: Optional[OpportunityResponse] = None

class TrackingListResponse(BaseModel):
    user_id: str
    total: int
    items: List[TrackedOpportunityItem]
