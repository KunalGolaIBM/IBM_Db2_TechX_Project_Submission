from datetime import date
from typing import Literal
from pydantic import BaseModel, Field

class InventoryItem(BaseModel):
    medicine_id: str
    medicine_name: str
    on_hand: int = Field(ge=0)
    reorder_level: int = Field(ge=0)
    avg_daily_use: float = Field(gt=0)
    supplier_lead_days: int = Field(ge=0)
    nearest_expiry: date | None = None
    expiring_quantity: int = Field(default=0, ge=0)

class RiskFinding(BaseModel):
    medicine_id: str
    medicine_name: str
    days_of_cover: float
    stockout_risk: bool
    expiry_risk: bool
    reasons: list[str]

class Recommendation(BaseModel):
    recommendation_id: str
    medicine_id: str
    medicine_name: str
    suggested_quantity: int
    days_of_cover: float
    rationale: list[str]
    status: Literal["PENDING_REVIEW", "APPROVED", "REJECTED"] = "PENDING_REVIEW"

class ReviewRequest(BaseModel):
    action: Literal["approve", "reject"]
    reviewer: str = Field(min_length=2, max_length=100)
    edited_quantity: int | None = Field(default=None, ge=0)
