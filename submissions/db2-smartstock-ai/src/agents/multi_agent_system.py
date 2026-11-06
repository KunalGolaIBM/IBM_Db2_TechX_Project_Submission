"""
Multi-Agent Inventory Optimization System (CrewAI Architecture).
Coordinates 6 specialized autonomous agents:
1. Inventory Agent
2. Waste Prediction Agent
3. Demand Forecasting Agent
4. Recipe Agent
5. Purchasing Agent
6. Reporting Agent
"""

import json
import logging
from typing import Dict, Any, List
from backend.services.inventory_service import InventoryService
from backend.services.waste_service import WasteService
from backend.services.demand_service import DemandService
from backend.services.recipe_service import RecipeService
from backend.services.purchasing_service import PurchasingService
from backend.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

class InventoryAgent:
    """Agent 1: Monitors live stock levels, batch statuses, and FEFO rotations."""
    def run(self) -> Dict[str, Any]:
        batches = InventoryService.get_inventory_batches()
        critical = [b for b in batches if b['days_until_expiry'] <= 2]
        low_stock = InventoryService.get_low_stock_alerts()
        return {
            "agent": "Inventory Agent",
            "role": "Stock & Expiration Monitor",
            "status": "Completed",
            "summary": f"Monitoring {len(batches)} active batches across 15 ingredients. Detected {len(critical)} batches requiring urgent FEFO rotation.",
            "metrics": {
                "Active Batches": len(batches),
                "Critical Expiring Batches": len(critical),
                "Low-Stock Alerts": len(low_stock)
            },
            "critical_items": [
                {
                    "ingredient": b['ingredient_name'],
                    "batch": b['batch_number'],
                    "quantity": f"{b['quantity']} {b['unit']}",
                    "expiry": b['expiry_date'],
                    "days_left": b['days_until_expiry']
                }
                for b in critical[:4]
            ]
        }

class WastePredictionAgent:
    """Agent 2: ML-driven waste risk analyzer."""
    def run(self) -> Dict[str, Any]:
        preds = WasteService.get_waste_predictions()
        high_risk = [p for p in preds if p['risk_level'] in ['High', 'Medium']]
        total_pred_loss = sum(float(p.get('potential_monetary_loss', 0) or 0) for p in preds)
        return {
            "agent": "Waste Prediction Agent",
            "role": "Machine Learning Spoilage Forecaster",
            "status": "Completed",
            "summary": f"Identified {len(high_risk)} high-risk ingredients with potential excess stock of {sum(p['potential_excess'] for p in high_risk):.1f} kg.",
            "metrics": {
                "High Risk Ingredients": len(high_risk),
                "Potential Monetary Loss": f"₹{total_pred_loss:,.2f}"
            },
            "risk_breakdown": [
                {
                    "ingredient": p['ingredient_name'],
                    "available": f"{p['available_stock']} {p['unit']}",
                    "potential_excess": f"{p['potential_excess']} {p['unit']}",
                    "loss": f"₹{p['potential_monetary_loss']:,.2f}",
                    "risk": p['risk_level']
                }
                for p in high_risk[:4]
            ]
        }

class DemandForecastingAgent:
    """Agent 3: Evaluates future demand vs current stock."""
    def run(self) -> Dict[str, Any]:
        forecasts = DemandService.get_demand_forecasts(horizon_days=7)
        shortages = [f for f in forecasts if f['shortage'] > 0]
        return {
            "agent": "Demand Forecasting Agent",
            "role": "Perishable Consumption Predictor",
            "status": "Completed",
            "summary": f"Forecasted 7-day demand across all categories. Detected {len(shortages)} imminent stock shortages.",
            "metrics": {
                "Projected Shortages": len(shortages),
                "Highest Shortage Item": shortages[0]['ingredient_name'] if shortages else "None"
            },
            "shortage_items": [
                {
                    "ingredient": s['ingredient_name'],
                    "current_stock": f"{s['current_stock']} {s['unit']}",
                    "forecast_demand": f"{s['predicted_demand']} {s['unit']}",
                    "shortage": f"{s['shortage']} {s['unit']}"
                }
                for s in shortages[:4]
            ]
        }

