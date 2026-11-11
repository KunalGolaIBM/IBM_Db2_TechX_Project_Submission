"""Allow-listed read-only analytical tools for SplitSync AI Assistant."""

import logging
from typing import Callable, Any

try:
    from langchain.tools import tool
except ImportError:
    def tool(func: Callable[..., Any]) -> Callable[..., Any]:
        """Fallback decorator when langchain is not installed."""
        func.is_tool = True  # type: ignore
        return func

from db.repositories.ledger_repo import ledger_repo
from db.repositories.approval_repo import approval_repo
from db.repositories.settlement_repo import settlement_repo

logger = logging.getLogger(__name__)


@tool
def get_group_financial_summary(group_id: str) -> str:
    """Get the high-level financial summary including total contributions and expenses for a group."""
    try:
        totals = ledger_repo.get_group_totals(group_id)
        contrib_inr = totals.get("total_contributions_minor", 0) / 100.0
        expense_inr = totals.get("total_expenses_minor", 0) / 100.0
        return (
            f"Group Financial Summary (ID: {group_id}):\n"
            f"- Total Contributions: ₹{contrib_inr:,.2f}\n"
            f"- Total Expenses: ₹{expense_inr:,.2f}"
        )
    except Exception as exc:
        return f"Error retrieving financial summary: {exc}"


@tool
def get_member_balances(group_id: str) -> str:
    """Get current net balances for all members in a group to see who is owed money or owes money."""
    try:
        balances = ledger_repo.get_member_balances(group_id)
        if not balances:
            return f"No active members or balances found for group {group_id}."

        lines = [f"Member Balances for Group {group_id}:"]
        for b in balances:
            name = b.get("DISPLAY_NAME") or "Unknown"
            net_inr = (b.get("NET_BALANCE_MINOR") or 0) / 100.0
            cred_inr = (b.get("TOTAL_CREDIT_MINOR") or 0) / 100.0
            deb_inr = (b.get("TOTAL_DEBIT_MINOR") or 0) / 100.0

            if net_inr > 0:
                status_str = f"is owed ₹{net_inr:,.2f}"
            elif net_inr < 0:
                status_str = f"owes ₹{abs(net_inr):,.2f}"
            else:
                status_str = "is settled up (₹0.00)"

            lines.append(
                f"- {name}: {status_str} (Contributed: ₹{cred_inr:,.2f}, Consumed: ₹{deb_inr:,.2f})"
            )
        return "\n".join(lines)
    except Exception as exc:
        return f"Error retrieving member balances: {exc}"


@tool
def get_recent_transactions(group_id: str) -> str:
    """Get the recent ledger transactions for a group including type, amount, and member involved."""
    try:
        entries = ledger_repo.get_entries_by_group(group_id, limit=10)
        if not entries:
            return f"No transactions recorded for group {group_id}."

        lines = [f"Recent 10 Transactions for Group {group_id}:"]
        for e in entries:
            name = e.get("DISPLAY_NAME") or "Member"
            entry_type = e.get("ENTRY_TYPE")
            amount_inr = (e.get("AMOUNT_MINOR") or 0) / 100.0
            entity_type = e.get("ENTITY_TYPE")
            created_at = str(e.get("CREATED_AT", ""))[:19]
            lines.append(
                f"- [{created_at}] {name}: {entry_type} ₹{amount_inr:,.2f} ({entity_type})"
            )
        return "\n".join(lines)
    except Exception as exc:
        return f"Error retrieving transactions: {exc}"


@tool
def get_pending_approvals(group_id: str) -> str:
    """Get count and details of pending cash submissions requiring peer approval in a group."""
    try:
        items = approval_repo.get_pending_approvals(group_id)
        if not items:
            return f"No pending approvals found for group {group_id}. All items are approved or verified."

        lines = [f"Found {len(items)} item(s) pending approval for Group {group_id}:"]
        for i in items:
            entity_type = i.get("ENTITY_TYPE")
            submitter = i.get("SUBMITTER_NAME") or "Unknown"
            amount_inr = (i.get("AMOUNT_MINOR") or 0) / 100.0
            desc = i.get("DESCRIPTION") or "No description"
            lines.append(f"- {entity_type} by {submitter}: ₹{amount_inr:,.2f} - '{desc}'")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error retrieving pending approvals: {exc}"


@tool
def get_latest_settlement_transfers(group_id: str) -> str:
    """Get the latest calculated minimum transfer settlement plan for a group."""
    try:
        runs = settlement_repo.get_runs_by_group(group_id)
        if not runs:
            return f"No settlement plans have been calculated yet for group {group_id}."

        latest_run = runs[0]
        items = settlement_repo.get_items_by_run(latest_run["RUN_ID"])
        total_inr = (latest_run.get("TOTAL_MINOR") or 0) / 100.0

        if not items:
            return f"Group {group_id} is already fully balanced. No transfers needed."

        lines = [
            f"Latest Settlement Plan (Run ID: {latest_run['RUN_ID']}, Total: ₹{total_inr:,.2f}):"
        ]
        for item in items:
            from_name = item.get("FROM_NAME") or "Member"
            to_name = item.get("TO_NAME") or "Member"
            amount_inr = (item.get("AMOUNT_MINOR") or 0) / 100.0
            status = item.get("STATUS")
            lines.append(f"- {from_name} pays {to_name} ₹{amount_inr:,.2f} [{status}]")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error retrieving settlement plan: {exc}"


ALL_TOOLS = [
    get_group_financial_summary,
    get_member_balances,
    get_recent_transactions,
    get_pending_approvals,
    get_latest_settlement_transfers,
]
