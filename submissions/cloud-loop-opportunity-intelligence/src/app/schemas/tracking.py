from pydantic import BaseModel, Field
from typing import Optional, List
from backend.app.schemas.opportunity import OpportunityResponse

class TrackingCreate(BaseModel):
    opportunity_id: str
    application_status: str = Field("saved", description="saved, applied, under_review, not_interested")
    bookmarked: bool = True

class TrackingItem(BaseModel):
    user_id: str
    opportunity_id: str
    application_status: str
    bookmarked: bool
    updated_at: Optional[str] = None
    opportunity: Optional[OpportunityResponse] = None

class TrackingResponse(BaseModel):
    items: List[TrackingItem]
    total_saved: int
    total_applied: int
    total_review: int

