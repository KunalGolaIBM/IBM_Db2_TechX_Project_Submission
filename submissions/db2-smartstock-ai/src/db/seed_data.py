"""
Seeds realistic restaurant operational data into IBM Db2 and SQLite Mirror in batches.
Includes master ingredients, batches, recipes, suppliers, stock movements, and users.
"""

import logging
from datetime import datetime, timedelta
from db.db2_client import db_client

logger = logging.getLogger(__name__)

SUPPLIERS = [
    ("SUP001", "GreenValley Fresh Farms", "+91 98765 43210", 2, 4.8, 5.0),
    ("SUP002", "Metro Wholesale Produce", "+91 98234 56789", 1, 4.6, 10.0),
    ("SUP003", "Dairy Best Co-op", "+91 98111 22334", 1, 4.9, 5.0),
    ("SUP004", "Ocean & Earth Poultry", "+91 98450 11223", 2, 4.7, 4.0),
    ("SUP005", "Apex Spice & Dry Goods", "+91 98999 88776", 3, 4.5, 15.0),
]

INGREDIENTS = [
    ("ING001", "Tomato", "Vegetables", "kg", 40.0, 10.0, 25.0, 4.0, 6),
    ("ING002", "Onion", "Vegetables", "kg", 35.0, 15.0, 30.0, 18.0, 21),
    ("ING003", "Potato", "Vegetables", "kg", 30.0, 20.0, 40.0, 16.0, 30),
    ("ING004", "Spinach", "Vegetables", "kg", 50.0, 5.0, 12.0, 3.0, 4),
    ("ING005", "Mushroom", "Vegetables", "kg", 180.0, 4.0, 10.0, 4.0, 5),
    ("ING006", "Paneer", "Dairy", "kg", 320.0, 6.0, 15.0, 3.0, 5),
    ("ING007", "Milk", "Dairy", "L", 65.0, 10.0, 25.0, 3.0, 4),
    ("ING008", "Cheese", "Dairy", "kg", 450.0, 4.0, 8.0, 4.0, 14),
    ("ING009", "Chicken Breast", "Meat", "kg", 260.0, 10.0, 20.0, -2.0, 4),
    ("ING010", "Bell Pepper", "Vegetables", "kg", 80.0, 5.0, 15.0, 6.0, 8),
    ("ING011", "Garlic", "Vegetables", "kg", 160.0, 3.0, 8.0, 18.0, 45),
    ("ING012", "Ginger", "Vegetables", "kg", 120.0, 3.0, 8.0, 15.0, 30),
    ("ING013", "Cooking Oil", "Dry Goods", "L", 140.0, 15.0, 30.0, 22.0, 180),
    ("ING014", "Basmati Rice", "Dry Goods", "kg", 95.0, 25.0, 50.0, 22.0, 365),
    ("ING015", "Heavy Cream", "Dairy", "L", 220.0, 4.0, 10.0, 4.0, 7),
]

INVENTORY_BATCHES = [
    ("INV001", "ING001", "BAT-TOM-01", 5.0, 10.0, "2026-11-01", "2026-11-06", 40.0, "Refrigerator A", "SUP001", "Active"), # Expires tomorrow
    ("INV002", "ING001", "BAT-TOM-02", 10.0, 10.0, "2026-11-04", "2026-11-10", 40.0, "Refrigerator A", "SUP001", "Active"),
    ("INV003", "ING002", "BAT-ONI-01", 20.0, 25.0, "2026-10-28", "2026-11-15", 35.0, "Dry Storage 1", "SUP002", "Active"),
    ("INV004", "ING003", "BAT-POT-01", 10.0, 30.0, "2026-10-25", "2026-11-20", 30.0, "Dry Storage 2", "SUP002", "Active"),
    ("INV005", "ING004", "BAT-SPI-01", 4.0, 6.0, "2026-11-03", "2026-11-07", 50.0, "Walk-in Cooler", "SUP001", "Active"), # Expires in 2 days
    ("INV006", "ING005", "BAT-MUS-01", 3.0, 5.0, "2026-11-03", "2026-11-08", 180.0, "Refrigerator B", "SUP001", "Active"), # Expires in 3 days
    ("INV007", "ING006", "BAT-PAN-01", 5.0, 8.0, "2026-11-03", "2026-11-08", 320.0, "Walk-in Cooler", "SUP003", "Active"),
    ("INV008", "ING007", "BAT-MIL-01", 8.0, 15.0, "2026-11-03", "2026-11-06", 65.0, "Refrigerator C", "SUP003", "Active"), # Expires tomorrow
    ("INV009", "ING008", "BAT-CHE-01", 6.0, 8.0, "2026-10-28", "2026-11-14", 450.0, "Refrigerator C", "SUP003", "Active"),
    ("INV010", "ING009", "BAT-CHK-01", 12.0, 15.0, "2026-11-04", "2026-11-08", 260.0, "Deep Freezer", "SUP004", "Active"),
    ("INV011", "ING010", "BAT-PEP-01", 7.0, 10.0, "2026-11-02", "2026-11-10", 80.0, "Refrigerator B", "SUP001", "Active"),
    ("INV012", "ING011", "BAT-GAR-01", 6.0, 8.0, "2026-10-15", "2026-11-30", 160.0, "Dry Storage 1", "SUP005", "Active"),
    ("INV013", "ING012", "BAT-GIN-01", 4.0, 6.0, "2026-10-20", "2026-11-25", 120.0, "Dry Storage 1", "SUP005", "Active"),
    ("INV014", "ING013", "BAT-OIL-01", 20.0, 30.0, "2026-10-01", "2027-04-01", 140.0, "Dry Storage 2", "SUP005", "Active"),
    ("INV015", "ING014", "BAT-RIC-01", 40.0, 50.0, "2026-09-15", "2027-09-15", 95.0, "Dry Storage 2", "SUP005", "Active"),
    ("INV016", "ING015", "BAT-CRM-01", 3.0, 5.0, "2026-11-02", "2026-11-09", 220.0, "Refrigerator C", "SUP003", "Active"),
]

