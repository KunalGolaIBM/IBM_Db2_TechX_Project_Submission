from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List
from datetime import datetime

class OpportunityBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    organization: str = Field(..., min_length=1, max_length=128)
    opportunity_type: str = Field(..., description="program, internship, job, event, certification")
    category: str = Field(..., max_length=64)
    description: Optional[str] = None
    location: Optional[str] = None
    location_type: Optional[str] = Field("remote", description="remote, onsite, hybrid")
    skills: Optional[List[str]] = Field(default_factory=list)
    eligibility: Optional[str] = None
    deadline: Optional[str] = None
    application_url: str = Field(..., description="Direct link to apply")
    source_name: Optional[str] = "CloudLoop Indexer"
    source_url: Optional[str] = None
    verification_status: Optional[str] = "verified"

class OpportunityCreate(OpportunityBase):
    slug: Optional[str] = None

class OpportunityResponse(OpportunityBase):
    id: str
    slug: str
    fetched_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}

class OpportunityListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[OpportunityResponse]

