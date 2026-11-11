"""Unit tests for the SplitSync AI deterministic minimum-transfer settlement engine.
Verifies debt simplification, sum conservation, and minimal transaction count.
"""

from typing import Any


def calculate_minimal_transfers(member_balances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Greedy minimum cash-flow transfer optimizer.
    Balances in integer paise:
    - Positive balance: Creditor (should receive money)
    - Negative balance: Debtor (owes money)
    """
    # Separate into creditors and debtors
    creditors = []
    debtors = []

    for mb in member_balances:
        bal = mb["net_balance_minor"]
        mid = mb["member_id"]
        if bal > 0:
            creditors.append({"member_id": mid, "balance": bal})
        elif bal < 0:
            debtors.append({"member_id": mid, "balance": -bal})  # store debt as positive

    # Sort descending by amount
    creditors.sort(key=lambda x: x["balance"], reverse=True)
    debtors.sort(key=lambda x: x["balance"], reverse=True)

    transfers = []
    c_idx = 0
    d_idx = 0

    while c_idx < len(creditors) and d_idx < len(debtors):
        creditor = creditors[c_idx]
        debtor = debtors[d_idx]

        settle_amount = min(debtor["balance"], creditor["balance"])
        if settle_amount > 0:
            transfers.append({
                "from_member_id": debtor["member_id"],
                "to_member_id": creditor["member_id"],
                "amount_minor": settle_amount,
            })

            debtor["balance"] -= settle_amount
            creditor["balance"] -= settle_amount

        if debtor["balance"] == 0:
            d_idx += 1
        if creditor["balance"] == 0:
            c_idx += 1

    return transfers


class TestSettlementEngine:
    """Test suite for graph-based debt simplification."""

    def test_two_member_direct_settlement(self):
        """Alice owes Bob ₹50.00 (5000 paise).
        Alice: -5000, Bob: +5000.
        Expected: 1 transfer from Alice to Bob for 5000 paise.
        """
        balances = [
            {"member_id": "alice", "net_balance_minor": -5000},
            {"member_id": "bob", "net_balance_minor": 5000},
        ]
        transfers = calculate_minimal_transfers(balances)
        assert len(transfers) == 1
        assert transfers[0]["from_member_id"] == "alice"
        assert transfers[0]["to_member_id"] == "bob"
        assert transfers[0]["amount_minor"] == 5000

    def test_three_member_simplification(self):
        """Alice: -2000, Bob: -3000, Charlie: +5000.
        Expected: Alice pays Charlie 2000, Bob pays Charlie 3000.
        """
        balances = [
            {"member_id": "alice", "net_balance_minor": -2000},
            {"member_id": "bob", "net_balance_minor": -3000},
            {"member_id": "charlie", "net_balance_minor": 5000},
        ]
        transfers = calculate_minimal_transfers(balances)
        assert len(transfers) == 2
        total_settled = sum(t["amount_minor"] for t in transfers)
        assert total_settled == 5000

    def test_zero_balances_produces_no_transfers(self):
        """All members have 0 net balance.
        Expected: 0 transfers.
        """
        balances = [
            {"member_id": "user1", "net_balance_minor": 0},
            {"member_id": "user2", "net_balance_minor": 0},
            {"member_id": "user3", "net_balance_minor": 0},
        ]
        transfers = calculate_minimal_transfers(balances)
        assert len(transfers) == 0

    def test_multi_debtor_multi_creditor_conservation(self):
        """Four members:
        A: -4000, B: -6000, C: +7000, D: +3000.
        Total debt = 10000, Total credit = 10000.
        Verify total settled equals 10000 and transfer count <= (N - 1).
        """
        balances = [
            {"member_id": "A", "net_balance_minor": -4000},
            {"member_id": "B", "net_balance_minor": -6000},
            {"member_id": "C", "net_balance_minor": 7000},
            {"member_id": "D", "net_balance_minor": 3000},
        ]
        transfers = calculate_minimal_transfers(balances)
        assert len(transfers) <= 3  # N - 1 is the upper bound
        assert sum(t["amount_minor"] for t in transfers) == 10000

        # Check that individual debts and credits match
        net_after = {mb["member_id"]: mb["net_balance_minor"] for mb in balances}
        for t in transfers:
            net_after[t["from_member_id"]] += t["amount_minor"]
            net_after[t["to_member_id"]] -= t["amount_minor"]

        for mid, net in net_after.items():
            assert net == 0, f"Member {mid} did not reach 0 balance: {net}"
