"""Inventory Event and Cooking History Repository for IBM Db2."""
from typing import List, Dict, Any
from recipe_waste_optimizer.db.connection import db_manager


class EventRepository:
    """Manages audit event ledger and cooking history in Db2."""

    def __init__(self, manager=None):
        self.manager = manager or db_manager

    def log_event(
        self,
        household_id: str,
        ingredient_id: int,
        event_type: str,
        quantity_delta: float,
        unit: str,
        reason: str = ""
    ) -> int:
        """Write an immutable audit log entry in INVENTORY_EVENTS."""
        with self.manager.cursor() as cur:
            cur.execute(
                """
                INSERT INTO INVENTORY_EVENTS (household_id, ingredient_id, event_type, quantity_delta, unit, reason)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (household_id, ingredient_id, event_type, quantity_delta, unit, reason)
            )
            cur.execute(
                """
                SELECT event_id FROM INVENTORY_EVENTS
                WHERE household_id = ? AND ingredient_id = ?
                ORDER BY created_at DESC FETCH FIRST 1 ROWS ONLY
                """,
                (household_id, ingredient_id)
            )
            row = cur.fetchone()
            return row[0] if row else 0

    def record_cooking_history(self, household_id: str, recipe_id: int, servings: int) -> int:
        """Record confirmed recipe cooking in COOKING_HISTORY."""
        with self.manager.cursor() as cur:
            cur.execute(
                """
                INSERT INTO COOKING_HISTORY (household_id, recipe_id, servings_prepared)
                VALUES (?, ?, ?)
                """,
                (household_id, recipe_id, servings)
            )
            cur.execute(
                """
                SELECT history_id FROM COOKING_HISTORY
                WHERE household_id = ? AND recipe_id = ?
                ORDER BY cooked_at DESC FETCH FIRST 1 ROWS ONLY
                """,
                (household_id, recipe_id)
            )
            row = cur.fetchone()
            return row[0] if row else 0

    def get_history(self, household_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch recent cooking logs."""
        with self.manager.cursor() as cur:
            cur.execute(
                f"""
                SELECT h.history_id, h.household_id, h.recipe_id, r.name,
                       h.servings_prepared, h.cooked_at
                FROM COOKING_HISTORY h
                JOIN RECIPES r ON h.recipe_id = r.recipe_id
                WHERE h.household_id = ?
                ORDER BY h.cooked_at DESC
                FETCH FIRST {limit} ROWS ONLY
                """,
                (household_id,)
            )
            rows = cur.fetchall()
            return [
                {
                    "history_id": int(r[0]),
                    "household_id": str(r[1]),
                    "recipe_id": int(r[2]),
                    "recipe_name": str(r[3]),
                    "servings_prepared": int(r[4]),
                    "cooked_at": r[5]
                }
                for r in rows
            ]

    def get_waste_summary(self, household_id: str) -> Dict[str, Any]:
        """Aggregate consumed vs discarded items from events."""
        with self.manager.cursor() as cur:
            cur.execute(
                """
                SELECT event_type, COUNT(*), SUM(ABS(quantity_delta))
                FROM INVENTORY_EVENTS
                WHERE household_id = ?
                GROUP BY event_type
                """,
                (household_id,)
            )
            rows = cur.fetchall()
            stats = {"added": 0, "consumed": 0, "discarded": 0, "adjusted": 0}
            for r in rows:
                etype = r[0]
                if etype in stats:
                    stats[etype] = int(r[1])
            return stats
