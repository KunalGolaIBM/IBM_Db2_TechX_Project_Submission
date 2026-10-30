from datetime import datetime, timedelta
from backend.feasibility import evaluate

SAFETY={"handling_verified":True,"temperature_verified":True,"allergens_verified":True,"packaging_verified":True,"local_requirements_verified":True}
def case(minutes=90, portions=20):
    listing={"id":1,"deadline":(datetime.now()+timedelta(minutes=minutes)).isoformat(),"portions":portions,"food_type":"Prepared meals","safety":dict(SAFETY),"safety_verified_by":"Demo verifier"}
    recipients=[{"id":1,"name":"A","capacity":50,"travel_minutes":15,"available":True,"food_categories":["Prepared meals"]}]
    return listing,recipients
def test_valid_feasible_recipient():
    l,r=case(); assert evaluate(l,r)["recommended"]["id"]==1
def test_insufficient_capacity():
    l,r=case(portions=60); assert any("Capacity" in x for x in evaluate(l,r)["rejected_candidates"][0]["reasons"])
def test_insufficient_time():
    l,r=case(minutes=5); assert any("travel" in x for x in evaluate(l,r)["rejected_candidates"][0]["reasons"])
def test_unavailable():
    l,r=case(); r[0]["available"]=False; assert any("unavailable" in x for x in evaluate(l,r)["rejected_candidates"][0]["reasons"])
def test_no_feasible():
    l,r=case(portions=80); result=evaluate(l,r); assert not result["feasible"] and "No recipient" in result["explanation"]
def test_alternative_after_preferred_unavailable():
    l,r=case(); r.append({"id":2,"name":"B","capacity":30,"travel_minutes":30,"available":True,"food_categories":["Prepared meals"]})
    first=evaluate(l,r); r[0]["available"]=False; after=evaluate(l,r)
    assert first["recommended"]["id"]==1 and after["recommended"]["id"]==2
def test_equal_scores_have_deterministic_id_tiebreak():
    l,r=case()
    r[0]["travel_minutes"]=20
    r.append({"id":2,"name":"B","capacity":50,"travel_minutes":20,"available":True,"food_categories":["Prepared meals"]})
    r.reverse()
    result=evaluate(l,r)
    assert [candidate["id"] for candidate in result["feasible_candidates"]]==[1,2]
    assert result["recommended"]["id"]==1 and result["alternative"]["id"]==2
def test_allergen_checkbox_is_optional_and_does_not_block_feasibility():
    l,r=case(); l["safety"]["allergens_verified"]=False; result=evaluate(l,r)
    assert result["feasible"] and result["food_safety_passed"]
    assert not any("allergen" in message.lower() for candidate in result["rejected_candidates"] for message in candidate["reasons"])

def test_required_human_safety_checks_still_block_feasibility():
    l,r=case(); l["safety"]["temperature_verified"]=False; result=evaluate(l,r)
    assert not result["feasible"] and not result["food_safety_passed"]
    assert any("temperature" in reason.lower() for reason in result["rejected_candidates"][0]["reasons"])

def test_fictional_demo_matches_only_in_simulation_without_claiming_safety():
    l,r=case(); l["demo"]=True; l["safety"]={key:False for key in SAFETY}; l["safety_verified_by"]="DEMO ONLY — no human verification"
    result=evaluate(l,r,volunteer_available_count=1)
    assert result["feasible"] and result["recommended"]["id"]==1
    assert result["simulation_only"] is True
    assert result["food_safety_passed"] is False
    assert "simulation only" in result["explanation"].lower()
    assert result["risk_assessment"]["score"] >= 12 * 4
    assert any("human verification" in reason.lower() for reason in result["risk_assessment"]["reasons"])

def test_demo_simulation_still_enforces_category_capacity_deadline_and_availability():
    l,r=case(minutes=5,portions=60); l["demo"]=True; l["safety"]={key:False for key in SAFETY}
    r[0]["food_categories"]=["Bakery"]; r[0]["available"]=False
    result=evaluate(l,r)
    assert not result["feasible"] and result["simulation_only"] is True
    reasons=result["rejected_candidates"][0]["reasons"]
    assert any("unavailable" in reason.lower() for reason in reasons)
    assert any("capacity" in reason.lower() for reason in reasons)
    assert any("travel" in reason.lower() for reason in reasons)
    assert any("food category" in reason.lower() for reason in reasons)

