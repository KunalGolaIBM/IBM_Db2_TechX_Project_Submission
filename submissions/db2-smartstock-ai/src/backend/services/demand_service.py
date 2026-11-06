"""
Intelligent Demand Forecasting Service.
Forecasts 1-day, 3-day, and 7-day ingredient consumption,
compares against current stock in IBM Db2, and flags potential shortages.
"""

from typing import List, Dict, Any
from db.db2_client import db_client
from ml.predictor import predictor
from backend.services.inventory_service import InventoryService

class DemandService:
    @staticmethod
    def get_demand_forecasts(horizon_days: int = 7, demand_multiplier: float = 1.0) -> List[Dict[str, Any]]:
        ingredients = InventoryService.get_all_ingredients()

        cons_sql = """
        SELECT ingredient_id, AVG(quantity_used) AS avg_daily, COUNT(*) AS history_count
        FROM CONSUMPTION
        GROUP BY ingredient_id
        """
        cons_rows = db_client.query(cons_sql)
        avg_cons_map = {r['ingredient_id']: float(r.get('avg_daily', 2.0) or 2.0) for r in cons_rows}

        forecasts = []
        for ing in ingredients:
            ing_id = ing['ingredient_id']
            stock = float(ing.get('current_stock', 0) or 0)
            base_daily = avg_cons_map.get(ing_id, 2.5)

            fc = predictor.forecast_ingredient_demand(
                daily_base_consumption=base_daily,
                current_stock=stock,
                horizon_days=horizon_days,
                demand_multiplier=demand_multiplier
            )

            predicted_demand = float(fc.get('predicted_demand', 0) or 0)
            shortage = float(fc.get('shortage', 0) or 0)
            unit_price = float(ing.get('unit_price', 0) or 0)
            reorder_cost = round(shortage * unit_price, 2)

            forecasts.append({
                "ingredient_id": ing_id,
                "ingredient_name": ing['ingredient_name'],
                "category": ing['category'],
                "unit": ing['unit'],
                "current_stock": stock,
                "predicted_demand": predicted_demand,
                "shortage": shortage,
                "reorder_suggested": fc.get('reorder_suggested', False),
                "estimated_reorder_cost": reorder_cost,
                "daily_breakdown": fc.get('daily_breakdown', []),
                "explanation": fc.get('explanation', '')
            })

        forecasts.sort(key=lambda x: x['shortage'], reverse=True)
        return forecasts