RECIPES = [
    ("REC001", "Creamy Tomato Soup", "Soup", 25, 4, "Sauté chopped garlic and onions in butter. Add fresh chopped tomatoes and simmer for 15 mins. Blend till silky, add heavy cream, season with salt and black pepper.", 140.0),
    ("REC002", "Palak Paneer (Spinach Curry)", "Main Course", 35, 4, "Blanch spinach leaves and blend into a smooth puree. Sauté onions, garlic, and ginger paste in oil. Add cumin, garam masala, and spinach puree. Simmer and fold in paneer.", 280.0),
    ("REC003", "Mushroom Masala", "Main Course", 30, 4, "Slice fresh mushrooms. In a pan, temper cumin seeds, sauté onions until golden brown, add tomato puree, ginger-garlic paste, turmeric, and mushrooms.", 210.0),
    ("REC004", "Tomato Basil Pasta", "Italian", 20, 3, "Boil pasta until al dente. In a skillet, sauté crushed garlic in olive oil, add diced ripe tomatoes, simmer into a rich sauce. Toss with pasta and shredded cheese.", 190.0),
    ("REC005", "Paneer Butter Masala", "Main Course", 40, 5, "Roast tomatoes, onions, garlic and blend into smooth gravy. Cook with butter, fold in paneer cubes and heavy cream.", 310.0),
    ("REC006", "Herb Garlic Roasted Potatoes", "Sides", 35, 4, "Parboil potato wedges. Toss in cooking oil, minced garlic, black pepper, and herbs. Roast in oven at 200°C until golden and crispy.", 110.0),
    ("REC007", "Kadhai Chicken", "Main Course", 45, 4, "Sauté chicken breast pieces with freshly ground coriander and red chilies. Add crunchy bell peppers, onions, and tomato reduction.", 340.0),
    ("REC008", "Vegetable Dum Biryani", "Rice", 50, 6, "Layer fragrant basmati rice with sautéed potatoes, bell peppers, onions, and tomatoes. Dum cook with saffron milk and aromatic spices.", 260.0),
]

RECIPE_INGREDIENTS = [
    ("REC001", "ING001", 1.5, "kg"),
    ("REC001", "ING002", 0.3, "kg"),
    ("REC001", "ING011", 0.05, "kg"),
    ("REC001", "ING015", 0.2, "L"),
    ("REC002", "ING004", 1.2, "kg"),
    ("REC002", "ING006", 0.5, "kg"),
    ("REC002", "ING002", 0.3, "kg"),
    ("REC002", "ING011", 0.05, "kg"),
    ("REC002", "ING012", 0.05, "kg"),
    ("REC002", "ING015", 0.1, "L"),
    ("REC003", "ING005", 1.0, "kg"),
    ("REC003", "ING001", 0.8, "kg"),
    ("REC003", "ING002", 0.4, "kg"),
    ("REC003", "ING011", 0.05, "kg"),
    ("REC003", "ING012", 0.05, "kg"),
    ("REC004", "ING001", 1.2, "kg"),
    ("REC004", "ING008", 0.2, "kg"),
    ("REC004", "ING011", 0.05, "kg"),
    ("REC004", "ING013", 0.05, "L"),
    ("REC005", "ING006", 0.6, "kg"),
    ("REC005", "ING001", 1.0, "kg"),
    ("REC005", "ING002", 0.4, "kg"),
    ("REC005", "ING015", 0.2, "L"),
    ("REC006", "ING003", 1.5, "kg"),
    ("REC006", "ING011", 0.05, "kg"),
    ("REC006", "ING013", 0.05, "L"),
    ("REC007", "ING009", 1.0, "kg"),
    ("REC007", "ING010", 0.5, "kg"),
    ("REC007", "ING001", 0.6, "kg"),
    ("REC007", "ING002", 0.4, "kg"),
    ("REC008", "ING014", 1.0, "kg"),
    ("REC008", "ING003", 0.5, "kg"),
    ("REC008", "ING010", 0.3, "kg"),
    ("REC008", "ING002", 0.5, "kg"),
    ("REC008", "ING007", 0.2, "L"),
]

