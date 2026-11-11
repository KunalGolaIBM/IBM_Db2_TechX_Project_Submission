from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Union
import json

class OpportunityBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    org: str = Field(..., min_length=1, max_length=120)
    kind: str = Field(..., description="job, internship, event, program, certification")
    location: Optional[str] = "India / Remote"
    mode: Optional[str] = Field("onsite", description="remote, hybrid, onsite")
    deadline: Optional[str] = None
    posted: Optional[str] = None
    apply_url: str = Field(..., description="Application URL")
    source: str = Field("curated", description="curated or synthetic-demo")
    skills: List[str] = Field(default_factory=list)
    description: Optional[str] = None

    @field_validator("skills", mode="before")
    @classmethod
    def parse_skills(cls, v: Union[str, list, None]) -> List[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(item).strip() for item in v if item]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if item]
                except Exception:
                    pass
            return [s.strip() for s in v.split(",") if s.strip()]
        return []

class OpportunityCreate(OpportunityBase):
    id: Optional[str] = None
    slug: Optional[str] = None

class OpportunityResponse(OpportunityBase):
    id: str
    slug: str
    updated_at: Optional[str] = None

    model_config = {"populate_by_name": True, "from_attributes": True}

class OpportunityListResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: List[OpportunityResponse]
