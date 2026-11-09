from pydantic import BaseModel, Field
from typing import Optional, List

class StudentProfileBase(BaseModel):
    education: Optional[str] = Field(None, description="Institute name or university")
    degree: Optional[str] = Field("B.Tech / B.E.", description="Degree program")
    study_year: int = Field(3, ge=1, le=5, description="Current study year (1-5)")
    graduation_batch: Optional[str] = Field("2026", description="Expected graduation year")
    skills: List[str] = Field(default_factory=list, description="List of technical skills")
    interests: List[str] = Field(default_factory=list, description="Career interests")
    preferred_domains: List[str] = Field(default_factory=list, description="Target technical domains")
    preferred_locations: List[str] = Field(default_factory=list, description="Target locations or remote")

class StudentProfileCreate(StudentProfileBase):
    pass

class StudentProfileResponse(StudentProfileBase):
    user_id: str
    updated_at: Optional[str] = None

    model_config = {"from_attributes": True}

