"""Cash API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from cash.service import cash_service

router = APIRouter(prefix="/groups/{group_id}/cash", tags=["Cash"])


class SubmitCashRequest(BaseModel):
    """Payload for submitting a cash contribution."""

    amount_minor: int = Field(..., gt=0, description="Amount in integer paise")
    description: Optional[str] = Field(None, max_length=500, description="Optional description of contribution")


@router.post("")
def submit_cash(
    group_id: str,
    body: SubmitCashRequest,
    current_user: dict = Depends(get_current_user),
):
    """Submit a cash contribution awaiting approval."""
    return cash_service.submit_cash(
        group_id=group_id,
        user_id=current_user["user_id"],
        amount_minor=body.amount_minor,
        description=body.description,
    )


@router.get("")
def list_cash(
    group_id: str,
    status: Optional[str] = Query(None, description="Optional status filter"),
    current_user: dict = Depends(get_current_user),
):
    """List cash contributions for a group."""
    return cash_service.list_cash(
        group_id=group_id,
        user_id=current_user["user_id"],
        status=status,
    )
