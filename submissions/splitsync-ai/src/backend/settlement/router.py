"""Settlement API routes."""

from fastapi import APIRouter, Depends

from auth.dependencies import get_current_user
from settlement.schemas import UpdateSettlementItemRequest
from settlement.service import settlement_service

router = APIRouter(prefix="/groups/{group_id}/settlements", tags=["Settlement"])


@router.post("")
def calculate_settlement(
    group_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Trigger a new optimal settlement calculation for a group."""
    return settlement_service.calculate_settlement(
        group_id=group_id,
        user_id=current_user["user_id"],
    )


@router.get("/latest")
def get_latest_settlement(
    group_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Fetch the latest settlement recommendations for a group."""
    return settlement_service.get_latest_settlement(
        group_id=group_id,
        user_id=current_user["user_id"],
    )


@router.get("")
def list_settlement_runs(
    group_id: str,
    current_user: dict = Depends(get_current_user),
):
    """List historical settlement runs for a group."""
    return settlement_service.list_settlement_runs(
        group_id=group_id,
        user_id=current_user["user_id"],
    )


@router.patch("/{run_id}/items/{item_id}")
def update_settlement_item(
    group_id: str,
    run_id: str,
    item_id: str,
    body: UpdateSettlementItemRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update status of an individual settlement transfer (e.g. mark as SETTLED)."""
    return settlement_service.mark_item_settled(
        group_id=group_id,
        run_id=run_id,
        item_id=item_id,
        user_id=current_user["user_id"],
        status=body.status,
    )
