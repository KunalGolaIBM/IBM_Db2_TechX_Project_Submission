from src.agents import calculate_impact

def test_calculate_impact_flags_runway_shorter_than_delay():
    context={
        "on_hand_qty":180,"reserved_qty":90,"daily_demand":30,
        "original_eta":"2026-11-08","revised_eta":"2026-11-16",
        "criticality":"CRITICAL",
        "production_orders":[
            {"production_order_id":"P1","required_qty":120,"required_date":"2026-11-12","order_status":"PLANNED"},
            {"production_order_id":"P2","required_qty":100,"required_date":"2026-11-14","order_status":"PLANNED"}
        ]
    }
    impact,severity=calculate_impact(context)
    assert impact["available_inventory"] == 90
    assert impact["inventory_runway_days"] == 3
    assert impact["delay_days"] == 8
    assert impact["shortage_risk"] is True
    assert impact["exposed_order_count"] == 2
    assert severity == "CRITICAL"

def test_calculate_impact_does_not_flag_shortage_when_runway_covers_delay():
    context={
        "on_hand_qty":500,"reserved_qty":50,"daily_demand":10,
        "original_eta":"2026-11-08","revised_eta":"2026-11-10",
        "criticality":"MEDIUM","production_orders":[]
    }
    impact,severity=calculate_impact(context)
    assert impact["shortage_risk"] is False
    assert severity == "MEDIUM"