def test_demo_label_cannot_bypass_safety_for_a_real_listing():
    l,r=case(); l["safety"]["temperature_verified"]=False
    l["safety_verified_by"]="DEMO ONLY — no human verification"
    result=evaluate(l,r)
    assert not result["feasible"] and not result["simulation_only"]
    assert result["food_safety_passed"] is False
    assert any("temperature" in reason.lower() for reason in result["rejected_candidates"][0]["reasons"])
def test_missing_verifier_name_blocks_fully_checked_listing():
    l,r=case(); l["safety_verified_by"]=" "; result=evaluate(l,r)
    assert not result["feasible"] and any("verifier name is missing" in reason.lower() for reason in result["rejected_candidates"][0]["reasons"])
def test_category_requirement():
    l,r=case(); l["food_type"]="Dairy"; assert not evaluate(l,r)["feasible"]
def test_empty_category_configuration_rejects_food_category():
    l,r=case(); r[0]["food_categories"]=[]; result=evaluate(l,r)
    assert not result["feasible"]
    assert any("not accepted" in reason for reason in result["rejected_candidates"][0]["reasons"])
def test_timezone_aware_deadline_is_rejected_by_engine():
    l,r=case(); l["deadline"]="2030-01-01T12:00:00+05:30"
    try:
        evaluate(l,r)
    except ValueError as exc:
        assert "timezone offset" in str(exc)
    else:
        raise AssertionError("Timezone-aware local deadline should be rejected")

def test_risk_is_explainable_and_uses_deadline_capacity_volunteers_and_feasible_alternatives():
    l,r=case(minutes=25,portions=45)
    r[0]["capacity"]=50;r[0]["travel_minutes"]=15
    r.append({"id":2,"name":"B","capacity":100,"travel_minutes":20,"available":True,"food_categories":["Prepared meals"]})
    result=evaluate(l,r,volunteer_available_count=0)
    risk=result["risk_assessment"]
    assert risk["category"]=="High"
    # The clock advances between fixture creation and evaluation; whole-minute
    # margins are deliberately rounded down for conservative deadline checks.
    assert risk["deadline_margin_minutes"] in {9,10}
    assert risk["alternative_recipient_ids"]==[2]
    assert any("minutes remain" in reason for reason in risk["reasons"])
    assert any("volunteer" in reason.lower() for reason in risk["reasons"])
    assert "not a trained AI model" in risk["method"]

def test_food_safety_risk_stays_high_until_human_verification_is_complete():
    l,r=case(minutes=240)
    l["safety"]["temperature_verified"]=False
    result=evaluate(l,r,volunteer_available_count=3)
    assert result["risk_assessment"]["category"]=="High"
    assert any("Storage temperature" in reason for reason in result["risk_assessment"]["reasons"])
    assert not result["feasible"]

def test_risk_score_changes_with_actual_rejection_reasons_instead_of_fixed_no_match_value():
    l,r=case(minutes=240)
    l["safety"]["local_requirements_verified"]=False
    r.extend([
        {"id":2,"name":"B","capacity":75,"travel_minutes":32,"available":True,"food_categories":["Prepared meals"]},
        {"id":3,"name":"C","capacity":50,"travel_minutes":24,"available":True,"food_categories":["Bakery"]},
        {"id":4,"name":"D","capacity":200,"travel_minutes":45,"available":True,"food_categories":["Prepared meals"]},
    ])
    result=evaluate(l,r,volunteer_available_count=1)
    risk=result["risk_assessment"]
    assert not result["feasible"]
    assert risk["score"] == 66
    assert risk["score"] != 70
    assert any("Applicable local requirements" in reason for reason in risk["reasons"])
    assert any("food category blocks 1 of 4" in reason.lower() for reason in risk["reasons"])

def test_category_capacity_and_deadline_rejections_contribute_to_risk_score():
    l,r=case(minutes=10,portions=80)
    r[0]["food_categories"]=["Bakery"]
    result=evaluate(l,r,volunteer_available_count=1)
    reasons=result["risk_assessment"]["reasons"]
    assert not result["feasible"]
    assert any("capacity blocks" in reason.lower() for reason in reasons)
    assert any("pickup deadline blocks" in reason.lower() for reason in reasons)
    assert any("food category blocks" in reason.lower() for reason in reasons)
