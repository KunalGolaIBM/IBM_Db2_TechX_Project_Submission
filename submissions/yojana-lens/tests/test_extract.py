from src.agent.extract import heuristic_normalize

DEMO = (
    "I am a 34-year-old widow from a village in Uttar Pradesh. We are an OBC "
    "household. I farm two acres of our own land, our house is kutcha, and the "
    "household income is about 1.8 lakh a year. My daughter is in class 12. "
    "I have a bank account and a ration card."
)


def test_demo_household_is_extracted():
    profile = heuristic_normalize(DEMO)
    facts = profile.facts

    assert facts["age"] == 34
    assert facts["income_annual"] == 180000
    assert facts["land_holding_acres"] == 2
    assert facts["marital_status"] == "widow"
    assert facts["gender"] == "female"
    assert facts["state_code"] == "UP"
    assert facts["residence"] == "rural"
    assert facts["house_type"] == "kutcha"
    assert facts["occupation"] == "farmer"
    assert facts["category"] == "obc"
    assert facts["has_girl_child"] == "yes"
    assert facts["has_bank_account"] == "yes"


def test_daughter_class_is_not_the_applicants_education():
    facts = heuristic_normalize(DEMO).facts
    # "my daughter is in class 12" describes the child, not the applicant.
    assert "education_level" not in facts
    assert facts["girl_age"] == 17


def test_ration_card_is_not_treated_as_bpl():
    # Deliberate: a ration card alone does not prove BPL status, so the
    # engine asks for it instead of guessing.
    assert "bpl_status" not in heuristic_normalize(DEMO).facts


def test_income_below_threshold_implies_not_a_taxpayer():
    facts = heuristic_normalize(DEMO).facts
    assert facts["income_tax_payer"] == "no"


def test_hectares_are_converted_to_acres():
    facts = heuristic_normalize("I am a farmer with 1 hectare of land in Bihar.").facts
    assert round(facts["land_holding_acres"], 1) == 2.5


def test_empty_text_yields_no_facts():
    assert heuristic_normalize("hello").facts == {}
