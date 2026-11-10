"""Database schema definition and sample data population for StockSage.

Defines tables for PRODUCTS, SALES, INVENTORY_BATCHES, and SUPPLIERS,
and seeds realistic retail grocery and dairy dataset for evaluation.
"""

from datetime import date, datetime, timedelta
import logging

logger = logging.getLogger("StockSage.Setup")

# Table DDL statements in IBM Db2 SQL syntax
DB2_TABLE_DDL = {
    "SUPPLIERS": """
        CREATE TABLE SUPPLIERS (
            supplier_id INT NOT NULL PRIMARY KEY,
            supplier_name VARCHAR(150) NOT NULL,
            lead_time_days INT NOT NULL,
            contact_details VARCHAR(150)
        )
    """,
    "PRODUCTS": """
        CREATE TABLE PRODUCTS (
            product_id INT NOT NULL PRIMARY KEY,
            product_name VARCHAR(150) NOT NULL,
            category VARCHAR(50) NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            reorder_level INT NOT NULL,
            supplier_id INT NOT NULL,
            CONSTRAINT fk_supplier FOREIGN KEY (supplier_id) REFERENCES SUPPLIERS(supplier_id)
        )
    """,
    "INVENTORY_BATCHES": """
        CREATE TABLE INVENTORY_BATCHES (
            batch_id INT NOT NULL PRIMARY KEY,
            product_id INT NOT NULL,
            available_quantity INT NOT NULL,
            expiry_date DATE NOT NULL,
            received_date DATE NOT NULL,
            CONSTRAINT fk_batch_product FOREIGN KEY (product_id) REFERENCES PRODUCTS(product_id)
        )
    """,
    "SALES": """
        CREATE TABLE SALES (
            sale_id INT NOT NULL PRIMARY KEY,
            product_id INT NOT NULL,
            quantity_sold INT NOT NULL,
            sale_date DATE NOT NULL,
            revenue DECIMAL(10,2) NOT NULL,
            CONSTRAINT fk_sale_product FOREIGN KEY (product_id) REFERENCES PRODUCTS(product_id)
        )
    """,
}

# Indexes for fast operational reporting & analytics
DB2_INDEX_DDL = [
    "CREATE INDEX idx_batches_product ON INVENTORY_BATCHES(product_id)",
    "CREATE INDEX idx_batches_expiry ON INVENTORY_BATCHES(expiry_date)",
    "CREATE INDEX idx_sales_product ON SALES(product_id)",
    "CREATE INDEX idx_sales_date ON SALES(sale_date)",
]


def drop_tables(db):
    """Drop existing tables in reverse dependency order."""
    tables = ["SALES", "INVENTORY_BATCHES", "PRODUCTS", "SUPPLIERS"]
    for table in tables:
        try:
            if db.is_mock:
                db.execute_non_query(f"DROP TABLE IF EXISTS {table}")
            else:
                db.execute_non_query(f"DROP TABLE {table}")
                logger.info("Dropped existing table %s", table)
        except Exception:
            pass  # Table did not exist


def create_schema(db):
    """Create all required relational tables and indexes."""
    for table_name, ddl in DB2_TABLE_DDL.items():
        try:
            if db.is_mock:
                # Use IF NOT EXISTS for in-memory SQLite simulator
                ddl_clean = ddl.replace(f"CREATE TABLE {table_name}", f"CREATE TABLE IF NOT EXISTS {table_name}")
                db.execute_non_query(ddl_clean)
            else:
                db.execute_non_query(ddl)
            logger.info("Created table: %s", table_name)
        except Exception as e:
            logger.error("Failed to create table %s: %s", table_name, e)
            raise e

    # Create indexes
    for idx_sql in DB2_INDEX_DDL:
        try:
            db.execute_non_query(idx_sql)
        except Exception:
            pass


