"""Inventory API routes."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from recipe_waste_optimizer.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventorySummary
)
from recipe_waste_optimizer.db.repositories.inventory_repo import InventoryRepository
from recipe_waste_optimizer.config import settings

router = APIRouter(prefix="/inventory", tags=["Household Inventory"])
repo = InventoryRepository()


@router.get("", response_model=List[InventoryItemResponse])
def get_inventory(
    household_id: Optional[str] = Query(None, description="Household ID filter"),
    status: str = Query("available", description="Inventory status filter")
):
    """Retrieve all current inventory items for household."""
    hid = household_id or settings.DEFAULT_HOUSEHOLD_ID
    return repo.list_inventory(hid, status=status)


@router.post("", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    item: InventoryItemCreate,
    household_id: Optional[str] = Query(None)
):
    """Add a new item to household inventory stock."""
    hid = household_id or settings.DEFAULT_HOUSEHOLD_ID
    try:
        created = repo.add_inventory_item(
            household_id=hid,
            ingredient_name=item.ingredient_name,
            quantity=item.quantity,
            unit=item.unit,
            storage_location=item.storage_location,
            purchase_date=item.purchase_date,
            expiry_date=item.expiry_date
        )
        return created
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to record inventory item: {e}")


@router.patch("/{inventory_id}", response_model=InventoryItemResponse)
def update_inventory_item(
    inventory_id: int,
    updates: InventoryItemUpdate,
    household_id: Optional[str] = Query(None)
):
    """Update stock quantity, location, or expiry date."""
    hid = household_id or settings.DEFAULT_HOUSEHOLD_ID
    updated = repo.update_inventory_item(
        inventory_id=inventory_id,
        household_id=hid,
        quantity=updates.quantity,
        unit=updates.unit,
        storage_location=updates.storage_location,
        expiry_date=updates.expiry_date,
        status=updates.status
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    return updated


@router.delete("/{inventory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(
    inventory_id: int,
    household_id: Optional[str] = Query(None)
):
    """Remove or discard an inventory item."""
    hid = household_id or settings.DEFAULT_HOUSEHOLD_ID
    success = repo.delete_inventory_item(inventory_id, hid)
    if not success:
        raise HTTPException(status_code=404, detail="Inventory item not found.")
    return None


@router.get("/summary", response_model=InventorySummary)
def get_inventory_summary(household_id: Optional[str] = Query(None)):
    """Summary of perishable ingredients grouped by urgency."""
    hid = household_id or settings.DEFAULT_HOUSEHOLD_ID
    items = repo.list_inventory(hid, status="available")
    urgent = sum(1 for i in items if i.get("expiry_status") == "urgent")
    approaching = sum(1 for i in items if i.get("expiry_status") == "approaching")
    safe = sum(1 for i in items if i.get("expiry_status") == "safe")
    expired = sum(1 for i in items if i.get("expiry_status") == "expired")

    return InventorySummary(
        total_items=len(items),
        urgent_count=urgent,
        approaching_count=approaching,
        safe_count=safe,
        expired_count=expired
    )
