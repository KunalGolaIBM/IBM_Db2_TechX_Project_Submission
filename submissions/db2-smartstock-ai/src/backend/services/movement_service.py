"""
Audited Stock Movements Service for IBM Db2.
Tracks all inventory modifications: Purchases, Consumptions, Waste discards, and Adjustments.
"""

import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from db.db2_client import db_client

class MovementService:
    @staticmethod
    def get_all_movements(limit: int = 100) -> List[Dict[str, Any]]:
        sql = """
        SELECT m.movement_id, m.ingredient_id, i.ingredient_name, i.category,
               m.batch_number, m.movement_type, m.quantity, i.unit,
               m.movement_date, m.reason, m.performed_by
        FROM STOCK_MOVEMENTS m
        JOIN INGREDIENTS i ON m.ingredient_id = i.ingredient_id
        ORDER BY m.movement_date DESC
        """
        rows = db_client.query(sql)
        for r in rows:
            r['quantity'] = float(r.get('quantity', 0) or 0)
        return rows[:limit]

    @staticmethod
    def record_movement(
        ingredient_id: str,
        batch_number: str,
        movement_type: str,
        quantity: float,
        reason: str,
        performed_by: str = "Manager"
    ) -> bool:
        mid = f"MOV_{uuid.uuid4().hex[:8].upper()}"
        today_str = datetime.now().strftime("%Y-%m-%d")
        sql = """
        INSERT INTO STOCK_MOVEMENTS (
            movement_id, ingredient_id, batch_number, movement_type,
            quantity, movement_date, reason, performed_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        return db_client.execute(sql, [
            mid, ingredient_id, batch_number, movement_type,
            float(quantity), today_str, reason, performed_by
        ])

