"""Settlement request and response schemas."""

from typing import Optional
from pydantic import BaseModel, Field


class SettlementItemResponse(BaseModel):
    """Single transfer recommendation."""

    item_id: str
    run_id: str
    from_member_id: str
    to_member_id: str
    amount_minor: int
    status: str
    from_name: Optional[str] = None
    from_email: Optional[str] = None
    to_name: Optional[str] = None
    to_email: Optional[str] = None


class SettlementRunResponse(BaseModel):
    """Settlement run header with transfer items."""

    run_id: str
    group_id: str
    total_minor: int
    currency: str
    status: str
    calculated_at: str
    calculated_by: str
    calculated_by_name: Optional[str] = None
    items: list[SettlementItemResponse] = []


class UpdateSettlementItemRequest(BaseModel):
    """Payload for updating settlement item status."""

    status: str = Field(..., description="Target status (e.g. SETTLED)")
