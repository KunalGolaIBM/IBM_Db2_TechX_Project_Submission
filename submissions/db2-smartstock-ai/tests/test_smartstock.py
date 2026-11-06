"""
Comprehensive End-to-End System Integration Test for SmartStock AI.
Verifies all 7 core modules, distinguishing features, ML models, and IBM Db2 integration.
"""

import sys
from pathlib import Path
import logging

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from db.db2_client import db_client
from backend.services.inventory_service import InventoryService
from backend.services.waste_service import WasteService
from backend.services.demand_service import DemandService
from backend.services.recipe_service import RecipeService
from backend.services.purchasing_service import PurchasingService
from backend.services.analytics_service import AnalyticsService
from backend.services.whatif_service import WhatIfService
from agents.chatbot import chatbot
from agents.multi_agent_system import crew

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_smartstock")

def run_tests():
    print("=" * 60)
    print("SMARTSTOCK AI - SYSTEM INTEGRATION TESTS")
    print("=" * 60)

    # Test 1: IBM Db2 Health
    print("\n[Test 1] IBM Db2 Health Check...")
    health = db_client.health_check()
    print("Status:", health)
    assert health.get("status") == "ONLINE", "Db2 must be online"

    # Test 2: Inventory & FEFO Batches
    print("\n[Test 2] Inventory & FEFO Batches...")
    batches = InventoryService.get_inventory_batches()
    print(f"Retrieved {len(batches)} batches from IBM Db2.")
    assert len(batches) > 0, "Batches must exist"
    # Verify sorted by expiry_date ASC
    exp_dates = [b['expiry_date'] for b in batches]
    assert exp_dates == sorted(exp_dates), "Batches must be in FEFO order"
    print("FEFO Ordering Verified: Earliest expiry is", exp_dates[0])

    # Test 3: FEFO Consumption
    print("\n[Test 3] FEFO Consumption...")
    cons_res = InventoryService.consume_ingredient(
        ingredient_id="ING001",
        quantity=1.0,
        dish_name="Test Tomato Soup",
        notes="Automated Verification"
    )
    print("Consumption result:", cons_res)
    assert cons_res.get("success") is True, "Consumption must succeed"

    # Test 4: Waste Predictions
    print("\n[Test 4] AI Waste Prediction Engine...")
    preds = WasteService.get_waste_predictions()
    print(f"Generated waste predictions for {len(preds)} ingredients.")
    assert len(preds) > 0, "Must have predictions"
    top_risk = preds[0]
    print(f"Top Risk Item: {top_risk['ingredient_name']} (Risk: {top_risk['risk_level']}, Excess: {top_risk['potential_excess']} {top_risk['unit']})")

    # Test 5: Demand Forecasting
    print("\n[Test 5] Demand Forecasting (7-Day)...")
    forecasts = DemandService.get_demand_forecasts(horizon_days=7)
    print(f"Generated demand forecasts for {len(forecasts)} ingredients.")
    assert len(forecasts) > 0, "Must have demand forecasts"
    shortages = [f for f in forecasts if f['shortage'] > 0]
    print(f"Detected {len(shortages)} potential shortage(s). Example: {shortages[0]['ingredient_name'] if shortages else 'None'}")

    # Test 6: Recipe Recommendations (Prioritizing Expiring Items)
    print("\n[Test 6] AI Recipe Recommendations...")
    recipes = RecipeService.get_recommended_recipes_for_expiring_stock()
    print(f"Retrieved {len(recipes)} recipes from IBM Db2.")
    assert len(recipes) > 0, "Must recommend recipes"
    top_recipe = recipes[0]
    print(f"Top Recipe: {top_recipe['recipe_name']} (Expiry Score: {top_recipe['expiry_utilization_score']}, Ingredients Used: {top_recipe['expiring_ingredients_used']})")

    # Test 7: Purchasing Recommendations & Approval
    print("\n[Test 7] Purchasing Assistant & Approval Workflow...")
    recs = PurchasingService.get_purchase_recommendations(horizon_days=7)
    print(f"Generated {len(recs)} purchase recommendation(s).")
    if recs:
        p = recs[0]
        oid = PurchasingService.create_purchase_order({
            "ingredient_id": p['ingredient_id'],
            "supplier_id": p['supplier_id'],
            "quantity": p['suggested_order_qty'],
            "unit_price": p['unit_price']
        })
        print(f"Created Purchase Order: {oid}")
        app_res = PurchasingService.approve_purchase_order(oid, "Test Manager")
        assert app_res is True, "Order approval must succeed"
        print("Purchase Order Approved Successfully!")

    # Test 8: What-If Simulation
    print("\n[Test 8] What-If Scenario Simulation (+30% Demand)...")
    sim = WhatIfService.simulate_demand_surge(percentage_change=30.0, horizon_days=7)
    print("Insight:", sim['summary_insight'])
    assert sim['total_shortage_items'] >= 0, "Simulation must calculate shortage items"

    # Test 9: Multi-Agent Crew
    print("\n[Test 9] Multi-Agent Optimization Crew...")
    crew_res = crew.run_crew()
    assert crew_res['execution_status'] == "SUCCESS", "Crew execution must succeed"
    print("Crew Status:", crew_res['execution_status'])
    print("Reporting Agent Executive Takeaway:", crew_res['executive_report']['executive_takeaway'])

    # Test 10: Natural Language Chatbot
    print("\n[Test 10] AI Chatbot (Text-to-SQL & RAG)...")
    chat_res = chatbot.process_query("Which ingredients will expire tomorrow?")
    print("Chat Answer:", chat_res['answer'][:120], "...")
    assert len(chat_res['answer']) > 0, "Chatbot must return an answer"

    print("\n" + "=" * 60)
    print("ALL 10 TEST SUITES PASSED FLAWLESSLY!")
    print("=" * 60)

def test_smartstock_integration():
    run_tests()

if __name__ == "__main__":
    run_tests()

