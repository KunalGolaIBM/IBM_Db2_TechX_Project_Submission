"""Payment API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from auth.dependencies import get_current_user
from payments.service import payment_service

router = APIRouter(prefix="/groups/{group_id}/payments", tags=["Payments"])


class DemoPaymentRequest(BaseModel):
    """Request payload for recording a demo UPI payment."""

    amount_minor: int = Field(..., gt=0, description="Payment amount in integer paise")
    provider_txn_id: Optional[str] = Field(None, description="Optional simulated transaction reference")


@router.get("/qr")
def get_payment_qr(
    group_id: str,
    amount_minor: Optional[int] = Query(None, description="Amount in paise to encode"),
    current_user: dict = Depends(get_current_user),
):
    """Generate dynamic UPI QR code for group settlement."""
    return payment_service.generate_qr(group_id=group_id, amount_minor=amount_minor)


@router.post("/demo")
def record_demo_payment(
    group_id: str,
    body: DemoPaymentRequest,
    current_user: dict = Depends(get_current_user),
):
    """Simulate a confirmed UPI payment in demo mode."""
    return payment_service.record_demo_payment(
        group_id=group_id,
        user_id=current_user["user_id"],
        amount_minor=body.amount_minor,
        provider_txn_id=body.provider_txn_id,
    )


@router.get("")
def list_payments(
    group_id: str,
    current_user: dict = Depends(get_current_user),
):
    """List all recorded payment events for a group."""
    return payment_service.list_payments(
        group_id=group_id,
        user_id=current_user["user_id"],
    )


@router.post("/{payment_id}/reverse")
def reverse_payment(
    group_id: str,
    payment_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Reverse a payment event and restore ledger balance (Admin only)."""
    return payment_service.reverse_payment(
        group_id=group_id,
        payment_id=payment_id,
        user_id=current_user["user_id"],
    )

