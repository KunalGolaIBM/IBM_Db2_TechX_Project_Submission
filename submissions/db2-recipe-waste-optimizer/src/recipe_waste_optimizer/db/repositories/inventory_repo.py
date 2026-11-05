"""Inventory Repository for IBM Db2."""
import json
from datetime import date
from typing import List, Optional, Dict, Any
from recipe_waste_optimizer.db.connection import db_manager
from recipe_waste_optimizer.services.normalization import (
    normalize_ingredient_name,
    normalize_unit,
    calculate_expiry_status,
)


class InventoryRepository:
    """Handles Db2 queries and updates for master ingredients and household inventory."""

    def __init__(self, manager=None):
        self.manager = manager or db_manager

    def get_or_create_ingredient(self, name: str, category: str = "general", default_unit: str = "pieces") -> int:
        """Find or insert a canonical ingredient in INGREDIENTS table."""
        canonical = normalize_ingredient_name(name)
        with self.manager.cursor() as cur:
            # Query by canonical name
            cur.execute("SELECT ingredient_id FROM INGREDIENTS WHERE canonical_name = ?", (canonical,))
            row = cur.fetchone()
            if row:
                return row[0]

            # Insert new canonical ingredient
            cur.execute(
                """
                INSERT INTO INGREDIENTS (canonical_name, category, default_unit, aliases, shelf_life_days)
                VALUES (?, ?, ?, ?, ?)
                """,
                (canonical, category, default_unit, json.dumps([name]), 7)
            )
            cur.execute("SELECT ingredient_id FROM INGREDIENTS WHERE canonical_name = ?", (canonical,))
            row = cur.fetchone()
            return row[0]

    def add_inventory_item(
        self,
        household_id: str,
        ingredient_name: str,
        quantity: float,
        unit: str,
        storage_location: str = "fridge",
        purchase_date: Optional[date] = None,
        expiry_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """Add an item to household stock."""
        ing_id = self.get_or_create_ingredient(ingredient_name, default_unit=unit)
        norm_unit = normalize_unit(unit)

        with self.manager.cursor() as cur:
            cur.execute(
                """
                INSERT INTO USER_INVENTORY (
                    household_id, ingredient_id, quantity, unit, storage_location,
                    purchase_date, expiry_date, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'available')
                """,
                (household_id, ing_id, quantity, norm_unit, storage_location, purchase_date, expiry_date)
            )
            # Retrieve newly inserted ID
            cur.execute(
                """
                SELECT inventory_id FROM USER_INVENTORY
                WHERE household_id = ? AND ingredient_id = ?
                ORDER BY created_at DESC FETCH FIRST 1 ROWS ONLY
                """,
                (household_id, ing_id)
            )
            row = cur.fetchone()
            inv_id = row[0] if row else 0

        # Also log to INVENTORY_EVENTS
        from recipe_waste_optimizer.db.repositories.event_repo import EventRepository
        EventRepository(self.manager).log_event(
            household_id=household_id,
            ingredient_id=ing_id,
            event_type="added",
            quantity_delta=quantity,
            unit=norm_unit,
            reason="User stock entry"
        )

        return self.get_inventory_item(inv_id, household_id)

    def get_inventory_item(self, inventory_id: int, household_id: str) -> Optional[Dict[str, Any]]:
        """Fetch single inventory item by ID scoped by household."""
        with self.manager.cursor() as cur:
            cur.execute(
                """
                SELECT i.inventory_id, i.household_id, i.ingredient_id, g.canonical_name,
                       g.category, i.quantity, i.unit, i.storage_location,
                       i.purchase_date, i.expiry_date, i.status, i.created_at, i.updated_at
                FROM USER_INVENTORY i
                JOIN INGREDIENTS g ON i.ingredient_id = g.ingredient_id
                WHERE i.inventory_id = ? AND i.household_id = ?
                """,
                (inventory_id, household_id)
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_dict(row)

    def list_inventory(self, household_id: str, status: str = "available") -> List[Dict[str, Any]]:
        """List current inventory records for household."""
        with self.manager.cursor() as cur:
            cur.execute(
                """
                SELECT i.inventory_id, i.household_id, i.ingredient_id, g.canonical_name,
                       g.category, i.quantity, i.unit, i.storage_location,
                       i.purchase_date, i.expiry_date, i.status, i.created_at, i.updated_at
                FROM USER_INVENTORY i
                JOIN INGREDIENTS g ON i.ingredient_id = g.ingredient_id
                WHERE i.household_id = ? AND i.status = ?
                ORDER BY i.expiry_date ASC, g.canonical_name ASC
                """,
                (household_id, status)
            )
            rows = cur.fetchall()
            return [self._row_to_dict(r) for r in rows]

    def update_inventory_item(
        self,
        inventory_id: int,
        household_id: str,
        quantity: Optional[float] = None,
        unit: Optional[str] = None,
        storage_location: Optional[str] = None,
        expiry_date: Optional[date] = None,
        status: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update fields of an inventory item."""
        existing = self.get_inventory_item(inventory_id, household_id)
        if not existing:
            return None

        updates = []
        params = []
        if quantity is not None:
            updates.append("quantity = ?")
            params.append(quantity)
        if unit is not None:
            updates.append("unit = ?")
            params.append(normalize_unit(unit))
        if storage_location is not None:
            updates.append("storage_location = ?")
            params.append(storage_location)
        if expiry_date is not None:
            updates.append("expiry_date = ?")
            params.append(expiry_date)
        if status is not None:
            updates.append("status = ?")
            params.append(status)

        if not updates:
            return existing

        updates.append("updated_at = CURRENT_TIMESTAMP")
        sql = f"UPDATE USER_INVENTORY SET {', '.join(updates)} WHERE inventory_id = ? AND household_id = ?"
        params.extend([inventory_id, household_id])

        with self.manager.cursor() as cur:
            cur.execute(sql, tuple(params))

        return self.get_inventory_item(inventory_id, household_id)

    def delete_inventory_item(self, inventory_id: int, household_id: str) -> bool:
        """Mark as discarded or delete inventory item."""
        item = self.get_inventory_item(inventory_id, household_id)
        if not item:
            return False

        with self.manager.cursor() as cur:
            cur.execute(
                "UPDATE USER_INVENTORY SET status = 'discarded', updated_at = CURRENT_TIMESTAMP WHERE inventory_id = ? AND household_id = ?",
                (inventory_id, household_id)
            )

        from recipe_waste_optimizer.db.repositories.event_repo import EventRepository
        EventRepository(self.manager).log_event(
            household_id=household_id,
            ingredient_id=item["ingredient_id"],
            event_type="discarded",
            quantity_delta=-item["quantity"],
            unit=item["unit"],
            reason="User discarded item"
        )
        return True

    def _row_to_dict(self, row) -> Dict[str, Any]:
        """Convert a Db2 row tuple to dictionary with enriched expiry calculation."""
        exp_date = row[9]
        days_left, exp_status = calculate_expiry_status(exp_date)
        return {
            "inventory_id": int(row[0]),
            "household_id": str(row[1]),
            "ingredient_id": int(row[2]),
            "ingredient_name": str(row[3]),
            "category": str(row[4]),
            "quantity": float(row[5]),
            "unit": str(row[6]),
            "storage_location": str(row[7]),
            "purchase_date": row[8],
            "expiry_date": row[9],
            "days_until_expiry": days_left,
            "expiry_status": exp_status,
            "status": str(row[10]),
            "created_at": row[11],
            "updated_at": row[12],
        }
