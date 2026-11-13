"""Time bands: a cancellation time is checked against the fare table's band edges, not left to the judge.

Band data is SPR's (asof/eval/unseen/bands.py, from the policy text). Added after the first unseen-domain run."""

from __future__ import annotations

import pytest

from asof import rules
from asof.eval.unseen.bands import P03, P05


def check(claim: str, question: str, bands: list) -> str:
    return rules.band_check(claim, question, {"time_bands": bands}, "CAN-004").status


@pytest.mark.parametrize(("when", "hours"), [
    ("2 hours 59 minutes before departure", 2 + 59 / 60), ("exactly 3 hours before departure", 3.0),
    ("3 h 01 min before departure", 3 + 1 / 60), ("35h59m before departure", 35 + 59 / 60), ("40 hours out", 40.0),
    ("55h ahead", 55.0), ("8 days before departure", 192.0), ("90 minutes before departure", 1.5)])
def test_cancellation_times_are_read_to_the_minute(when, hours):
    assert rules.time_before_departure(f"I cancel {when}.") == [pytest.approx(hours)]


def test_limits_and_ranges_are_rules_not_times():
    assert rules.time_before_departure("cancelled at least 36 hours before departure") == []
    assert rules.time_before_departure("tickets cancelled 4 to 12 hours before the train") == []
    assert rules.time_before_departure("within 24 hours after departure") == []


@pytest.mark.parametrize("version", [1, 2, 3])
def test_every_band_edge_belongs_to_the_band_above_it(version):
    """'At least' includes the threshold: exactly on an edge is the higher band, a minute less the lower."""
    bands = P03[version]
    for upper, lower in zip(bands, bands[1:], strict=False):
        edge = upper["from_h"]
        assert rules.band_for(bands, edge) is upper
        assert rules.band_for(bands, edge - 1 / 60) is lower
        assert rules.band_for(bands, edge + 1 / 60) is upper


Q = "A confirmed 1A ticket, INR 2,000 base fare, booked on the day, is cancelled {when} before scheduled departure."


@pytest.mark.parametrize(("when", "claim", "status"), [
    ("2 hours 59 minutes", "A 50% charge applies, so you get INR 1,000 back.", "MISMATCH"),   # below 3 h: no refund
    ("2 hours 59 minutes", "There is no refund.", "MATCH"),
    ("exactly 3 hours", "There is no refund since the 3-hour limit is reached.", "MISMATCH"),  # 3 h is the 50% band
    ("exactly 3 hours", "A 50% charge applies, so you get INR 1,000 back.", "MATCH"),
    ("3 hours 1 minute", "A 50% charge applies, so you get INR 1,000 back.", "MATCH"),
    ("exactly 10 hours", "A 50% charge applies.", "MISMATCH"),                                # 10 h is the flat band
    ("exactly 10 hours", "The cancellation charge is INR 130, so you get INR 1,870 back.", "MATCH"),
    ("9 hours 59 minutes", "The cancellation charge is INR 130.", "MISMATCH"),
    ("exactly 36 hours", "The cancellation charge is INR 260.", "MATCH"),
    ("35 hours 59 minutes", "The cancellation charge is INR 260.", "MISMATCH"),
])
def test_v2_fare_table_edges(when, claim, status):
    assert check(claim, Q.format(when=when), P03[2]) == status


@pytest.mark.parametrize(("version", "edges"), [(1, (4, 12, 48)), (2, (3, 10, 36)), (3, (2, 8, 24))])
def test_each_versions_edges_decide_the_outcome(version, edges):
    low, mid, high = edges
    pct = P03[version][2]["charge_pct"]
    flat_mid, flat_high = P03[version][1]["charge_inr"]["2S"], P03[version][0]["charge_inr"]["2S"]
    q = "I booked 2S for INR 500 and cancel {when} before departure."
    assert check("There is no refund.", q.format(when=f"{low - 1} hours 59 minutes"), P03[version]) == "MATCH"
    assert check("There is no refund.", q.format(when=f"exactly {low} hours"), P03[version]) == "MISMATCH"
    assert check(f"A {pct:g}% charge applies.", q.format(when=f"exactly {low} hours"), P03[version]) == "MATCH"
    assert check(f"A {pct:g}% charge applies.", q.format(when=f"exactly {mid} hours"), P03[version]) == "MISMATCH"
    assert check(f"The charge is INR {flat_mid}.", q.format(when=f"exactly {mid} hours"), P03[version]) == "MATCH"
    assert check(f"The charge is INR {flat_mid}.", q.format(when=f"exactly {high} hours"), P03[version]) == "MISMATCH"
    assert check(f"The charge is INR {flat_high}.", q.format(when=f"exactly {high} hours"), P03[version]) == "MATCH"
    assert check(f"The charge is INR {flat_high}.", q.format(when=f"{high - 1} hours 59 minutes"),
                 P03[version]) == "MISMATCH"


