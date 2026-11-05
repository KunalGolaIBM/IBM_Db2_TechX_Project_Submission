"""Judge Demo Pantry Seed Script.

Populates the exact benchmark household inventory for live demonstration.
"""
import sys
from datetime import date, timedelta
from pathlib import Path

current_dir = Path(__file__).resolve().parent
src_dir = current_dir.parent / "src"
sys.path.insert(0, str(src_dir))

from recipe_waste_optimizer.db.repositories.inventory_repo import InventoryRepository
from recipe_waste_optimizer.config import settings


def seed_demo_inventory(household_id: str = None):
    hid = household_id or settings.DEFAULT_HOUSEHOLD_ID
    repo = InventoryRepository()
    today = date.today()

    demo_items = [
        {"name": "tomato", "quantity": 3.0, "unit": "pieces", "expiry": today + timedelta(days=1), "loc": "fridge"},
        {"name": "spinach", "quantity": 100.0, "unit": "g", "expiry": today + timedelta(days=1), "loc": "fridge"},
        {"name": "onion", "quantity": 2.0, "unit": "pieces", "expiry": today + timedelta(days=5), "loc": "pantry"},
        {"name": "potato", "quantity": 4.0, "unit": "pieces", "expiry": today + timedelta(days=7), "loc": "pantry"},
        {"name": "eggs", "quantity": 4.0, "unit": "pieces", "expiry": today + timedelta(days=10), "loc": "fridge"},
        {"name": "cooking oil", "quantity": 200.0, "unit": "ml", "expiry": today + timedelta(days=60), "loc": "pantry"},
        {"name": "garlic", "quantity": 10.0, "unit": "cloves", "expiry": today + timedelta(days=14), "loc": "pantry"},
    ]

    print(f"Seeding demo pantry stock for household '{hid}'...")
    for item in demo_items:
        res = repo.add_inventory_item(
            household_id=hid,
            ingredient_name=item["name"],
            quantity=item["quantity"],
            unit=item["unit"],
            storage_location=item["loc"],
            purchase_date=today - timedelta(days=2),
            expiry_date=item["expiry"]
        )
        print(f"  [+] Added {res['ingredient_name']}: {res['quantity']} {res['unit']} (Expires in {res['days_until_expiry']}d, status={res['expiry_status']})")

    print("\nDemo inventory successfully seeded into IBM Db2!")


if __name__ == "__main__":
    seed_demo_inventory()
