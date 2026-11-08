"""Deterministic rule checks against the real Aurelia corpus rules."""

from __future__ import annotations

from datetime import date

import pytest

from asof.corpus import load_corpus
from asof.rules import RuleClause, asserted_flag, check, extract_quantities, situation_conflicts

MARCH, JUNE, JULY, OCT = date(2026, 3, 10), date(2026, 6, 2), date(2026, 7, 15), date(2026, 10, 1)


def rc(clause_id: str, on: date = MARCH) -> RuleClause:
    return RuleClause(clause_id, load_corpus().version_in_force(clause_id, on).rule)


@pytest.mark.parametrize("claim, clause, on, expected", [
    # The Moffatt case: retroactive bereavement claims, before and after the May policy change.
    ("You can apply for the bereavement discount retroactively within 90 days of ticket issue.", "BRV-002", MARCH, "MISMATCH"),
    ("You can apply for the bereavement discount retroactively within 90 days of ticket issue.", "BRV-002", JUNE, "MATCH"),
    ("Bereavement fares cannot be applied retroactively once you have flown.", "BRV-002", MARCH, "MATCH"),
    ("You can claim the bereavement fare after you travel.", "BRV-002", MARCH, "MISMATCH"),
    ("The bereavement fare is 40% off the lowest Economy fare.", "BRV-001", MARCH, "MATCH"),
    ("The bereavement fare is 50% off.", "BRV-001", MARCH, "MISMATCH"),
    ("A bereavement fare covers up to 4 passengers on one booking.", "BRV-005", MARCH, "MATCH"),
    ("A bereavement fare covers up to 6 passengers.", "BRV-005", MARCH, "MISMATCH"),
    ("A bereavement fare can be booked for a passenger in Economy.", "BRV-005", MARCH, "NOT_APPLICABLE"),
    ("The discount applies to you and up to three additional passengers on your booking.", "BRV-005", MARCH, "NOT_APPLICABLE"),
    ("Bereavement fares can be booked at the airport.", "BRV-004", MARCH, "MISMATCH"),
    # Fees that changed on a date.
    ("Your first checked bag is $35 each way.", "BAG-001", JULY, "MISMATCH"),
    ("Your first checked bag is $40 each way.", "BAG-001", JULY, "MATCH"),
    ("Your first checked bag is free.", "BAG-001", JULY, "MISMATCH"),
    ("Standard Economy changes cost $75 plus the fare difference.", "CHG-002", OCT, "MISMATCH"),
    ("Standard Economy tickets can be changed with no change fee.", "CHG-002", OCT, "MATCH"),
    ("Standard Economy tickets can be changed free, and you won't pay any fare difference.", "CHG-002", OCT, "MISMATCH"),
    # Limits versus situations.
    ("A 28 kg bag is accepted if you pay a $100 overweight fee.", "BAG-003", JULY, "MATCH"),
    ("Bags over 32 kg can be checked for an extra $200.", "BAG-003", JULY, "MISMATCH"),
    ("Pets up to 8 kg including the carrier fly in the cabin for $100 each way.", "PET-001", MARCH, "MATCH"),
    ("Pets up to 10 kg can fly in the cabin.", "PET-001", MARCH, "MISMATCH"),
    ("Each passenger may bring 2 pets in the cabin.", "PET-002", MARCH, "MISMATCH"),
    ("One carry-on bag of up to 10 kg and one personal item are free.", "BAG-004", MARCH, "MATCH"),
    ("If you cancel your $400 ticket after 24 hours, the cancellation fee is $100.", "CXL-003", MARCH, "MATCH"),
    # Durations in other words.
    ("Delay compensation can be claimed within a year of the flight.", "DLY-005", MARCH, "MATCH"),
    ("Delay compensation can be claimed within 6 months of the flight.", "DLY-005", MARCH, "MISMATCH"),
    ("Travel credits last 12 months.", "CRD-001", MARCH, "MATCH"),
    ("Travel credits are valid for one year.", "CRD-001", MARCH, "MATCH"),
    ("Travel credits are valid for 6 months.", "CRD-001", MARCH, "MISMATCH"),
    ("Card refunds arrive within 7 business days.", "RFD-001", MARCH, "MATCH"),
    ("Taxes on an unused ticket are refunded on request within a year.", "RFD-003", MARCH, "MATCH"),
    ("You can cancel for free within 24 hours of booking.", "CXL-001", MARCH, "MATCH"),
    ("You can cancel for free within 48 hours of booking.", "CXL-001", MARCH, "MISMATCH"),
    ("Service dogs fly free; send the documents 48 hours before departure.", "PET-003", MARCH, "MATCH"),
    ("Pets are not accepted in the cabin on flights over 10 hours.", "PET-004", MARCH, "MISMATCH"),
    # Permissions.
    ("You can transfer your ticket to a friend for a $50 name change fee.", "CHG-004", MARCH, "MISMATCH"),
    ("Tickets cannot be transferred to another person.", "CHG-004", MARCH, "MATCH"),
    ("Spelling corrections of up to 3 characters are free.", "CHG-004", MARCH, "MATCH"),
    ("You can cash out a travel credit.", "CRD-004", MARCH, "MISMATCH"),
    ("Travel credits have no cash value.", "CRD-004", MARCH, "MATCH"),
    ("Basic Economy tickets can be upgraded after booking.", "CHG-001", MARCH, "MISMATCH"),
    ("Weather delays also qualify for compensation.", "DLY-004", MARCH, "MISMATCH"),
    ("Weather delays are not eligible for compensation.", "DLY-004", MARCH, "MATCH"),
    # Nothing checkable.
    ("Please keep your boarding pass.", "BAG-004", MARCH, "NOT_APPLICABLE"),
])
def test_claims_against_clauses(claim, clause, on, expected):
    assert check(claim, rc(clause, on)).status == expected


