"""What the answer says about this customer must reach the judge, and claims must state only the answer's numbers.

Two deterministic backstops behind the extractor, which is told to keep the answer's own premises and numbers
and to correct nothing, and does not always do so. Neither can release a draft: a premise no claim kept is
judged as a claim of its own, and a claim with a number the answer does not state holds the answer.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fakes import ScriptedLLM, ZeroEmbeddings, claims, clause, judge, verdict

from asof import gate as gate_mod
from asof.gate import Gate, GateRequest, invented_details, unstated_premises
from asof.ledger import Appended
from asof.schemas import JudgeResult, RewriteResult

DAY = date(2026, 3, 17)
DLY_QUOTE = "are outside Aurelia Air's control and are not eligible for compensation"
PET_QUOTE = "Small cats and dogs may travel in the cabin if the pet and its carrier together weigh no more than 8 kg"


# ---- premises ---------------------------------------------------------------------------------------------

def test_a_premise_turned_into_a_general_rule_is_judged_as_written():
    draft = "Because the delay was caused by a storm, it is outside our control and not eligible for compensation."
    general = "Delays caused by a storm are outside our control and not eligible for compensation."
    assert unstated_premises(draft, [general]) == [draft]


@pytest.mark.parametrize("claim", [
    "Because the delay was caused by a storm, it is outside our control and not eligible for compensation.",
    "The delay was caused by a storm, so it is not eligible for compensation.",
])
def test_a_claim_that_keeps_the_premise_needs_nothing_added(claim):
    draft = "Because the delay was caused by a storm, it is outside our control and not eligible for compensation."
    assert unstated_premises(draft, [claim]) == []


def test_contractions_and_case_do_not_count_as_a_dropped_premise():
    draft = "Since you're in Business class, the bereavement fare does not apply."
    assert unstated_premises(draft, ["since you are in business class, the bereavement fare does not apply."]) == []


@pytest.mark.parametrize("draft", [
    "Since 1 May, you can request the fare retroactively.",       # time, not a premise
    "Since May 2026, your account has no closing fee.",
    "Since then, your bag allowance has been two bags.",
    "Delays due to weather are not compensated.",                 # a general rule, not about this customer
    "Bags are accepted because of the new rules.",                # no reference to the customer
    "Since you asked, here is what we found.",                    # nothing a policy decides
    "As you know, we value your business.",
])
def test_time_courtesy_and_general_rules_are_not_premises(draft):
    assert unstated_premises(draft, ["Something else entirely."]) == []


@pytest.mark.parametrize("draft", [
    "Because last night's storm caused your delay, it is not eligible for compensation.",
    "Since 2 of your bags are over 23 kg, each costs $100 each way.",
    "Because Mark booked your ticket, the bereavement fare does not apply.",
    "Because decisions on your refund are final, the fee cannot be returned.",
])
def test_words_that_start_like_dates_still_start_premises(draft):
    assert unstated_premises(draft, ["Something else entirely."]) == [draft]


@pytest.mark.parametrize("draft,general", [
    ("Due to the weather, your delay is not eligible for compensation.",
     "Delays due to the weather are not eligible for compensation."),
    ("Because of the storm, your flight is not eligible for compensation.",
     "Delays caused by a storm are not eligible for compensation."),
    ("Because the delay, which was caused by weather, is outside our control, it is not compensated.",
     "Delays caused by weather are outside our control and are not compensated."),
])
def test_a_generalised_claim_does_not_keep_a_short_premise(draft, general):
    assert unstated_premises(draft, [general]) == [draft]


def test_every_premise_is_returned_whole_after_courtesies():
    draft = ("Since you asked, here is what our policy says. As you know, we value your business. "
             "Because the delay was caused by weather, it is not eligible for compensation.")
    assert unstated_premises(draft, ["Weather delays are not eligible for compensation."]) == [
        "Because the delay was caused by weather, it is not eligible for compensation."]
    long = ("Thank you for writing to us about your trip " + "and everything that happened along the way " * 9
            + "and because the delay was caused by weather, it is not eligible for compensation.")
    assert unstated_premises(long, ["Weather delays are not compensated."]) == [long]


def test_more_premises_than_fit_hold_the_answer_instead_of_dropping_some():
    from asof.gate import TooManyClaims
    from asof.schemas import ExtractedClaim
    seven = [ExtractedClaim(text=f"Claim {i} costs ${i}.", area="baggage", claim_type="amount") for i in range(7)]
    draft = "Since your bag weighs 27 kg, it costs $100. Because your flight is international, your bag fee is $40."
    with pytest.raises(TooManyClaims):
        Gate.premise_claims(draft, seven)
    assert len(Gate.premise_claims(draft, seven[:6])) == 2


def test_a_premise_claim_overlapping_no_claim_goes_to_other():
    from asof.gate import _premise_claim
    from asof.schemas import ExtractedClaim
    c = _premise_claim("Because it was booked today, cancellation is free.",
                       [ExtractedClaim(text="Pets fly for $100.", area="pets", claim_type="amount")])
    assert c.area == "other" and c.claim_type == "amount"


# ---- numbers the answer does not state --------------------------------------------------------------------

def test_a_claim_with_the_customers_number_instead_of_the_answers_is_flagged():
    draft = "Yes, since your cat and carrier weigh under 8 kg, she can travel in the cabin for $100 each way."
    found = invented_details(draft, ["Since your cat and carrier weigh 11 kg, she cannot travel in the cabin.",
                                     "The pet fee is $100 each way."])
    assert found == ["11 kg (in a claim, not in the answer)"]


@pytest.mark.parametrize("draft,claim", [
    ("The fee is $1,500.", "The fee is $1500."),
    ("You can bring one pet.", "You can bring 1 pet."),
    ("You can bring a pet in the cabin.", "You can bring one pet in the cabin."),
    ("Refunds take thirty days.", "Refunds take 30 days."),
    ("You get a full refund.", "You get a 100% refund."),
    ("You can cancel free of charge within 24 hours.", "Cancellation within 24 hours is free."),
    ("Feel free to call us. Bags cost $35.", "Bags cost $35."),
])
def test_the_same_number_written_differently_is_not_flagged(draft, claim):
    assert invented_details(draft, [claim]) == []


# ---- through the gate -------------------------------------------------------------------------------------

@pytest.fixture
def world(monkeypatch):
    state = {"ids": ["DLY-004"], "entries": []}
    monkeypatch.setattr(gate_mod, "clauses_as_of",
                        lambda conn, vec, as_of, doc_id, k, system_time=None, schema="ASOF":
                        [clause(cid, as_of) for cid in state["ids"]])

    def append(conn, entry, schema="ASOF"):
        state["entries"].append(entry)
        return Appended(len(state["entries"]), "h" * 64, datetime(2026, 11, 7))

    monkeypatch.setattr(gate_mod.ledger, "append", append)
    return state


class FakeConn:
    def close(self):
        pass


def check(llm, draft, question):
    return Gate(llm, ZeroEmbeddings(), connect=FakeConn).check(GateRequest(question, draft, DAY, "AURELIA-CSP", "api"))


def judged_claims(llm) -> list[str]:
    """The claim texts each judge call was given, from the human message's <claims> block."""
    return [m[-1][1] for schema, m in llm.calls if schema is JudgeResult]


