"""Group summary and unified transactions history API routes."""

from typing import Optional
from fastapi import APIRouter, Depends, Query

from auth.dependencies import get_current_user
from db.repositories.member_repo import member_repo
from db.repositories.ledger_repo import ledger_repo
from db.repositories.approval_repo import approval_repo
from db.repositories.payment_repo import payment_repo
from db.repositories.cash_repo import cash_repo
from db.repositories.expense_repo import expense_repo
from api.middleware import AppError

router = APIRouter(prefix="/groups/{group_id}", tags=["Summary"])


def _require_membership(group_id: str, user_id: str) -> dict:
    """Verify requesting user is an active member of group."""
    member = member_repo.get_member_by_group_and_user(group_id, user_id)
    if not member:
        raise AppError(403, "Access denied. You are not a member of this group.")
    return member


@router.get("/summary")
def get_group_summary(
    group_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Fetch high-level financial summary, totals, and per-member balances for a group."""
    _require_membership(group_id, current_user["user_id"])

    member_count = member_repo.get_member_count(group_id)
    totals = ledger_repo.get_group_totals(group_id)
    pending_items = approval_repo.get_pending_approvals(group_id)
    balances = ledger_repo.get_member_balances(group_id)

    members_summary = [
        {
            "member_id": b.get("MEMBER_ID"),
            "display_name": b.get("DISPLAY_NAME"),
            "email": b.get("EMAIL"),
            "net_balance_minor": int(b.get("NET_BALANCE_MINOR", 0) or 0),
            "contributed_minor": int(b.get("TOTAL_CREDIT_MINOR", 0) or 0),
            "spent_minor": int(b.get("TOTAL_DEBIT_MINOR", 0) or 0),
        }
        for b in balances
    ]

    return {
        "total_contributions_minor": int(totals.get("total_contributions_minor", 0) or 0),
        "total_expenses_minor": int(totals.get("total_expenses_minor", 0) or 0),
        "member_count": member_count,
        "pending_approvals": len(pending_items),
        "members": members_summary,
    }


@router.get("/transactions")
def list_transactions(
    group_id: str,
    type: Optional[str] = Query(None, description="Filter by type: PAYMENT, CASH, EXPENSE"),
    status: Optional[str] = Query(None, description="Filter by status (e.g. VERIFIED, PENDING_APPROVAL)"),
    member_id: Optional[str] = Query(None, description="Filter by member ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of transactions to return"),
    current_user: dict = Depends(get_current_user),
):
    """Fetch unified timeline of payments, cash contributions, and expenses."""
    _require_membership(group_id, current_user["user_id"])

    transactions = []

    # 1. Payments
    payments = payment_repo.get_by_group(group_id, limit=limit)
    for p in payments:
        transactions.append(
            {
                "transaction_id": p.get("PAYMENT_ID"),
                "type": "PAYMENT",
                "amount_minor": int(p.get("AMOUNT_MINOR", 0) or 0),
                "description": f"UPI Payment via {p.get('PROVIDER', 'UPI')}",
                "status": p.get("STATUS"),
                "member_id": p.get("MEMBER_ID"),
                "display_name": p.get("DISPLAY_NAME"),
                "email": p.get("EMAIL"),
                "created_at": str(p.get("CREATED_AT", "")),
            }
        )

    # 2. Cash Contributions
    cash_items = cash_repo.get_by_group(group_id)
    for c in cash_items:
        transactions.append(
            {
                "transaction_id": c.get("CASH_CONTRIBUTION_ID"),
                "type": "CASH",
                "amount_minor": int(c.get("AMOUNT_MINOR", 0) or 0),
                "description": c.get("DESCRIPTION") or "Cash Contribution",
                "status": c.get("STATUS"),
                "member_id": c.get("MEMBER_ID"),
                "display_name": c.get("DISPLAY_NAME"),
                "email": c.get("EMAIL"),
                "created_at": str(c.get("CREATED_AT", "")),
            }
        )

    # 3. Expenses
    expenses = expense_repo.get_by_group(group_id)
    for e in expenses:
        transactions.append(
            {
                "transaction_id": e.get("EXPENSE_ID"),
                "type": "EXPENSE",
                "amount_minor": int(e.get("AMOUNT_MINOR", 0) or 0),
                "description": e.get("DESCRIPTION"),
                "status": e.get("STATUS"),
                "member_id": e.get("PAID_BY_MEMBER_ID"),
                "display_name": e.get("PAYER_NAME"),
                "email": e.get("PAYER_EMAIL"),
                "created_at": str(e.get("CREATED_AT", "")),
            }
        )

    # Apply filters
    filtered = transactions
    if type:
        clean_type = type.strip().upper()
        filtered = [t for t in filtered if t["type"] == clean_type]

    if status:
        clean_status = status.strip().upper()
        filtered = [t for t in filtered if str(t["status"]).upper() == clean_status]

    if member_id:
        filtered = [t for t in filtered if t["member_id"] == member_id]

    # Sort descending by timestamp
    filtered.sort(key=lambda t: t["created_at"], reverse=True)

    return filtered[:limit]