class RecipeAgent:
    """Agent 4: Recommends dishes to utilize high-risk expiring ingredients."""
    def run(self) -> Dict[str, Any]:
        recipes = RecipeService.get_recommended_recipes_for_expiring_stock()
        top_picks = recipes[:3]
        return {
            "agent": "Recipe Agent",
            "role": "Culinary Waste Diversion Engine",
            "status": "Completed",
            "summary": f"Evaluated recipe catalog. Selected {len(top_picks)} dishes optimized to consume ingredients expiring within 48-72 hours.",
            "metrics": {
                "Recommended Dishes": len(top_picks),
                "Top Priority": top_picks[0]['recipe_name'] if top_picks else "None"
            },
            "recommended_dishes": [
                {
                    "recipe": r['recipe_name'],
                    "category": r['category'],
                    "cost": f"₹{r['estimated_cost']:,.2f}",
                    "utilizes": ", ".join(r['expiring_ingredients_used']) if r['expiring_ingredients_used'] else "Pantry items",
                    "can_cook": "Ready to Prepare" if r['can_cook'] else "Missing Items"
                }
                for r in top_picks
            ]
        }

class PurchasingAgent:
    """Agent 5: Optimizes purchase orders with MOQs and supplier constraints."""
    def run(self) -> Dict[str, Any]:
        recs = PurchasingService.get_purchase_recommendations(horizon_days=7)
        total_order_cost = sum(float(r.get('estimated_total_cost', 0) or 0) for r in recs)
        return {
            "agent": "Purchasing Agent",
            "role": "Procurement & Replenishment Optimizer",
            "status": "Completed",
            "summary": f"Generated {len(recs)} replenishment purchase recommendations complying with supplier lead times and minimum order quantities.",
            "metrics": {
                "Purchase Orders Needed": len(recs),
                "Total Order Spend": f"₹{total_order_cost:,.2f}"
            },
            "suggested_orders": [
                {
                    "ingredient": r['ingredient_name'],
                    "order_qty": f"{r['suggested_order_qty']} {r['unit']}",
                    "supplier": r['primary_supplier'],
                    "est_cost": f"₹{r['estimated_total_cost']:,.2f}"
                }
                for r in recs[:4]
            ]
        }

class ReportingAgent:
    """Agent 6: Compiles executive business findings and ROI metrics."""
    def run(self, agent_results: Dict[str, Any]) -> Dict[str, Any]:
        summary = AnalyticsService.get_executive_summary()
        return {
            "agent": "Reporting Agent",
            "role": "Executive Decision Intelligence",
            "status": "Completed",
            "executive_takeaway": (
                f"SmartStock AI monitored 15 live ingredients. Identified {agent_results['inventory']['metrics']['Critical Expiring Batches']} critical batches "
                f"at risk of spoilage. Recommended prioritizing {len(agent_results['recipes']['recommended_dishes'])} recipes to prevent "
                f"an estimated ₹{summary['estimated_savings_avoided']:,.2f} in waste loss. "
                f"Prepared {agent_results['purchasing']['metrics']['Purchase Orders Needed']} suggested purchase orders to avoid impending stockouts."
            ),
            "estimated_savings": f"₹{summary['estimated_savings_avoided']:,.2f}",
            "inventory_valuation": f"₹{summary['total_inventory_value']:,.2f}"
        }

class MultiAgentOptimizationCrew:
    def __init__(self):
        self.inv_agent = InventoryAgent()
        self.waste_agent = WastePredictionAgent()
        self.demand_agent = DemandForecastingAgent()
        self.recipe_agent = RecipeAgent()
        self.purchasing_agent = PurchasingAgent()
        self.reporting_agent = ReportingAgent()

    def run_crew(self) -> Dict[str, Any]:
        logger.info("Starting Multi-Agent Optimization Crew execution...")
        inv_res = self.inv_agent.run()
        waste_res = self.waste_agent.run()
        demand_res = self.demand_agent.run()
        recipe_res = self.recipe_agent.run()
        purchasing_res = self.purchasing_agent.run()

        intermediate = {
            "inventory": inv_res,
            "waste": waste_res,
            "demand": demand_res,
            "recipes": recipe_res,
            "purchasing": purchasing_res
        }

        report_res = self.reporting_agent.run(intermediate)

        return {
            "execution_status": "SUCCESS",
            "agents": [inv_res, waste_res, demand_res, recipe_res, purchasing_res, report_res],
            "executive_report": report_res
        }

crew = MultiAgentOptimizationCrew()
