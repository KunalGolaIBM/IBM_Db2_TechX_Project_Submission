"""
Db2 Copilot Database Initializer & Seed Script
Creates relational tables (customers, orders, payments, refunds, query_audit)
and policy documents with vector embeddings (using fastembed).
"""
import sys
import os
import random
from datetime import datetime, timedelta
from fastembed import TextEmbedding

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db import get_connection, execute_non_query, execute_query
import ibm_db

# Policies data
POLICIES_DATA = [
    {
        "id": 1,
        "title": "Standard Return and Refund Window",
        "category": "General",
        "content": (
            "Customers may request a full refund within 30 days of the delivery date for standard items. "
            "Items must be in original condition with tags and packaging intact. Refunds are credited back "
            "to the original payment method within 5 to 7 business days. Standard shipping fees are non-refundable."
        ),
    },
    {
        "id": 2,
        "title": "Electronics and Perishables Policy",
        "category": "Electronics & Perishables",
        "content": (
            "Electronics items are subject to a strict 14-day return window from the confirmed delivery date. "
            "Opened electronics are subject to a 10% restocking fee unless defective. Perishable items, "
            "fresh groceries, and opened consumable goods are strictly non-refundable unless they arrived spoiled or expired."
        ),
    },
    {
        "id": 3,
        "title": "Damaged, Defective, or Wrong Items",
        "category": "Damaged Goods",
        "content": (
            "If an order arrives damaged, defective, or contains the incorrect item, the customer is entitled to a "
            "100% full refund including all shipping fees, or an immediate free replacement. Dispute claims for damaged "
            "goods must be submitted within 7 calendar days of delivery with photo evidence."
        ),
    },
    {
        "id": 4,
        "title": "VIP and Loyalty Tier Privileges",
        "category": "VIP & Loyalty",
        "content": (
            "Gold and Platinum tier loyalty members receive an extended 60-day return window on all eligible products, "
            "free expedited return shipping, and instant courtesy refund approval for any claims under $100 without "
            "requiring item return."
        ),
    },
]


def drop_existing_tables(conn):
    """Drop tables in reverse dependency order."""
    tables = ["QUERY_AUDIT", "REFUNDS", "PAYMENTS", "ORDERS", "CUSTOMERS", "POLICIES"]
    print("Dropping existing tables if any...")
    for t in tables:
        try:
            ibm_db.exec_immediate(conn, f"DROP TABLE {t}")
            print(f"  Dropped {t}")
        except Exception:
            pass


