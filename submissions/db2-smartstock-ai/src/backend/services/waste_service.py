"""
AI Food Waste Prediction Service.
Combines historical consumption in IBM Db2 with Machine Learning models
to predict waste quantities, identify high-risk ingredients, and record discards.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any
from db.db2_client import db_client
from ml.predictor import predictor
from backend.services.inventory_service import InventoryService
from backend.services.movement_service import MovementService

class WasteService:
    @staticmethod
    def get_waste_predictions() -> List[Dict[str, Any]]:
        ingredients = InventoryService.get_all_ingredients()
        batches = InventoryService.get_inventory_batches()

        ing_batches = {}
        for b in batches:
            ing_id = b['ingredient_id']
            if ing_id not in ing_batches:
                ing_batches[ing_id] = []
            ing_batches[ing_id].append(b)

        cons_sql = """
        SELECT ingredient_id, AVG(quantity_used) AS avg_daily
        FROM CONSUMPTION
        GROUP BY ingredient_id
        """
        cons_rows = db_client.query(cons_sql)
        avg_cons_map = {r['ingredient_id']: float(r.get('avg_daily', 2.0) or 2.0) for r in cons_rows}

        results = []
        for ing in ingredients:
            ing_id = ing['ingredient_id']
            stock = float(ing.get('current_stock', 0) or 0)
            if stock <= 0:
                continue

            b_list = ing_batches.get(ing_id, [])
            min_days_left = min([b['days_until_expiry'] for b in b_list]) if b_list else int(ing.get('shelf_life_days', 7) or 7)
            daily_cons = avg_cons_map.get(ing_id, 2.5)

            pred = predictor.predict_food_waste(
                category=ing.get('category', 'Vegetables'),
                purchase_qty=float(stock * 1.5),
                remaining_stock=float(stock),
                days_to_expiry=max(1, min_days_left),
                storage_temp=float(ing.get('storage_temp', 4.0) or 4.0),
                daily_demand=float(daily_cons)
            )

            unit_price = float(ing.get('unit_price', 0) or 0)
            pred_waste_qty = float(pred.get('predicted_waste_qty', 0) or 0)
            potential_loss = round(pred_waste_qty * unit_price, 2)

            results.append({
                "ingredient_id": ing_id,
                "ingredient_name": ing['ingredient_name'],
                "category": ing['category'],
                "unit": ing['unit'],
                "available_stock": stock,
                "days_until_expiry": min_days_left,
                "expected_usage": float(pred.get('expected_usage', 0) or 0),
                "potential_excess": float(pred.get('potential_excess', 0) or 0),
                "predicted_waste_qty": pred_waste_qty,
                "unit_price": unit_price,
                "potential_monetary_loss": potential_loss,
                "risk_level": pred.get('waste_level', 'Low'),
                "risk_score": int(pred.get('risk_score', 10) or 10),
                "explanation": pred.get('explanation', '')
            })

        results.sort(key=lambda x: x['risk_score'], reverse=True)
        return results

    @staticmethod
    def get_historical_waste_summary() -> Dict[str, Any]:
        sql = """
        SELECT w.waste_id, w.ingredient_id, i.ingredient_name, i.category,
               w.quantity_wasted, w.waste_date, w.waste_reason, w.monetary_loss
        FROM WASTE_RECORDS w
        JOIN INGREDIENTS i ON w.ingredient_id = i.ingredient_id
        ORDER BY w.waste_date DESC
        """
        records = db_client.query(sql)
        for r in records:
            r['quantity_wasted'] = float(r.get('quantity_wasted', 0) or 0)
            r['monetary_loss'] = float(r.get('monetary_loss', 0) or 0)

        total_kg = sum(r['quantity_wasted'] for r in records)
        total_loss = sum(r['monetary_loss'] for r in records)

        by_ing = {}
        for r in records:
            name = r['ingredient_name']
            by_ing[name] = round(by_ing.get(name, 0.0) + r['quantity_wasted'], 2)

        by_cat = {}
        for r in records:
            cat = r['category']
            by_cat[cat] = round(by_cat.get(cat, 0.0) + r['monetary_loss'], 2)

        by_reason = {}
        for r in records:
            rs = r.get('waste_reason', 'Expired')
            by_reason[rs] = round(by_reason.get(rs, 0.0) + r['quantity_wasted'], 2)

        return {
            "records": records,
            "total_wasted_kg": round(total_kg, 2),
            "total_monetary_loss": round(total_loss, 2),
            "top_wasted_ingredients": dict(sorted(by_ing.items(), key=lambda x: x[1], reverse=True)),
            "waste_loss_by_category": dict(sorted(by_cat.items(), key=lambda x: x[1], reverse=True)),
            "waste_by_reason": dict(sorted(by_reason.items(), key=lambda x: x[1], reverse=True))
        }

    @staticmethod
    def record_waste_discard(
        ingredient_id: str,
        batch_number: str,
        quantity: float,
        reason: str = "Expired",
        user: str = "Manager"
    ) -> bool:
        """Deducts wasted quantity from inventory batch and records in WASTE_RECORDS."""
        qty = float(quantity)
        
        # Get ingredient unit price
        ing_rows = db_client.query("SELECT unit_price FROM INGREDIENTS WHERE ingredient_id = ?", [ingredient_id])
        unit_price = float(ing_rows[0]['unit_price']) if ing_rows else 40.0
        monetary_loss = round(qty * unit_price, 2)

        # Update batch quantity
        b_rows = db_client.query("SELECT inventory_id, quantity FROM INVENTORY WHERE ingredient_id = ? AND batch_number = ?", [ingredient_id, batch_number])
        if b_rows:
            inv_id = b_rows[0]['inventory_id']
            curr_q = float(b_rows[0]['quantity'])
            new_q = max(0.0, round(curr_q - qty, 2))
            status = "Active" if new_q > 0 else "Depleted"
            db_client.execute("UPDATE INVENTORY SET quantity = ?, status = ? WHERE inventory_id = ?", [new_q, status, inv_id])

        wid = f"WST_{uuid.uuid4().hex[:8].upper()}"
        today_str = datetime.now().strftime("%Y-%m-%d")
        w_sql = """
        INSERT INTO WASTE_RECORDS (waste_id, ingredient_id, batch_number, quantity_wasted, waste_date, waste_reason, monetary_loss)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        success = db_client.execute(w_sql, [wid, ingredient_id, batch_number, qty, today_str, reason, monetary_loss])
        if success:
            MovementService.record_movement(
                ingredient_id=ingredient_id,
                batch_number=batch_number,
                movement_type="Waste",
                quantity=qty,
                reason=f"Discarded: {reason}",
                performed_by=user
            )
        return success