def test_delay_tier_is_routed_to_the_tier_that_applies():
    """A 5-hour delay belongs to DLY-001 ($125) even if the judge cited DLY-002 ($250)."""
    tiers = [rc("DLY-001"), rc("DLY-002"), rc("DLY-003")]
    result = check("A 5-hour delay caused by a mechanical problem gets you $250.", rc("DLY-002"), tiers)
    assert result.status == "MISMATCH" and result.clause_id == "DLY-001"
    ok = check("If your flight arrives 7 hours late because of a crew shortage, you get $250.", rc("DLY-002"), tiers)
    assert ok.status == "MATCH" and ok.clause_id is None
    long = check("A 12-hour delay within our control earns $400.", rc("DLY-001"), tiers)
    assert long.status == "MATCH" and long.clause_id == "DLY-003"


def test_mismatch_details_name_the_parameter():
    detail = " ".join(check("Your first checked bag is $35 each way.", rc("BAG-001", JULY)).details)
    assert "$35" in detail and "first_bag_fee_usd=40" in detail


@pytest.mark.parametrize("text, forms", [
    ("$1,250 fee", {("usd", 1250.0)}),
    ("within 90 days", {("days", 90.0), ("hours", 2160.0)}),
    ("a 24-hour window", {("hours", 24.0)}),
    ("valid for a year", {("days", 365.0), ("months", 12.0)}),
    ("two weeks", {("days", 14.0)}),
    ("40 percent off", {("pct", 40.0)}),
    ("3 travel credits", {("count:credit", 3.0)}),
])
def test_quantity_extraction(text, forms):
    assert set(extract_quantities(text)[0].forms) == forms


def test_dollar_amounts_are_not_counted_as_nouns():
    qs = extract_quantities("The fee is $100 per passenger.")
    assert [q.forms for q in qs] == [(("usd", 100.0),)]


def test_not_free_is_not_zero():
    assert extract_quantities("Changes are not free.") == []


@pytest.mark.parametrize("claim, value", [
    ("You can apply retroactively.", True),
    ("You cannot apply retroactively.", False),
    ("You can apply retroactively, no questions asked.", True),
    ("Requests after travel aren't accepted.", False),
    ("You can request the refund after travel without any extra fee.", True),
    ("Please book soon.", None),
])
def test_retroactive_flag(claim, value):
    assert asserted_flag(claim, "retroactive_allowed") is value


def test_every_fact_a_clause_states_needs_its_parameter_or_the_rule_check_misfires():
    """Found by the first bank-test run (BT26): MTF-003 says e-statements are free, but its RULE_JSON
    held only the paper fee, so "electronic statements are free" read as $0 against $2."""
    from asof.rules import check

    clause = rc("MTF-003", date(2026, 5, 30))
    assert check("Electronic statements are free.", clause).status == "MATCH"
    assert check("Paper statements cost $5 each.", clause).status == "MISMATCH"
    assert check("Paper statements cost $2 per statement.", clause).status == "MATCH"


