"""
What-If Scenario Simulation Service.
Allows restaurant managers to simulate scenarios such as:
'What happens if customer demand increases by 30% next week?'
Recalculates inventory depletion, projected shortages, and financial exposure.
"""

from typing import Dict, Any, List
from backend.services.demand_service import DemandService
from backend.services.inventory_service import InventoryService

class WhatIfService:
    @staticmethod
    def simulate_demand_surge(percentage_change: float = 30.0, horizon_days: int = 7) -> Dict[str, Any]:
        """
        Simulates customer demand surge or drop (e.g. +30.0 for 30% increase, -15.0 for 15% drop).
        """
        multiplier = 1.0 + (percentage_change / 100.0)

        # Baseline forecast
        baseline_forecasts = DemandService.get_demand_forecasts(horizon_days=horizon_days, demand_multiplier=1.0)
        # Simulated forecast
        simulated_forecasts = DemandService.get_demand_forecasts(horizon_days=horizon_days, demand_multiplier=multiplier)

        baseline_map = {f['ingredient_id']: f for f in baseline_forecasts}

        comparison = []
        total_shortage_items = 0
        total_shortage_cost = 0.0

        for sim in simulated_forecasts:
            ing_id = sim['ingredient_id']
            base = baseline_map.get(ing_id, {})

            base_demand = base.get('predicted_demand', 0.0)
            sim_demand = sim['predicted_demand']
            current_stock = sim['current_stock']
            shortage = sim['shortage']
            shortage_delta = round(shortage - base.get('shortage', 0.0), 1)

            unit_price = base.get('estimated_reorder_cost', 0) / max(0.1, base.get('shortage', 1)) if base.get('shortage', 0) > 0 else 40.0
            item_shortage_cost = round(shortage * unit_price, 2)

            if shortage > 0:
                total_shortage_items += 1
                total_shortage_cost += item_shortage_cost

            comparison.append({
                "ingredient_id": ing_id,
                "ingredient_name": sim['ingredient_name'],
                "category": sim['category'],
                "unit": sim['unit'],
                "current_stock": current_stock,
                "baseline_demand": base_demand,
                "simulated_demand": sim_demand,
                "demand_increase": round(sim_demand - base_demand, 1),
                "simulated_shortage": shortage,
                "shortage_delta": shortage_delta,
                "shortage_cost": item_shortage_cost,
                "risk_status": "Severe Shortage" if shortage >= 10.0 else ("Moderate Shortage" if shortage > 0 else "Sufficient")
            })

        comparison.sort(key=lambda x: x['simulated_shortage'], reverse=True)

        return {
            "percentage_change": percentage_change,
            "horizon_days": horizon_days,
            "total_shortage_items": total_shortage_items,
            "total_estimated_reorder_cost": round(total_shortage_cost, 2),
            "summary_insight": (
                f"A {percentage_change:+}% shift in demand over {horizon_days} days would result in "
                f"{total_shortage_items} ingredient shortages with an estimated ₹{total_shortage_cost:,.2f} "
                f"in additional replenishment capital required."
            ),
            "items": comparison
        }