def create_schema(conn):
    """Create all required relational and vector tables."""
    print("Creating relational and vector tables...")

    # Customers
    ibm_db.exec_immediate(
        conn,
        """
    CREATE TABLE CUSTOMERS (
        customer_id INT NOT NULL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(100) NOT NULL,
        tier VARCHAR(20) NOT NULL,
        created_at DATE NOT NULL
    )
    """,
    )
    print("  ✅ CUSTOMERS table created")

    # Orders
    ibm_db.exec_immediate(
        conn,
        """
    CREATE TABLE ORDERS (
        order_id INT NOT NULL PRIMARY KEY,
        customer_id INT NOT NULL,
        order_date DATE NOT NULL,
        delivery_date DATE,
        status VARCHAR(30) NOT NULL,
        item_name VARCHAR(120) NOT NULL,
        item_category VARCHAR(50) NOT NULL,
        item_price DECIMAL(10,2) NOT NULL,
        shipping_fee DECIMAL(10,2) NOT NULL,
        total_amount DECIMAL(10,2) NOT NULL,
        CONSTRAINT fk_order_cust FOREIGN KEY (customer_id) REFERENCES CUSTOMERS(customer_id)
    )
    """,
    )
    print("  ✅ ORDERS table created")

    # Payments
    ibm_db.exec_immediate(
        conn,
        """
    CREATE TABLE PAYMENTS (
        payment_id INT NOT NULL PRIMARY KEY,
        order_id INT NOT NULL,
        payment_method VARCHAR(30) NOT NULL,
        payment_status VARCHAR(20) NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        transaction_time TIMESTAMP NOT NULL,
        CONSTRAINT fk_pay_order FOREIGN KEY (order_id) REFERENCES ORDERS(order_id)
    )
    """,
    )
    print("  ✅ PAYMENTS table created")

    # Refunds (with requested_at as the dispute / request date)
    ibm_db.exec_immediate(
        conn,
        """
    CREATE TABLE REFUNDS (
        refund_id INT NOT NULL PRIMARY KEY,
        order_id INT NOT NULL,
        amount DECIMAL(10,2) NOT NULL,
        reason VARCHAR(200) NOT NULL,
        status VARCHAR(20) NOT NULL,
        requested_at DATE NOT NULL,
        processed_at DATE,
        CONSTRAINT fk_ref_order FOREIGN KEY (order_id) REFERENCES ORDERS(order_id)
    )
    """,
    )
    print("  ✅ REFUNDS table created (with requested_at dispute date)")

    # Policies with VECTOR(384, FLOAT32)
    ibm_db.exec_immediate(
        conn,
        """
    CREATE TABLE POLICIES (
        policy_id INT NOT NULL PRIMARY KEY,
        policy_title VARCHAR(100) NOT NULL,
        category VARCHAR(50) NOT NULL,
        content VARCHAR(1500) NOT NULL,
        embedding VECTOR(384, FLOAT32) NOT NULL
    )
    """,
    )
    print("  ✅ POLICIES table created (VECTOR 384-dim)")

    # Query Audit Log
    ibm_db.exec_immediate(
        conn,
        """
    CREATE TABLE QUERY_AUDIT (
        audit_id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        question VARCHAR(1000) NOT NULL,
        generated_sql VARCHAR(2000),
        sql_status VARCHAR(50) NOT NULL,
        verdict VARCHAR(8000),
        created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP
    )
    """,
    )
    print("  ✅ QUERY_AUDIT table created (clean slate)")


