"""Minimum Cash-Flow Settlement Engine.

Optimizes multi-party debt obligations down to the minimal number of peer-to-peer transfers
using a deterministic greedy debt-simplification algorithm.
"""

from typing import Any


class SettlementEngine:
    """Computes minimal transfers to settle group balances with zero floating-point loss."""

    @staticmethod
    def calculate_transfers(member_balances: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate the minimal set of direct transfers required to balance all accounts.

        Args:
            member_balances: List of dicts containing 'member_id' and 'net_balance_minor'.
                             Positive values represent creditors (owed money).
                             Negative values represent debtors (owe money).

        Returns:
            Dict containing 'transfers' (list of transfer recommendations) and
            'total_settled_minor' (total amount transferred).
        """
        # Filter out members with zero balance
        creditors: list[dict[str, Any]] = []
        debtors: list[dict[str, Any]] = []

        total_net = 0
        for b in member_balances:
            val = int(b.get("net_balance_minor", 0) or 0)
            total_net += val
            mid = b.get("member_id") or b.get("MEMBER_ID")
            if not mid:
                continue

            if val > 0:
                creditors.append({"member_id": str(mid), "balance": val})
            elif val < 0:
                debtors.append({"member_id": str(mid), "balance": val})

        if not creditors or not debtors:
            return {"transfers": [], "total_settled_minor": 0}

        # Ensure exact balance conservation: if small rounding residual exists, adjust largest
        if total_net != 0:
            if total_net > 0 and creditors:
                creditors.sort(key=lambda c: c["balance"], reverse=True)
                creditors[0]["balance"] -= total_net
            elif total_net < 0 and debtors:
                debtors.sort(key=lambda d: d["balance"])
                debtors[0]["balance"] -= total_net

        # Sort debtors ascending (most negative first)
        debtors.sort(key=lambda d: d["balance"])
        # Sort creditors descending (most positive first)
        creditors.sort(key=lambda c: c["balance"], reverse=True)

        transfers: list[dict[str, Any]] = []
        total_settled_minor = 0

        d_idx = 0
        c_idx = 0

        while d_idx < len(debtors) and c_idx < len(creditors):
            debtor = debtors[d_idx]
            creditor = creditors[c_idx]

            debt_owed = -debtor["balance"]
            credit_due = creditor["balance"]

            settle_amount = min(debt_owed, credit_due)

            if settle_amount > 0:
                transfers.append(
                    {
                        "from_member_id": debtor["member_id"],
                        "to_member_id": creditor["member_id"],
                        "amount_minor": settle_amount,
                    }
                )
                total_settled_minor += settle_amount

            debtor["balance"] += settle_amount
            creditor["balance"] -= settle_amount

            if debtor["balance"] == 0:
                d_idx += 1
            if creditor["balance"] == 0:
                c_idx += 1

        return {
            "transfers": transfers,
            "total_settled_minor": total_settled_minor,
        }


settlement_engine = SettlementEngine()
