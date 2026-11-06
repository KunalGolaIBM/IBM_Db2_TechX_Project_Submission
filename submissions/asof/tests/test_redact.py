"""Personal data is masked; policy numbers are left alone."""

from __future__ import annotations

import pytest

from asof.redact import redact


@pytest.mark.parametrize("text, expected", [
    ("Email me at jane.doe+trip@example.co.uk please", "Email me at [EMAIL] please"),
    ("My card is 4111 1111 1111 1111.", "My card is [CARD]."),
    ("Call +1 514-555-0199 or (514) 555 0199", "Call [PHONE] or [PHONE]"),
    ("Booking ref Q7XK2M, flight on 2026-03-10", "Booking ref [BOOKING_REF], flight on 2026-03-10"),
])
def test_personal_data_is_masked(text, expected):
    assert redact(text).text == expected


@pytest.mark.parametrize("text", [
    "The first bag costs $1,250 or $40 each way.",
    "Request within 90 days of 2026-05-01; 40% off; 23 kg; up to 4 passengers.",
    "Clause BRV-002 v2 applies from 2026-05-01.",
])
def test_policy_numbers_survive(text):
    assert redact(text).text == text


def test_long_numbers_are_masked_even_when_not_cards():
    assert redact("Account 1234 5678 9012 3456 on file").text == "Account [NUMBER] on file"


def test_counts_are_reported():
    r = redact("a@b.io and c@d.io, card 4111111111111111")
    assert r.counts == {"email": 2, "card": 1, "number": 0, "phone": 0, "booking_ref": 0}
