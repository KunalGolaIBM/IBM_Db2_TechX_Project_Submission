"""Pydantic schemas for Inventory."""
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator


class InventoryItemBase(BaseModel):
    ingredient_name: str = Field(..., description="Name of the ingredient (e.g. spinach, tomato)")
    quantity: float = Field(..., gt=0, description="Quantity available in stock")
    unit: str = Field(..., description="Measurement unit (e.g. g, kg, pieces, cloves, ml)")
    storage_location: Literal["fridge", "freezer", "pantry", "counter"] = "fridge"
    purchase_date: Optional[date] = None
    expiry_date: Optional[date] = None


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    quantity: Optional[float] = Field(None, gt=0)
    unit: Optional[str] = None
    storage_location: Optional[Literal["fridge", "freezer", "pantry", "counter"]] = None
    expiry_date: Optional[date] = None
    status: Optional[Literal["available", "consumed", "discarded"]] = None


class InventoryItemResponse(BaseModel):
    inventory_id: int
    household_id: str
    ingredient_id: int
    ingredient_name: str
    category: str
    quantity: float
    unit: str
    storage_location: str
    purchase_date: Optional[date] = None
    expiry_date: Optional[date] = None
    days_until_expiry: Optional[int] = None
    expiry_status: Literal["expired", "urgent", "approaching", "safe", "unknown"] = "unknown"
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InventorySummary(BaseModel):
    total_items: int
    urgent_count: int  # <= 2 days
    approaching_count: int  # 3-5 days
    safe_count: int
    expired_count: int