def seed_relational_data(conn):
    """Seed ~200 rows of relational e-commerce data with specific varied scenarios."""
    print("Seeding relational e-commerce data with varied dispute cases...")

    # 1. Customers (30 customers)
    # Explicitly define first 5 customers for predictable test scenarios:
    # 1: Alice Smith (Standard)
    # 2: Bob Johnson (Gold - VIP)
    # 3: Charlie Williams (Standard)
    # 4: Diana Brown (Platinum - VIP)
    # 5: Evan Jones (Standard)
    first_names = ["Alice", "Bob", "Charlie", "Diana", "Evan", "Fiona", "George", "Hannah", "Ian", "Julia"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    tiers = [
        "Standard",  # 1: Alice Smith
        "Gold",      # 2: Bob Johnson (VIP)
        "Standard",  # 3: Charlie Williams
        "Platinum",  # 4: Diana Brown (VIP)
        "Standard",  # 5: Evan Jones
    ] + ["Standard"] * 15 + ["Gold"] * 6 + ["Platinum"] * 4

    customers = []
    base_date = datetime(2026, 1, 1)
    for cid in range(1, 31):
        name = f"{first_names[(cid - 1) % 10]} {last_names[(cid - 1) // 3]}"
        email = f"{name.lower().replace(' ', '.')}@example.com"
        tier = tiers[cid - 1]
        join_date = (base_date + timedelta(days=cid * 3)).strftime("%Y-%m-%d")
        customers.append((cid, name, email, tier, join_date))
        sql = f"INSERT INTO CUSTOMERS VALUES ({cid}, '{name}', '{email}', '{tier}', '{join_date}')"
        ibm_db.exec_immediate(conn, sql)
    print(f"  Inserted {len(customers)} customers.")

    # 2. Orders (100 orders)
    catalog = [
        ("Wireless Noise-Canceling Headphones", "Electronics", 149.99, 9.99),
        ("Smart 4K Ultra HD TV 55-inch", "Electronics", 499.99, 29.99),
        ("Classic Cotton Crewneck T-Shirt", "Clothing", 24.99, 4.99),
        ("Artisan Swiss Chocolate Box 500g", "Perishables", 35.00, 5.00),
        ("Mechanical Gaming Keyboard", "Electronics", 89.99, 5.99),
        ("Waterproof Winter Parka Jacket", "Clothing", 179.99, 12.99),
        ("Organic Fair-Trade Coffee Beans 1kg", "Perishables", 22.50, 4.50),
        ("Leather Formal Oxford Shoes", "Clothing", 119.99, 8.99),
        ("Cloud Storage Pro 1-Year License", "Digital", 59.99, 0.00),
        ("Cybersecurity Suite Anti-Malware", "Digital", 39.99, 0.00),
    ]

    orders = []
    # Seed specific key test orders first:
    # Order 101: Alice Smith (Standard), Electronics, delivered 2026-09-04
    # Order 102: Bob Johnson (Gold VIP), Electronics, delivered 2026-09-05
    # Order 103: Charlie Williams (Standard), Clothing, delivered 2026-09-06
    # Order 104: Diana Brown (Platinum VIP), Perishables, delivered 2026-09-07
    # Order 131: Alice Smith (Standard), Clothing (for multiple refund test)
    # Order 132: Bob Johnson (Gold VIP), Electronics (for multiple refund test)
    # Order 134: Diana Brown (Platinum VIP), Digital (for multiple refund test)

    for oid in range(101, 201):
        idx = oid - 101
        cid = (idx % 30) + 1
        
        # Override specific customer assignments for multiple-refund test cases
        if oid == 131:
            cid = 1  # Alice Smith gets second order
        elif oid == 132:
            cid = 2  # Bob Johnson gets second order
        elif oid == 134:
            cid = 4  # Diana Brown gets second order

        item_name, item_cat, item_price, shipping = catalog[idx % len(catalog)]
        status = "DELIVERED"
        order_dt = datetime(2026, 9, 1) + timedelta(days=(idx * 2) % 50)
        deliv_dt = order_dt + timedelta(days=3)
        total = round(item_price + shipping, 2)

        order_date_str = order_dt.strftime("%Y-%m-%d")
        deliv_str = f"'{deliv_dt.strftime('%Y-%m-%d')}'"

        sql = (
            f"INSERT INTO ORDERS VALUES ("
            f"{oid}, {cid}, '{order_date_str}', {deliv_str}, '{status}', "
            f"'{item_name}', '{item_cat}', {item_price}, {shipping}, {total})"
        )
        ibm_db.exec_immediate(conn, sql)
        orders.append((oid, cid, total, status, order_dt, deliv_dt))
    print(f"  Inserted {len(orders)} orders.")

    # 3. Payments (100 payments)
    methods = ["CREDIT_CARD", "DEBIT_CARD", "UPI", "STORE_CREDIT"]
    for idx, (oid, cid, total, status, order_dt, deliv_dt) in enumerate(orders):
        pid = 500 + idx + 1
        method = methods[idx % len(methods)]
        pstatus = "COMPLETED"
        tx_time = f"{order_dt.strftime('%Y-%m-%d')} 14:30:00"
        sql = f"INSERT INTO PAYMENTS VALUES ({pid}, {oid}, '{method}', '{pstatus}', {total}, '{tx_time}')"
        ibm_db.exec_immediate(conn, sql)
    print(f"  Inserted {len(orders)} payments.")

    # 4. Refunds (explicitly seeded varied dispute cases)
    # We define specific dispute scenarios:
    refund_records = [
        # Case 1: Order 101 - Approved within 7-day damaged goods window
        # Alice Smith (Standard), Headphones, delivered 2026-09-04, requested 2026-09-08 (4 days elapsed <= 7 days)
        (901, 101, 159.98, "Damaged item in transit", "PENDING", "2026-09-08", None),

        # Case 2: Order 102 - VIP 60-day exception
        # Bob Johnson (Gold VIP), Smart TV ($529.98), delivered 2026-09-05, requested 2026-10-15 (40 days elapsed > 14/30d, but <= 60d VIP window)
        (902, 102, 529.98, "Screen flickering periodically", "PENDING", "2026-10-15", None),

        # Case 3: Order 103 - Denied Too Late (> 30-day window)
        # Charlie Williams (Standard), T-Shirt ($29.98), delivered 2026-09-06, requested 2026-10-25 (49 days elapsed > 30d window)
        (903, 103, 29.98, "Customer changed mind", "REJECTED", "2026-10-25", "2026-10-26"),

        # Case 4: Order 104 - VIP Courtesy Instant Refund under $100
        # Diana Brown (Platinum VIP), Swiss Chocolate ($40.00), delivered 2026-09-07, requested 2026-09-17 (10 days elapsed, VIP < $100)
        (904, 104, 40.00, "Box arrived crushed", "APPROVED", "2026-09-17", "2026-09-17"),

        # Multiple-refund test cases:
        # Alice Smith second refund (Order 131)
        (905, 131, 29.98, "Wrong size clothing delivered", "APPROVED", "2026-09-20", "2026-09-22"),

        # Bob Johnson second refund (Order 132)
        (906, 132, 95.98, "Item defective / stopped working", "APPROVED", "2026-09-22", "2026-09-24"),

        # Diana Brown second refund (Order 134)
        (907, 134, 59.99, "Late delivery beyond promised date", "PROCESSED", "2026-09-25", "2026-09-27"),
    ]

    # Additional realistic background refunds to total ~35
    extra_reasons = [
        "Item incompatible with setup",
        "Wrong item delivered",
        "Arrived after expected event date",
        "Missing user manual and cables",
    ]
    for i in range(8, 36):
        rid = 900 + i
        oid = 104 + (i * 2)
        if oid > 200:
            oid = 105 + (i % 50)
        reason = extra_reasons[i % len(extra_reasons)]
        r_stat = "APPROVED" if i % 2 == 0 else "PENDING"
        req_date = "2026-09-15"
        proc_date = "2026-09-17" if r_stat == "APPROVED" else None
        refund_records.append((rid, oid, 59.99, reason, r_stat, req_date, proc_date))

    for rec in refund_records:
        rid, oid, amt, rsn, stat, req_d, proc_d = rec
        proc_str = f"'{proc_d}'" if proc_d and proc_d != "NULL" else "NULL"
        sql = (
            f"INSERT INTO REFUNDS VALUES ("
            f"{rid}, {oid}, {amt}, '{rsn}', '{stat}', '{req_d}', {proc_str})"
        )
        ibm_db.exec_immediate(conn, sql)
    print(f"  Inserted {len(refund_records)} refunds with specific test scenarios.")


def seed_policy_embeddings(conn):
    """Embed the 4 policy documents using fastembed and insert into POLICIES table."""
    print("Embedding policy documents using fastembed (BAAI/bge-small-en-v1.5)...")
    embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    texts = [f"{p['title']}: {p['content']}" for p in POLICIES_DATA]
    embeddings = list(embedding_model.embed(texts))

    print("Inserting policies and vectors into Db2...")
    for p, emb in zip(POLICIES_DATA, embeddings):
        vec_list = [round(float(x), 6) for x in emb.tolist()]
        vec_str = str(vec_list)
        sql = (
            f"INSERT INTO POLICIES (policy_id, policy_title, category, content, embedding) "
            f"VALUES ({p['id']}, '{p['title']}', '{p['category']}', '{p['content']}', "
            f"VECTOR('{vec_str}', 384, FLOAT32))"
        )
        ibm_db.exec_immediate(conn, sql)
        print(f"  ✅ Policy {p['id']} embedded & inserted: '{p['title']}'")


def verify_counts(conn):
    """Verify total row counts across all tables."""
    print("\n" + "=" * 50)
    print("Database Row Counts Verification")
    print("=" * 50)
    for table in ["CUSTOMERS", "ORDERS", "PAYMENTS", "REFUNDS", "POLICIES", "QUERY_AUDIT"]:
        res = execute_query(conn, f"SELECT COUNT(*) AS CNT FROM {table}")
        count = res[0]["cnt"] if res else 0
        print(f"  {table:<15}: {count} rows")


def main():
    print("=" * 60)
    print("Db2 Copilot Database Setup & Seeding")
    print("=" * 60)
    conn = get_connection()
    try:
        drop_existing_tables(conn)
        create_schema(conn)
        seed_relational_data(conn)
        seed_policy_embeddings(conn)
        verify_counts(conn)
    finally:
        ibm_db.close(conn)
    print("=" * 60)
    print("SEEDING COMPLETED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    main()
