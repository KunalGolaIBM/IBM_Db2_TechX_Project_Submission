"""
Inventory Management Service with FEFO (First-Expired, First-Out) logic,
batch tracking, stock adjustment, and audited movements in IBM Db2.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from db.db2_client import db_client
from backend.services.movement_service import MovementService

class InventoryService:
    @staticmethod
    def get_all_ingredients() -> List[Dict[str, Any]]:
        sql = """
        SELECT i.ingredient_id, i.ingredient_name, i.category, i.unit,
               i.unit_price, i.reorder_level, i.reorder_quantity,
               i.storage_temp, i.shelf_life_days,
               COALESCE(SUM(inv.quantity), 0) AS current_stock
        FROM INGREDIENTS i
        LEFT JOIN INVENTORY inv ON i.ingredient_id = inv.ingredient_id AND inv.status = 'Active'
        GROUP BY i.ingredient_id, i.ingredient_name, i.category, i.unit,
                 i.unit_price, i.reorder_level, i.reorder_quantity,
                 i.storage_temp, i.shelf_life_days
        ORDER BY i.ingredient_name
        """
        rows = db_client.query(sql)
        for r in rows:
            r['current_stock'] = float(r.get('current_stock', 0) or 0)
            r['reorder_level'] = float(r.get('reorder_level', 10) or 10)
            r['reorder_quantity'] = float(r.get('reorder_quantity', 25) or 25)
            r['unit_price'] = float(r.get('unit_price', 0) or 0)
            r['storage_temp'] = float(r.get('storage_temp', 4) or 4)
            r['shelf_life_days'] = int(r.get('shelf_life_days', 7) or 7)
            r['is_low_stock'] = r['current_stock'] <= r['reorder_level']
        return rows

    @staticmethod
    def get_inventory_batches(ingredient_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns batch-level inventory sorted by expiry_date ASC (FEFO order)."""
        params = []
        where_clause = "WHERE inv.status = 'Active'"
        if ingredient_id:
            where_clause += " AND inv.ingredient_id = ?"
            params.append(ingredient_id)

        sql = f"""
        SELECT inv.inventory_id, inv.ingredient_id, i.ingredient_name, i.category,
               i.unit, inv.batch_number, inv.quantity, inv.initial_quantity,
               inv.purchase_date, inv.expiry_date, inv.unit_price,
               inv.storage_location, inv.supplier_id, s.supplier_name, inv.status
        FROM INVENTORY inv
        JOIN INGREDIENTS i ON inv.ingredient_id = i.ingredient_id
        LEFT JOIN SUPPLIERS s ON inv.supplier_id = s.supplier_id
        {where_clause}
        ORDER BY inv.expiry_date ASC
        """
        batches = db_client.query(sql, params)
        now_dt = datetime.now()
        for b in batches:
            b['quantity'] = float(b.get('quantity', 0) or 0)
            b['initial_quantity'] = float(b.get('initial_quantity', b['quantity']) or b['quantity'])
            b['unit_price'] = float(b.get('unit_price', 0) or 0)
            b['total_val'] = round(b['quantity'] * b['unit_price'], 2)
            try:
                exp_dt = datetime.strptime(str(b['expiry_date'])[:10], "%Y-%m-%d")
                days_left = (exp_dt - now_dt).days + 1
            except:
                days_left = 7
            b['days_until_expiry'] = days_left
            if days_left <= 1:
                b['alert_status'] = "Critical"
            elif days_left <= 3:
                b['alert_status'] = "Warning"
            elif days_left <= 7:
                b['alert_status'] = "Upcoming"
            else:
                b['alert_status'] = "Good"
        return batches

    @staticmethod
    def add_inventory_batch(data: Dict[str, Any], user: str = "Manager") -> bool:
        inv_id = data.get("inventory_id") or f"INV_{uuid.uuid4().hex[:8].upper()}"
        batch_no = data.get("batch_number") or f"BAT_{uuid.uuid4().hex[:6].upper()}"
        qty = float(data["quantity"])
        u_price = float(data["unit_price"])
        sql = """
        INSERT INTO INVENTORY (
            inventory_id, ingredient_id, batch_number, quantity,
            initial_quantity, purchase_date, expiry_date, unit_price,
            storage_location, supplier_id, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
        """
        params = [
            inv_id,
            data["ingredient_id"],
            batch_no,
            qty,
            float(data.get("initial_quantity", qty)),
            data.get("purchase_date", datetime.now().strftime("%Y-%m-%d")),
            data["expiry_date"],
            u_price,
            data.get("storage_location", "Refrigerator"),
            data.get("supplier_id", "SUP001")
        ]
        success = db_client.execute(sql, params)
        if success:
            MovementService.record_movement(
                ingredient_id=data["ingredient_id"],
                batch_number=batch_no,
                movement_type="Purchase",
                quantity=qty,
                reason="Supplier Shipment Received",
                performed_by=user
            )
        return success

    @staticmethod
    def add_ingredient(data: Dict[str, Any]) -> bool:
        ing_id = data.get("ingredient_id") or f"ING_{uuid.uuid4().hex[:6].upper()}"
        sql = """
        INSERT INTO INGREDIENTS (
            ingredient_id, ingredient_name, category, unit, unit_price,
            reorder_level, reorder_quantity, storage_temp, shelf_life_days
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = [
            ing_id,
            data["ingredient_name"],
            data.get("category", "Vegetables"),
            data.get("unit", "kg"),
            float(data.get("unit_price", 40.0)),
            float(data.get("reorder_level", 10.0)),
            float(data.get("reorder_quantity", 25.0)),
            float(data.get("storage_temp", 4.0)),
            int(data.get("shelf_life_days", 7))
        ]
        return db_client.execute(sql, params)

    @staticmethod
    def delete_ingredient(ingredient_id: str) -> bool:
        # Delete batches and ingredient
        db_client.execute("DELETE FROM INVENTORY WHERE ingredient_id = ?", [ingredient_id])
        return db_client.execute("DELETE FROM INGREDIENTS WHERE ingredient_id = ?", [ingredient_id])

    @staticmethod
    def adjust_stock(inventory_id: str, new_quantity: float, reason: str, user: str = "Manager") -> bool:
        new_q = max(0.0, float(new_quantity))
        status = "Active" if new_q > 0 else "Depleted"
        
        # Get old batch details
        rows = db_client.query("SELECT ingredient_id, batch_number, quantity FROM INVENTORY WHERE inventory_id = ?", [inventory_id])
        if rows:
            old_b = rows[0]
            diff = round(new_q - float(old_b['quantity']), 2)
            sql = "UPDATE INVENTORY SET quantity = ?, status = ? WHERE inventory_id = ?"
            success = db_client.execute(sql, [new_q, status, inventory_id])
            if success:
                MovementService.record_movement(
                    ingredient_id=old_b['ingredient_id'],
                    batch_number=old_b['batch_number'],
                    movement_type="Adjustment",
                    quantity=abs(diff),
                    reason=f"{reason} (Adjustment delta: {diff:+})",
                    performed_by=user
                )
            return success
        return False

    @staticmethod
    def consume_ingredient(ingredient_id: str, quantity: float, dish_name: str = "Service", notes: str = "", user: str = "Chef") -> Dict[str, Any]:
        """
        Consumes ingredient using FEFO (First-Expired, First-Out).
        Deducts from the oldest expiring batch first.
        """
        batches = InventoryService.get_inventory_batches(ingredient_id=ingredient_id)
        if not batches:
            return {"success": False, "error": "No active batches available for this ingredient"}

        total_avail = sum(b['quantity'] for b in batches)
        if quantity > total_avail:
            return {"success": False, "error": f"Insufficient stock. Available: {total_avail}, Requested: {quantity}"}

        remaining_to_deduct = float(quantity)
        consumed_batches = []

        for b in batches:
            if remaining_to_deduct <= 0:
                break
            batch_qty = b['quantity']
            if batch_qty <= remaining_to_deduct:
                deduct = batch_qty
                new_qty = 0.0
                status = 'Depleted'
            else:
                deduct = remaining_to_deduct
                new_qty = round(batch_qty - deduct, 2)
                status = 'Active'

            remaining_to_deduct = round(remaining_to_deduct - deduct, 2)
            consumed_batches.append({"batch_number": b['batch_number'], "deducted": deduct})

            update_sql = "UPDATE INVENTORY SET quantity = ?, status = ? WHERE inventory_id = ?"
            db_client.execute(update_sql, [new_qty, status, b['inventory_id']])

            MovementService.record_movement(
                ingredient_id=ingredient_id,
                batch_number=b['batch_number'],
                movement_type="Consumption",
                quantity=deduct,
                reason=f"Prepared: {dish_name}",
                performed_by=user
            )

        cid = f"CON_{uuid.uuid4().hex[:8].upper()}"
        cons_sql = """
        INSERT INTO CONSUMPTION (consumption_id, ingredient_id, quantity_used, consumption_date, dish_name, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        today_str = datetime.now().strftime("%Y-%m-%d")
        db_client.execute(cons_sql, [cid, ingredient_id, quantity, today_str, dish_name, notes])

        return {
            "success": True,
            "quantity_consumed": quantity,
            "consumed_batches": consumed_batches,
            "consumption_id": cid
        }

    @staticmethod
    def get_low_stock_alerts() -> List[Dict[str, Any]]:
        ingredients = InventoryService.get_all_ingredients()
        return [i for i in ingredients if i['is_low_stock']]