def test_the_judge_sees_the_premise_the_extractor_generalised_and_can_hold_the_answer(world):
    draft = "Because the delay was caused by weather, it is outside our control and not eligible for compensation."
    llm = ScriptedLLM(
        extract=[claims(("Delays caused by weather are outside our control and not eligible for compensation.",
                         "delay", "eligibility")), claims()],
        judge=[judge(verdict(1, "SUPPORTED", "DLY-004", DLY_QUOTE),
                     verdict(2, "SUPPORTED", "DLY-004", DLY_QUOTE, conflict=True))],
        rewrite=[RewriteResult(answer="Please contact us about your delay.")])
    r = check(llm, draft, "Our flight was 5 hours late. The pilot said the brakes had a fault.")
    assert draft in judged_claims(llm)[0]
    assert r.claims[1].text == draft
    assert r.claims[1].verdict == "CONTRADICTED" and r.decision != "PASS"


def test_a_claim_written_from_the_question_instead_of_the_answer_holds_it(world):
    world["ids"] = ["PET-001"]
    draft = "Yes, since your cat and carrier weigh under 8 kg, she can travel in the cabin for $100 each way."
    faithless = "Since your cat and carrier weigh 11 kg, she cannot travel in the cabin."
    llm = ScriptedLLM(extract=[claims((faithless, "pets", "eligibility"))],
                      judge=[judge(verdict(1, "SUPPORTED", "PET-001", PET_QUOTE),
                                   verdict(2, "SUPPORTED", "PET-001", PET_QUOTE))])  # the draft's own sentence
    r = check(llm, draft, "My cat and her carrier weigh 11 kg. Can she come in the cabin?")
    assert r.decision == "ESCALATED" and r.reason_code == "UNCHECKED_DETAILS"
    assert "11 kg (in a claim, not in the answer)" in r.unchecked


def test_an_answer_with_no_policy_claims_gets_no_premise_added(world):
    llm = ScriptedLLM(extract=[claims()])
    r = check(llm, "Since you asked so kindly, we hope you have a lovely trip!", "Any tips for my trip?")
    assert r.decision == "PASS" and not judged_claims(llm)


def test_a_premise_sentence_never_counts_as_stating_a_number_the_extractor_dropped(world):
    """The premise sentence holds every number of its sentence; if it counted as stating them, a number the
    extractor left out (the $200 credit) would escape the coverage hold and rest on the judge alone."""
    world["ids"] = ["BAG-003"]
    draft = "Since your bag weighs 27 kg, the overweight fee is $100 each way and we add a $200 travel credit."
    quote = "Bags between 23 kg and 32 kg are accepted for an overweight fee of $100 each way"
    llm = ScriptedLLM(extract=[claims(("The overweight fee for your 27 kg bag is $100 each way.", "baggage", "amount"))],
                      judge=[judge(verdict(1, "SUPPORTED", "BAG-003", quote), verdict(2, "SUPPORTED", "BAG-003", quote))])
    r = check(llm, draft, "My bag weighs 27 kg. What do I pay?")
    assert len(judged_claims(llm)) == 1 and draft in judged_claims(llm)[0]
    assert r.decision == "ESCALATED" and r.reason_code == "UNCHECKED_DETAILS" and "$200" in r.unchecked


def test_extracted_and_premise_claims_together_stay_within_what_the_ledger_accepts(world):
    eight = [(f"Bag {i} costs ${10 * i}.", "baggage", "amount") for i in range(1, 9)]
    llm = ScriptedLLM(extract=[claims(*eight)])
    r = check(llm, "Since your bag weighs 27 kg, the overweight fee is $100 each way.", "What do I pay?")
    assert r.decision == "ESCALATED" and r.reason_code == "TOO_MANY_CLAIMS" and not judged_claims(llm)

