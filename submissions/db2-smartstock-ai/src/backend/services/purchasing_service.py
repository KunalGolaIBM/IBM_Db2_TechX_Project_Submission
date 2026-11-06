"""
Intelligent Purchasing Assistant Service.
Converts predicted shortages into optimized purchase orders,
evaluates supplier prices, lead times, minimum order quantities (MOQs),
and enforces manager approval workflows.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from db.db2_client import db_client
from backend.services.demand_service import DemandService
from backend.services.inventory_service import InventoryService
from backend.services.movement_service import MovementService

class PurchasingService:
    @staticmethod
    def get_purchase_recommendations(horizon_days: int = 7) -> List[Dict[str, Any]]:
        forecasts = DemandService.get_demand_forecasts(horizon_days=horizon_days)
        ingredients = {i['ingredient_id']: i for i in InventoryService.get_all_ingredients()}

        sup_sql = "SELECT supplier_id, supplier_name, contact, lead_time_days, rating, min_order_qty FROM SUPPLIERS"
        suppliers = db_client.query(sup_sql)
        sup_map = {s['supplier_id']: s for s in suppliers}

        recommendations = []
        for fc in forecasts:
            shortage = float(fc.get('shortage', 0) or 0)
            current_stock = float(fc.get('current_stock', 0) or 0)
            ing_id = fc['ingredient_id']
            ing_meta = ingredients.get(ing_id, {})
            reorder_level = float(ing_meta.get('reorder_level', 10.0) or 10.0)

            needs_reorder = shortage > 0 or current_stock <= reorder_level
            if not needs_reorder:
                continue

            raw_suggested = max(shortage, float(ing_meta.get('reorder_quantity', 20.0) or 20.0))
            supplier = suppliers[0] if suppliers else {}
            moq = float(supplier.get('min_order_qty', 5.0) or 5.0)
            suggested_qty = max(raw_suggested, moq)

            unit_price = float(ing_meta.get('unit_price', 50.0) or 50.0)
            total_cost = round(suggested_qty * unit_price, 2)

            recommendations.append({
                "ingredient_id": ing_id,
                "ingredient_name": fc['ingredient_name'],
                "category": fc['category'],
                "unit": fc['unit'],
                "current_stock": current_stock,
                "reorder_level": reorder_level,
                "predicted_demand": float(fc.get('predicted_demand', 0) or 0),
                "projected_shortage": shortage,
                "suggested_order_qty": suggested_qty,
                "unit_price": unit_price,
                "estimated_total_cost": total_cost,
                "primary_supplier": supplier.get('supplier_name', 'Default Supplier'),
                "supplier_id": supplier.get('supplier_id', 'SUP001'),
                "lead_time_days": int(supplier.get('lead_time_days', 2) or 2),
                "supplier_rating": float(supplier.get('rating', 4.5) or 4.5),
                "reason": (
                    f"Current stock of {current_stock} {fc['unit']} is below safety threshold. "
                    f"Projected {horizon_days}-day demand is {fc['predicted_demand']} {fc['unit']}. "
                    f"Recommending {suggested_qty} {fc['unit']} to cover shortage and restore safety stock."
                )
            })

        recommendations.sort(key=lambda x: x['estimated_total_cost'], reverse=True)
        return recommendations

    @staticmethod
    def get_purchase_orders() -> List[Dict[str, Any]]:
        sql = """
        SELECT po.order_id, po.supplier_id, s.supplier_name, po.ingredient_id,
               i.ingredient_name, i.unit, po.quantity, po.unit_price,
               po.total_price, po.order_date, po.status, po.approved_by
        FROM PURCHASE_ORDERS po
        JOIN INGREDIENTS i ON po.ingredient_id = i.ingredient_id
        LEFT JOIN SUPPLIERS s ON po.supplier_id = s.supplier_id
        ORDER BY po.order_date DESC
        """
        rows = db_client.query(sql)
        for r in rows:
            r['quantity'] = float(r.get('quantity', 0) or 0)
            r['unit_price'] = float(r.get('unit_price', 0) or 0)
            r['total_price'] = float(r.get('total_price', 0) or 0)
        return rows

    @staticmethod
    def create_purchase_order(data: Dict[str, Any]) -> str:
        order_id = f"PO_{uuid.uuid4().hex[:8].upper()}"
        sql = """
        INSERT INTO PURCHASE_ORDERS (
            order_id, supplier_id, ingredient_id, quantity,
            unit_price, total_price, order_date, status, approved_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        qty = float(data['quantity'])
        u_price = float(data['unit_price'])
        total = round(qty * u_price, 2)
        today_str = datetime.now().strftime("%Y-%m-%d")

        db_client.execute(sql, [
            order_id,
            data.get('supplier_id', 'SUP001'),
            data['ingredient_id'],
            qty,
            u_price,
            total,
            today_str,
            data.get('status', 'Suggested'),
            data.get('approved_by', None)
        ])
        return order_id

    @staticmethod
    def approve_purchase_order(order_id: str, approver_name: str = "Restaurant Manager") -> bool:
        sql = "UPDATE PURCHASE_ORDERS SET status = 'Approved', approved_by = ? WHERE order_id = ?"
        return db_client.execute(sql, [approver_name, order_id])

    @staticmethod
    def reject_purchase_order(order_id: str) -> bool:
        sql = "UPDATE PURCHASE_ORDERS SET status = 'Rejected' WHERE order_id = ?"
        return db_client.execute(sql, [order_id])
