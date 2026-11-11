"""Tests for deterministic financial mathematics in SplitSync AI.
Verifies integer paise precision, fair remainder distribution, and balance conservation.
"""

import pytest


def calculate_equal_split(amount_minor: int, num_participants: int) -> list[int]:
    """Calculate equal split in integer paise with remainder to the first participant."""
    if num_participants <= 0:
        raise ValueError("Number of participants must be greater than zero")
    if amount_minor < 0:
        raise ValueError("Amount cannot be negative")

    base_share = amount_minor // num_participants
    remainder = amount_minor % num_participants

    shares = [base_share] * num_participants
    if remainder > 0:
        shares[0] += remainder

    return shares


class TestFinancialMath:
    """Test suite ensuring zero-loss integer math across all monetary operations."""

    def test_even_split(self):
        """₹300.00 (30000 paise) split equally among 3 members."""
        shares = calculate_equal_split(30000, 3)
        assert shares == [10000, 10000, 10000]
        assert sum(shares) == 30000

    def test_odd_split_with_remainder(self):
        """₹100.00 (10000 paise) split among 3 members.
        3333 + 3333 + 3334 = 10000 paise exactly.
        """
        shares = calculate_equal_split(10000, 3)
        assert shares == [3334, 3333, 3333]
        assert sum(shares) == 10000

    def test_single_participant(self):
        """Single participant pays and owes 100%."""
        shares = calculate_equal_split(4550, 1)
        assert shares == [4550]

    def test_zero_amount(self):
        """Zero amount yields zero shares."""
        shares = calculate_equal_split(0, 4)
        assert shares == [0, 0, 0, 0]

    def test_large_amount_split(self):
        """₹1,000,000.07 split among 7 members."""
        amount_minor = 100000007  # 100,000,007 paise
        shares = calculate_equal_split(amount_minor, 7)
        assert sum(shares) == amount_minor
        assert len(shares) == 7

    def test_invalid_participants_raises(self):
        """Zero or negative participants must raise ValueError."""
        with pytest.raises(ValueError):
            calculate_equal_split(1000, 0)
        with pytest.raises(ValueError):
            calculate_equal_split(1000, -2)

    def test_negative_amount_raises(self):
        """Negative amount must raise ValueError."""
        with pytest.raises(ValueError):
            calculate_equal_split(-500, 2)
