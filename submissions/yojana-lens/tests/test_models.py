from src.models import coerce_facts


def test_unknown_keys_are_dropped():
    facts = coerce_facts({"age": "34", "favourite_colour": "blue", "hack": "x"})
    assert facts == {"age": 34.0}


def test_numeric_strings_are_coerced():
    facts = coerce_facts({"income_annual": "180000", "land_holding_acres": 2})
    assert facts["income_annual"] == 180000.0
    assert facts["land_holding_acres"] == 2.0


def test_unparsable_numbers_are_dropped_not_guessed():
    assert "income_annual" not in coerce_facts({"income_annual": "a lot"})


def test_vocabulary_is_canonicalised():
    facts = coerce_facts({"gender": "Woman", "residence": "Village", "category": "SC"})
    assert facts == {"gender": "female", "residence": "rural", "category": "sc"}


def test_state_codes_are_upper_case():
    assert coerce_facts({"state_code": "up"})["state_code"] == "UP"


def test_json_string_input_is_accepted():
    assert coerce_facts('{"age": 30}') == {"age": 30.0}


def test_garbage_input_returns_empty_dict():
    assert coerce_facts("not json") == {}
    assert coerce_facts(None) == {}
