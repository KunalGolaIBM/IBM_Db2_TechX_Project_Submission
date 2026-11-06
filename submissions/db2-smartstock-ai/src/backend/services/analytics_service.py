"""
Financial Intelligence and Waste Analytics Service for IBM Db2.
Calculates monetary losses, inventory valuation, category trends,
turnover, and generates operational business reports.
"""

from typing import Dict, Any, List
from db.db2_client import db_client
from backend.services.inventory_service import InventoryService
from backend.services.waste_service import WasteService

class AnalyticsService:
    @staticmethod
    def get_executive_summary() -> Dict[str, Any]:
        ingredients = InventoryService.get_all_ingredients()
        batches = InventoryService.get_inventory_batches()
        waste_preds = WasteService.get_waste_predictions()
        hist_waste = WasteService.get_historical_waste_summary()

        total_val = sum(float(b.get('total_val', 0) or 0) for b in batches)
        active_count = len([i for i in ingredients if float(i.get('current_stock', 0) or 0) > 0])
        expiring_soon_count = len([b for b in batches if int(b.get('days_until_expiry', 7) or 7) <= 2])

        total_pred_waste_kg = round(sum(float(p.get('predicted_waste_qty', 0) or 0) for p in waste_preds), 1)
        total_potential_loss = round(sum(float(p.get('potential_monetary_loss', 0) or 0) for p in waste_preds), 2)
        low_stock_count = len([i for i in ingredients if i.get('is_low_stock')])
        estimated_savings = round(total_potential_loss * 0.85, 2)

        return {
            "total_inventory_value": round(total_val, 2),
            "active_ingredients_count": active_count,
            "expiring_soon_count": expiring_soon_count,
            "predicted_waste_kg": total_pred_waste_kg,
            "predicted_monetary_loss": total_potential_loss,
            "low_stock_count": low_stock_count,
            "estimated_savings_avoided": estimated_savings,
            "historical_total_wasted_kg": float(hist_waste.get('total_wasted_kg', 0) or 0),
            "historical_monetary_loss": float(hist_waste.get('total_monetary_loss', 0) or 0),
            "top_wasted_ingredients": hist_waste.get('top_wasted_ingredients', {}),
            "waste_by_category": hist_waste.get('waste_loss_by_category', {}),
            "waste_by_reason": hist_waste.get('waste_by_reason', {})
        }

    @staticmethod
    def get_consumption_vs_waste_trends() -> Dict[str, Any]:
        cons_sql = """
        SELECT consumption_date, SUM(quantity_used) AS total_used
        FROM CONSUMPTION
        GROUP BY consumption_date
        ORDER BY consumption_date ASC
        """
        cons_rows = db_client.query(cons_sql)
        for r in cons_rows:
            r['total_used'] = float(r.get('total_used', 0) or 0)

        waste_sql = """
        SELECT waste_date, SUM(quantity_wasted) AS total_wasted, SUM(monetary_loss) AS total_loss
        FROM WASTE_RECORDS
        GROUP BY waste_date
        ORDER BY waste_date ASC
        """
        waste_rows = db_client.query(waste_sql)
        for r in waste_rows:
            r['total_wasted'] = float(r.get('total_wasted', 0) or 0)
            r['total_loss'] = float(r.get('total_loss', 0) or 0)

        return {
            "consumption_trend": cons_rows,
            "waste_trend": waste_rows
        }

    @staticmethod
    def generate_report(period: str = "Weekly") -> Dict[str, Any]:
        summary = AnalyticsService.get_executive_summary()
        batches = InventoryService.get_inventory_batches()
        orders_sql = "SELECT SUM(total_price) AS total_purchased FROM PURCHASE_ORDERS WHERE status = 'Approved'"
        po_rows = db_client.query(orders_sql)
        total_purchased = float(po_rows[0].get('total_purchased', 0) or 0) if po_rows else 0.0

        return {
            "report_period": period,
            "total_inventory_value": summary['total_inventory_value'],
            "total_purchases_approved": total_purchased,
            "total_waste_loss": summary['historical_monetary_loss'],
            "predicted_waste_loss": summary['predicted_monetary_loss'],
            "estimated_savings_achieved": summary['estimated_savings_avoided'],
            "tracked_batches": len(batches),
            "active_ingredients": summary['active_ingredients_count']
        }
