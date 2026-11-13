"""Two ways a policy writes a duration, found onboarding SPR's text: "48 h" and "7 calendar days"."""

from __future__ import annotations

from asof import intake, rules
from asof.rules import RuleClause


def forms(text: str) -> list[tuple[tuple[str, float], ...]]:
    return [q.forms for q in rules.extract_quantities(text)]


def test_hours_written_h_are_read_as_hours():
    assert forms("T >= 48 h") == [(("hours", 48.0),)]
    assert forms("12 <= T < 48 h") == [(("hours", 48.0),)]
    assert forms("cancel 3h before") == [(("hours", 3.0),)]


def test_calendar_days_are_days():
    assert forms("no later than 7 calendar days after scheduled departure") == [(("days", 7.0), ("hours", 168.0))]
    assert forms("within 30 calendar-days") == [(("days", 30.0), ("hours", 720.0))]


def test_letters_and_classes_are_not_hours():
    assert forms("AC First (1A) and Second Sitting (2S)") == []
    assert forms("an h-shaped bracket") == []
    assert forms("Platform 9 has a 4 hour wait") == [(("hours", 4.0),)]


def test_a_claim_in_calendar_days_is_checked_against_a_days_limit():
    clause = RuleClause("CAN-005", {"max_claim_deadline_days": 7})
    assert rules.check("You can file the claim within 10 calendar days.", clause).status == "MISMATCH"
    assert rules.check("File within 7 calendar days of departure.", clause).status == "MATCH"


def test_intake_no_longer_blocks_values_stated_in_these_forms():
    text = "If SPR cancels the train, a claim filed no later than 7 calendar days after departure is refunded."
    (c,) = intake.rule_checks(text, {"max_claim_deadline_days": 7})
    assert c.status == "pass"
    (c,) = intake.rule_checks("T >= 48 h INR 240", {"min_t_hours": 48})
    assert c.status == "pass"