# ---- a unit word inside the key (min_days_before_departure) ----------------------------------------
CXL1 = RuleClause("CXL-001", {"free_cancel_window_hours": 24, "min_days_before_departure": 7})
CXL2 = RuleClause("CXL-001", {"free_cancel_window_hours": 24, "min_days_before_departure": 0})


@pytest.mark.parametrize("claim, clause, status", [
    ("your booking was made at least 7 days before the scheduled departure", CXL1, "MATCH"),  # was a false MISMATCH
    ("you must book at least 3 days before departure", CXL1, "MISMATCH"),
    ("you must book at least 7 days before departure", CXL2, "MISMATCH"),  # v2 dropped the requirement
    ("free of charge within 24 hours of purchase", CXL2, "MATCH"),
])
def test_unit_inside_the_key_is_read(claim, clause, status):
    assert check(claim, clause, [clause]).status == status


# ---- the customer's situation, as stated in the question, against the claim -----------------------
@pytest.mark.parametrize("claim, question, conflict", [
    ("Because you arrived 10 hours late, you are entitled to $400.", "My flight was 2 hours late.", True),
    ("Your flight was delayed by 8 hours, so you get $250", "we were delayed 5 hours", True),
    ("you arrived 7 hours late, so $250", "My flight landed 7 hours late", False),
    ("For a 7-hour delay caused by us, we owe you $250", "My flight was 7 hours late", False),
    ("For delays of 9 hours or more, you get $400", "My flight was 10 hours late", False),   # a threshold
    ("If you arrive at least 9 hours late, you get $400", "My flight was 10 hours late", False),
    ("you arrived 10 hours late", "Do I get compensation for my delayed flight?", False),     # nothing to compare
])
def test_situation_conflicts(claim, question, conflict):
    assert bool(situation_conflicts(claim, question)) == conflict


# Lists: eligible_relations (BRV-001) and accepted_documents (BRV-003). Wording here differs from list-test's.
@pytest.mark.parametrize("claim", [
    "Your sister-in-law is treated as immediate family, so the bereavement fare applies.",
    "Uncles qualify as immediate family members.",
    "Since she was your godmother, you are eligible for the bereavement discount.",
    "Your husband's father counts as immediate family for this fare.",
    "Bereavement fares also cover a boyfriend or girlfriend.",
])
def test_a_relation_the_list_leaves_out_cannot_qualify(claim):
    r = check(claim, rc("BRV-001"))
    assert r.status == "MISMATCH" and "eligible_relations" in r.details[0]


@pytest.mark.parametrize("claim", [
    "A brother counts as immediate family.",
    "Your late wife qualifies you for the bereavement fare.",
    "Grandchildren are included in immediate family.",
    "A stepdaughter is considered immediate family.",
    "Nephews are not included, so the fare does not apply.",
    "Friends do not qualify, however close.",
])
def test_listed_relations_and_correct_exclusions_agree_with_the_list(claim):
    assert check(claim, rc("BRV-001")).status == "MATCH"


def test_saying_a_listed_relation_does_not_qualify_is_a_mismatch():
    r = check("A grandparent does not count as immediate family.", rc("BRV-001"))
    assert r.status == "MISMATCH" and "does not qualify" in r.details[0]


@pytest.mark.parametrize(("claim", "status"), [
    ("A memorial card from the service is accepted as proof.", "MISMATCH"),
    ("Just send a social media post announcing the death.", "MISMATCH"),
    ("An email from a family member is sufficient documentation.", "MISMATCH"),
    ("A letter from the funeral home is accepted.", "MATCH"),
    ("Please provide a death certificate.", "MATCH"),
    ("A doctor's letter works as documentation.", "MATCH"),
    ("An obituary is not accepted as documentation.", "MATCH"),
])
def test_documents_are_checked_against_the_accepted_list(claim, status):
    assert check(claim, rc("BRV-003")).status == status


@pytest.mark.parametrize("claim", [
    "Bereavement fares are for customers travelling because of a death in the immediate family.",  # names no relation
    "Your mother must give us the name of the deceased.",             # a relation, but nothing about qualifying
    "Call us and your daughter's booking will be updated.",
    "The bereavement fare is 40% off the lowest Economy fare.",
])
def test_claims_that_do_not_say_who_qualifies_are_left_alone(claim):
    assert check(claim, rc("BRV-001")).status != "MISMATCH"


def test_list_checks_only_apply_to_the_clause_that_has_the_list():
    # BRV-002 has no relation list: a relation claim against it is not this check's business.
    assert check("A cousin qualifies for the bereavement fare.", rc("BRV-002")).status == "NOT_APPLICABLE"
