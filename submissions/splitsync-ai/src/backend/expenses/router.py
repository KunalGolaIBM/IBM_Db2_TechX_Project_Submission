"""Expense API routes."""

from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from expenses.service import expense_service

router = APIRouter(prefix="/groups/{group_id}/expenses", tags=["Expenses"])


class CreateExpenseRequest(BaseModel):
    """Payload for recording a group expense."""

    amount_minor: int = Field(..., gt=0, description="Expense amount in integer paise")
    description: str = Field(..., min_length=1, max_length=500, description="Description of expense")
    category: str = Field("OTHER", max_length=50, description="Category code (e.g. FOOD, TRAVEL)")
    payment_method: str = Field("DIGITAL", description="Method: DIGITAL or CASH")
    participant_member_ids: Optional[list[str]] = Field(
        None, description="Optional list of member IDs participating in split"
    )
    expense_date: Optional[str] = Field(None, description="Date of expense in YYYY-MM-DD format")


@router.post("")
def create_expense(
    group_id: str,
    body: CreateExpenseRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new group expense with equal split calculations."""
    return expense_service.create_expense(
        group_id=group_id,
        user_id=current_user["user_id"],
        amount_minor=body.amount_minor,
        description=body.description,
        category=body.category,
        payment_method=body.payment_method,
        participant_member_ids=body.participant_member_ids,
        expense_date=body.expense_date,
    )


@router.get("")
def list_expenses(
    group_id: str,
    current_user: dict = Depends(get_current_user),
):
    """List all recorded expenses for a group."""
    return expense_service.list_expenses(
        group_id=group_id,
        user_id=current_user["user_id"],
    )


@router.get("/{expense_id}")
def get_expense(
    group_id: str,
    expense_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get full details and split allocations for an expense."""
    return expense_service.get_expense_details(
        group_id=group_id,
        expense_id=expense_id,
        user_id=current_user["user_id"],
    )
