from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class IngestionRunResponse(BaseModel):
    id: str
    source: str
    records_processed: int
    records_inserted: int
    records_updated: int
    records_rejected: int
    status: str
    error_summary: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

class IngestionBatchRequest(BaseModel):
    source: str = Field(..., description="Dataset provenance source name")
    items: List[Dict[str, Any]]

