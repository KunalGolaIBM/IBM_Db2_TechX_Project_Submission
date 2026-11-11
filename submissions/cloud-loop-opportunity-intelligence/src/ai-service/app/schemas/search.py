from pydantic import BaseModel, Field
from typing import Optional, List
from app.schemas.opportunity import OpportunityResponse

class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Natural language opportunity query")
    kind: Optional[str] = Field(None, description="Optional kind filter: job, internship, event, program, certification")
    top_k: int = Field(10, ge=1, le=50, description="Max ranked results to retrieve")

class SemanticSearchResultItem(BaseModel):
    opportunity: OpportunityResponse
    similarity_score: float

class SemanticSearchResponse(BaseModel):
    query: str
    kind: Optional[str] = None
    count: int
    engine: str = "IBM Db2 & Haystack Vector Matcher"
    results: List[SemanticSearchResultItem]