def seed_sample_data(db):
    """Seed realistic grocery and dairy data with varying shelf-lives and sales."""
    today = date.today()

    # 1. Suppliers
    suppliers = [
        (1, "Anand Regional Dairy Co-op", 1, "+91-98112-23344, dispatch@ananddairy.in"),
        (2, "Golden Harvest Bakeries", 1, "+91-98223-34455, orders@goldenharvest.com"),
        (3, "GreenField Fresh Farms", 2, "+91-98334-45566, produce@greenfield.org"),
        (4, "Kisan Agro Foods & Pulses", 4, "+91-98445-56677, sales@kisanagro.com"),
        (5, "Himalayan Spring Beverages", 3, "+91-98556-67788, supply@himalayanspring.in"),
    ]

    for s in suppliers:
        db.execute_non_query(
            "INSERT INTO SUPPLIERS (supplier_id, supplier_name, lead_time_days, contact_details) VALUES (?, ?, ?, ?)",
            s,
        )

    # 2. Products
    products = [
        (101, "Fresh Cow Milk (1L)", "Dairy", 64.00, 25, 1),
        (102, "Full Cream Milk (500ml)", "Dairy", 35.00, 30, 1),
        (103, "Fresh Malai Paneer (200g)", "Dairy", 95.00, 15, 1),
        (104, "Plain Curd / Dahi (400g)", "Dairy", 40.00, 20, 1),
        (105, "Salted Butter (100g)", "Dairy", 58.00, 10, 1),
        (106, "Greek Natural Yogurt (100g)", "Dairy", 50.00, 12, 1),
        (107, "Cheddar Cheese Block (200g)", "Dairy", 145.00, 8, 1),
        (108, "Whole Wheat Bread (400g)", "Bakery", 45.00, 15, 2),
        (109, "Brown Multigrain Bread (400g)", "Bakery", 55.00, 10, 2),
        (110, "Farm Fresh Eggs (Pack of 12)", "Dairy/Poultry", 96.00, 15, 3),
        (111, "Fresh Bananas (1 Dozen)", "Fresh Produce", 60.00, 12, 3),
        (112, "Shimla Apples (1kg)", "Fresh Produce", 160.00, 10, 3),
        (113, "Basmati Rice Royal (5kg)", "Grains & Staples", 480.00, 5, 4),
        (114, "Sharbati Atta (5kg)", "Grains & Staples", 230.00, 6, 4),
        (115, "Toor Dal Premium (1kg)", "Grains & Staples", 165.00, 8, 4),
        (116, "Cold-Pressed Mustard Oil (1L)", "Grains & Staples", 175.00, 6, 4),
        (117, "Fresh Squeezed Orange Juice (1L)", "Beverages", 120.00, 8, 5),
        (118, "Organic Green Tea Bags (25 count)", "Beverages", 190.00, 5, 5),
    ]

    for p in products:
        db.execute_non_query(
            "INSERT INTO PRODUCTS (product_id, product_name, category, unit_price, reorder_level, supplier_id) VALUES (?, ?, ?, ?, ?, ?)",
            p,
        )

    # 3. Inventory Batches (with deliberate near-expiry and critical expiry)
    batches = [
        # Milk - critical expiry (tomorrow) and low stock
        (1, 101, 8, (today + timedelta(days=1)).isoformat(), (today - timedelta(days=2)).isoformat()),
        (2, 101, 12, (today + timedelta(days=2)).isoformat(), (today - timedelta(days=1)).isoformat()),
        # Full Cream Milk - expiring in 2 and 3 days
        (3, 102, 10, (today + timedelta(days=2)).isoformat(), (today - timedelta(days=1)).isoformat()),
        (4, 102, 18, (today + timedelta(days=3)).isoformat(), today.isoformat()),
        # Paneer - 1 batch expiring tomorrow (critical!), 1 fresh
        (5, 103, 5, (today + timedelta(days=1)).isoformat(), (today - timedelta(days=3)).isoformat()),
        (6, 103, 14, (today + timedelta(days=4)).isoformat(), today.isoformat()),
        # Curd - 1 batch near expiry (2 days), 1 batch fresh (5 days)
        (7, 104, 6, (today + timedelta(days=2)).isoformat(), (today - timedelta(days=2)).isoformat()),
        (8, 104, 22, (today + timedelta(days=5)).isoformat(), today.isoformat()),
        # Butter - long expiry (35 days)
        (9, 105, 25, (today + timedelta(days=35)).isoformat(), (today - timedelta(days=10)).isoformat()),
        # Greek Yogurt - expiring in 3 days
        (10, 106, 7, (today + timedelta(days=3)).isoformat(), (today - timedelta(days=4)).isoformat()),
        # Cheddar Cheese - plenty of shelf life (50 days)
        (11, 107, 16, (today + timedelta(days=50)).isoformat(), (today - timedelta(days=15)).isoformat()),
        # Whole Wheat Bread - expiring today & tomorrow!
        (12, 108, 4, today.isoformat(), (today - timedelta(days=3)).isoformat()),
        (13, 108, 9, (today + timedelta(days=2)).isoformat(), (today - timedelta(days=1)).isoformat()),
        # Brown Bread - expiring in 2 days
        (14, 109, 8, (today + timedelta(days=2)).isoformat(), (today - timedelta(days=2)).isoformat()),
        # Eggs - 10 days remaining
        (15, 110, 24, (today + timedelta(days=10)).isoformat(), (today - timedelta(days=4)).isoformat()),
        # Bananas - expiring in 2 days
        (16, 111, 6, (today + timedelta(days=2)).isoformat(), (today - timedelta(days=2)).isoformat()),
        # Apples - 6 days remaining
        (17, 112, 15, (today + timedelta(days=6)).isoformat(), (today - timedelta(days=2)).isoformat()),
        # Basmati Rice - 180 days remaining
        (18, 113, 14, (today + timedelta(days=180)).isoformat(), (today - timedelta(days=30)).isoformat()),
        # Atta - 90 days remaining (LOW STOCK: 4 remaining vs reorder level 6!)
        (19, 114, 4, (today + timedelta(days=90)).isoformat(), (today - timedelta(days=20)).isoformat()),
        # Toor Dal - 120 days remaining
        (20, 115, 18, (today + timedelta(days=120)).isoformat(), (today - timedelta(days=15)).isoformat()),
        # Mustard Oil - 150 days remaining
        (21, 116, 12, (today + timedelta(days=150)).isoformat(), (today - timedelta(days=10)).isoformat()),
        # Orange Juice - expiring in 3 days (CRITICAL: 5 units remaining vs reorder level 8!)
        (22, 117, 5, (today + timedelta(days=3)).isoformat(), (today - timedelta(days=3)).isoformat()),
        # Green Tea - 160 days remaining (Slow moving)
        (23, 118, 15, (today + timedelta(days=160)).isoformat(), (today - timedelta(days=20)).isoformat()),
    ]

    for b in batches:
        db.execute_non_query(
            "INSERT INTO INVENTORY_BATCHES (batch_id, product_id, available_quantity, expiry_date, received_date) VALUES (?, ?, ?, ?, ?)",
            b,
        )

    # 4. Sales History (Last 14 days of realistic transactions)
    # Milk and Bread sell every day in high volume; staples sell moderately; tea sells slowly.
    daily_sales_profile = {
        101: (22, 64.00),   # Milk 1L: avg 22 units/day
        102: (18, 35.00),   # Milk 500ml: avg 18 units/day
        103: (8, 95.00),    # Paneer: avg 8 units/day
        104: (14, 40.00),   # Curd: avg 14 units/day
        105: (3, 58.00),    # Butter: avg 3 units/day
        106: (4, 50.00),    # Greek Yogurt: avg 4 units/day
        107: (2, 145.00),   # Cheese: avg 2 units/day
        108: (12, 45.00),   # Whole Wheat Bread: avg 12 units/day
        109: (6, 55.00),    # Brown Bread: avg 6 units/day
        110: (9, 96.00),    # Eggs: avg 9 units/day
        111: (10, 60.00),   # Bananas: avg 10 units/day
        112: (5, 160.00),   # Apples: avg 5 units/day
        113: (2, 480.00),   # Basmati Rice: avg 2 units/day
        114: (3, 230.00),   # Atta: avg 3 units/day
        115: (3, 165.00),   # Toor Dal: avg 3 units/day
        116: (2, 175.00),   # Mustard Oil: avg 2 units/day
        117: (4, 120.00),   # Orange Juice: avg 4 units/day
        118: (1, 190.00),   # Green Tea: avg ~0.5 units/day
    }

    sale_id = 1
    import random
    # Deterministic seed for reproducible tests
    random.seed(42)

    for day_offset in range(14, 0, -1):
        sale_date = (today - timedelta(days=day_offset)).isoformat()
        for prod_id, (base_qty, price) in daily_sales_profile.items():
            # Add small random variation (+- 20%)
            jitter = random.choice([-2, -1, 0, 1, 2])
            qty = max(1, base_qty + jitter)
            if prod_id == 118 and day_offset % 2 == 1:
                # Green tea sells every other day
                continue
            rev = round(qty * price, 2)
            db.execute_non_query(
                "INSERT INTO SALES (sale_id, product_id, quantity_sold, sale_date, revenue) VALUES (?, ?, ?, ?, ?)",
                (sale_id, prod_id, qty, sale_date, rev),
            )
            sale_id += 1

    logger.info("Successfully seeded database with %d products, %d batches, and %d sales records.",
                len(products), len(batches), sale_id - 1)


def initialize_database(db, force_recreate=False):
    """Orchestrate schema creation and seed data."""
    if force_recreate:
        drop_tables(db)
    create_schema(db)
    seed_sample_data(db)


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    from src.db_connection import db_manager
    print("Initializing StockSage Database against IBM Db2...")
    initialize_database(db_manager, force_recreate=True)
    print("Database initialization complete on IBM Db2!")