HISTORICAL_WASTE = [
    ("WST001", "ING001", "BAT-TOM-OLD1", 3.5, "2026-10-15", "Overripe & Soft", 140.0),
    ("WST002", "ING004", "BAT-SPI-OLD1", 1.5, "2026-10-18", "Wilting & Moisture", 75.0),
    ("WST003", "ING007", "BAT-MIL-OLD1", 4.0, "2026-10-22", "Sour / Expired", 260.0),
    ("WST004", "ING005", "BAT-MUS-OLD1", 1.2, "2026-10-25", "Browning & Mold", 216.0),
    ("WST005", "ING001", "BAT-TOM-OLD2", 2.0, "2026-10-29", "Bruised in Crate", 80.0),
    ("WST006", "ING006", "BAT-PAN-OLD1", 1.0, "2026-11-01", "Sour smell", 320.0),
    ("WST007", "ING010", "BAT-PEP-OLD1", 1.8, "2026-11-03", "Soft spots", 144.0),
    ("WST008", "ING004", "BAT-SPI-OLD2", 1.0, "2026-11-04", "Expired", 50.0),
]

USERS = [
    ("USR001", "admin", "David Bensoussan", "Administrator", "david@smartstock.ai", "Active"),
    ("USR002", "chef_marcus", "Marcus Samuel", "Head Chef", "marcus@smartstock.ai", "Active"),
    ("USR003", "inv_clerk", "Amina Ray", "Inventory Manager", "amina@smartstock.ai", "Active"),
    ("USR004", "sous_chef", "Karan Sharma", "Kitchen Staff", "karan@smartstock.ai", "Active"),
]

STOCK_MOVEMENTS = [
    ("MOV001", "ING001", "BAT-TOM-01", "Purchase", 10.0, "2026-11-01", "Received supplier shipment", "Amina Ray"),
    ("MOV002", "ING001", "BAT-TOM-01", "Consumption", 5.0, "2026-11-03", "Tomato Soup preparation", "Marcus Samuel"),
    ("MOV003", "ING002", "BAT-ONI-01", "Purchase", 25.0, "2026-10-28", "Bulk produce purchase", "Amina Ray"),
    ("MOV004", "ING002", "BAT-ONI-01", "Consumption", 5.0, "2026-11-02", "Gravy base cooking", "Karan Sharma"),
    ("MOV005", "ING007", "BAT-MIL-01", "Purchase", 15.0, "2026-11-03", "Fresh morning dairy batch", "Amina Ray"),
    ("MOV006", "ING007", "BAT-MIL-01", "Consumption", 7.0, "2026-11-04", "Sauce and dessert service", "Marcus Samuel"),
    ("MOV007", "ING004", "BAT-SPI-01", "Purchase", 6.0, "2026-11-03", "Organic hydroponic spinach", "Amina Ray"),
    ("MOV008", "ING004", "BAT-SPI-01", "Consumption", 2.0, "2026-11-04", "Palak Paneer special", "Marcus Samuel"),
    ("MOV009", "ING003", "BAT-POT-01", "Purchase", 30.0, "2026-10-25", "Potato crate delivery", "Amina Ray"),
    ("MOV010", "ING003", "BAT-POT-01", "Consumption", 20.0, "2026-11-03", "Mashed and roasted potatoes", "Karan Sharma"),
    ("MOV011", "ING005", "BAT-MUS-01", "Purchase", 5.0, "2026-11-03", "Button mushroom crate", "Amina Ray"),
    ("MOV012", "ING005", "BAT-MUS-01", "Consumption", 2.0, "2026-11-05", "Mushroom masala dinner", "Marcus Samuel"),
]

