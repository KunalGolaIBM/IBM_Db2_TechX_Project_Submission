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
    assert r.counts == {"email": 2, "card": 1, "number": 0, "phone": 0, "booking_ref": 0, "name": 0}


@pytest.mark.parametrize("text, expected", [
    ("My grandmother, Eleanor Price, passed away last week.", "My grandmother, [NAME], passed away last week."),
    ("Hi Jane, you can cancel free of charge within 24 hours.", "Hi [NAME], you can cancel free of charge within 24 hours."),
    ("Can Priya Sharma use my travel credit?", "Can [NAME] use my travel credit?"),
    ("My name is Raj Patel.", "My name is [NAME]."),
    ("Dear Mrs. Okafor, your refund is on its way.", "Dear Mrs. [NAME], your refund is on its way."),
    ("Thanks, Omar.\n\nRegards,\nMaria Garcia", "Thanks, [NAME].\n\nRegards,\n[NAME]"),
    ("This is Omar from Toronto. My son Liam is 12.", "This is [NAME] from Toronto. My son [NAME] is 12."),
    ("Passenger: Wei Zhang. Cardholder: Ana Lima.", "Passenger: [NAME]. Cardholder: [NAME]."),
    ("I am writing on behalf of Fatima Khan.", "I am writing on behalf of [NAME]."),
    ("Mark Chen asked about fees.", "[NAME] asked about fees."),
])
def test_person_names_are_masked(text, expected):
    assert redact(text).text == expected


@pytest.mark.parametrize("text", [
    "I'm flying Business class on Aurelia Air in May to Lisbon.",
    "Dear Customer, Basic Economy tickets cannot be changed. Thank you, Aurelia Air.",
    "Hello there, may I change my June flight? Is there a grace period?",
    "Grace period? Max 8 kg for the pet and carrier.",       # given names that are also words, alone
    "Customer Experience Policy, Fernhollow Bank Everyday Checking.",
    "I'm Canadian and I paid in euros.",
    "Bereavement fares are 40% off. Clause BRV-002 v2 applies from 2026-05-01.",
])
def test_policy_and_product_words_are_not_names(text):
    assert redact(text).text == text


def test_name_redaction_does_not_touch_any_eval_case_or_built_in_scenario():
    """The frozen eval inputs and the recorded replay scenarios reach the model exactly as before."""
    import json
    from importlib import resources

    from asof.eval import SPLITS, load_cases
    for split in SPLITS:
        for c in load_cases(split):
            assert redact(c.question).counts["name"] == 0 and redact(c.draft).counts["name"] == 0, c.id
    scenarios = json.loads((resources.files("asof") / "ui" / "scenarios.json").read_text(encoding="utf-8"))
    texts = [v for c in scenarios["playground"] for k, v in c.items() if k in ("question", "draft")]
    assert texts and all(redact(t).counts["name"] == 0 for t in texts)