def test_a_flat_charge_is_capped_at_the_fare_and_the_refund_follows():
    q = "I booked 2S for INR 50 and cancel 50 hours before departure."  # v1 2S charge INR 60, fare only INR 50
    assert check("Nothing is refunded: there is no refund.", q, P03[1]) == "MATCH"
    q = "I booked 2S for INR 500 and cancel 40 hours before departure."
    assert check("The charge is INR 30 and you get INR 470 back.", q, P03[1]) == "MATCH"
    assert check("The charge is INR 30 and you get INR 440 back.", q, P03[1]) == "MISMATCH"


def test_premium_quickbook_bands():
    q = "A confirmed PQ booking is cancelled {when} before departure, fare INR 2,000."
    assert check("Only a 30% premium charge is deducted.", q.format(when="35h59m"), P05[2]) == "MISMATCH"
    assert check("A 30% charge applies.", q.format(when="exactly 36 hours"), P05[2]) == "MATCH"
    assert check("The base fare is non-refundable.", q.format(when="23 hours 59 minutes"), P05[3]) == "MATCH"
    assert check("You get 65% back.", q.format(when="exactly 24 hours"), P05[3]) == "MATCH"
    assert check("You get a 50% refund.", q.format(when="200 hours"), P05[1]) == "MISMATCH"


def test_nothing_is_checked_without_one_time_or_without_bands():
    assert check("A 50% charge applies.", "I cancel early.", P03[2]) == "NOT_APPLICABLE"
    two = "I cancel 5 hours before departure, or maybe 2 hours before departure."
    assert check("A 50% charge applies.", two, P03[2]) == "NOT_APPLICABLE"
    assert rules.band_check("A 50% charge applies.", Q.format(when="exactly 3 hours"), {"fee_usd": 5}).status == \
        "NOT_APPLICABLE"


@pytest.mark.parametrize("bad", [[], [{"from_h": 1}], [{"from_h": -1, "refund": False}], [{"refund": True}],
                                 [{"charge_inr": {"XX": 5}}], [{"charge_pct": 5, "refund": False}],
                                 [{"to_h": 3, "refund": False, "note": "x"}]])
def test_malformed_bands_are_refused(bad):
    with pytest.raises(ValueError):
        rules.validate_time_bands(bad)


def test_the_spr_tables_are_well_formed():
    for table in (P03, P05):
        for bands in table.values():
            rules.validate_time_bands(bands)


def test_a_sentence_about_the_booking_fee_is_not_a_no_refund_claim():
    """Found in the post-hoc run (R10, R21): "the booking service fee is not refunded" held a right rewrite."""
    q = Q.format(when="exactly 3 hours")
    assert check("The booking service fee is not refunded.", q, P03[2]) == "NOT_APPLICABLE"
    assert check("A 50% charge applies. The booking service fee is not refunded.", q, P03[2]) == "MATCH"
    assert check("There is no refund. The booking service fee is not refunded.", q, P03[2]) == "MISMATCH"


def test_an_amount_that_a_sentence_results_in_is_the_refund():
    """Found in the post-hoc run (R06): "minus this charge, resulting in INR 800" read the 800 as the charge."""
    q = Q.format(when="exactly 2 hours")  # v3 1A, 2 h: the 60% band, INR 2,000 fare
    claim = "Your refund is the base fare minus this charge, resulting in an amount of INR 800."
    assert rules.band_check(claim, q, {"time_bands": P03[3]}).status == "MATCH"
    assert rules.band_check("You get INR 800 back after a 60% deduction.", q, {"time_bands": P03[3]}).status == "MATCH"
    assert rules.band_check("You get INR 1,000 back after a 50% deduction.", q,
                            {"time_bands": P03[3]}).status == "MISMATCH"