def generate_consumption_history():
    records = []
    base_date = datetime(2026, 11, 4)
    cid = 100
    daily_rates = {
        "ING001": (5.0, "Tomato Soup & Gravies"),
        "ING002": (4.0, "Curry base & Biryani"),
        "ING003": (3.5, "Roasted potatoes & Biryani"),
        "ING004": (2.0, "Palak paneer & Soups"),
        "ING005": (1.5, "Mushroom masala"),
        "ING006": (2.5, "Paneer butter masala"),
        "ING007": (3.0, "Sauces, Desserts, Tea"),
        "ING008": (1.0, "Pastas & Pizzas"),
        "ING009": (4.0, "Kadhai Chicken"),
        "ING010": (1.5, "Kadhai & Biryani"),
    }
    for days_back in range(14, 0, -1):
        dt = (base_date - timedelta(days=days_back)).strftime("%Y-%m-%d")
        for ing_id, (avg_qty, dish) in daily_rates.items():
            cid += 1
            qty = round(avg_qty * (0.85 + (cid % 30) / 100.0), 1)
            records.append((f"CON{cid}", ing_id, qty, dt, dish, "Standard service"))
    return records

def seed():
    batch = []
    print("Preparing seed batch...")
    for tbl in [
        "STOCK_MOVEMENTS", "USERS", "VECTOR_STORAGE", "CONSUMPTION",
        "WASTE_RECORDS", "RECIPE_INGREDIENTS", "RECIPES", "INVENTORY",
        "INGREDIENTS", "SUPPLIERS"
    ]:
        batch.append((f"DELETE FROM {tbl}", []))

    for s in SUPPLIERS:
        batch.append(("INSERT INTO SUPPLIERS (supplier_id, supplier_name, contact, lead_time_days, rating, min_order_qty) VALUES (?, ?, ?, ?, ?, ?)", list(s)))

    for ing in INGREDIENTS:
        batch.append(("INSERT INTO INGREDIENTS (ingredient_id, ingredient_name, category, unit, unit_price, reorder_level, reorder_quantity, storage_temp, shelf_life_days) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", list(ing)))

    for inv in INVENTORY_BATCHES:
        batch.append(("INSERT INTO INVENTORY (inventory_id, ingredient_id, batch_number, quantity, initial_quantity, purchase_date, expiry_date, unit_price, storage_location, supplier_id, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", list(inv)))

    for rec in RECIPES:
        batch.append(("INSERT INTO RECIPES (recipe_id, recipe_name, category, prep_time, servings, instructions, estimated_cost) VALUES (?, ?, ?, ?, ?, ?, ?)", list(rec)))

    for ri in RECIPE_INGREDIENTS:
        batch.append(("INSERT INTO RECIPE_INGREDIENTS (recipe_id, ingredient_id, required_quantity, unit) VALUES (?, ?, ?, ?)", list(ri)))

    for w in HISTORICAL_WASTE:
        batch.append(("INSERT INTO WASTE_RECORDS (waste_id, ingredient_id, batch_number, quantity_wasted, waste_date, waste_reason, monetary_loss) VALUES (?, ?, ?, ?, ?, ?, ?)", list(w)))

    for u in USERS:
        batch.append(("INSERT INTO USERS (user_id, username, full_name, role, email, status) VALUES (?, ?, ?, ?, ?, ?)", list(u)))

    for m in STOCK_MOVEMENTS:
        batch.append(("INSERT INTO STOCK_MOVEMENTS (movement_id, ingredient_id, batch_number, movement_type, quantity, movement_date, reason, performed_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", list(m)))

    for c in generate_consumption_history():
        batch.append(("INSERT INTO CONSUMPTION (consumption_id, ingredient_id, quantity_used, consumption_date, dish_name, notes) VALUES (?, ?, ?, ?, ?, ?)", list(c)))

    for rec in RECIPES:
        doc_id = f"VEC_{rec[0]}"
        content = f"Recipe: {rec[1]}. Category: {rec[2]}. Prep time: {rec[3]} mins. Servings: {rec[4]}. Instructions: {rec[5]}"
        batch.append(("INSERT INTO VECTOR_STORAGE (doc_id, doc_type, title, content, embedding_json) VALUES (?, ?, ?, ?, ?)", [doc_id, "RECIPE", rec[1], content, "[]"]))

    print(f"Executing batch of {len(batch)} statements...")
    success = db_client.execute_batch(batch)
    if success:
        print("All records successfully seeded into IBM Db2 and SQLite mirror!")
    else:
        print("Notice: check database tables status.")

if __name__ == "__main__":
    seed()
