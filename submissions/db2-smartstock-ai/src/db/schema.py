"""
Database Schema Initialization for IBM Db2 and SQLite Mirror.
Creates relational tables for:
- SUPPLIERS
- INGREDIENTS
- INVENTORY (Batch-level tracking)
- CONSUMPTION
- RECIPES
- RECIPE_INGREDIENTS
- WASTE_RECORDS
- PURCHASE_ORDERS
- DEMAND_FORECASTS
- VECTOR_STORAGE (Embeddings for Recipe RAG)
- STOCK_MOVEMENTS (Audited inventory movement history)
- USERS (System user management)
"""

import logging
from db.db2_client import db_client

logger = logging.getLogger(__name__)

DB2_TABLES = [
    """
    CREATE TABLE SUPPLIERS (
        supplier_id VARCHAR(50) NOT NULL PRIMARY KEY,
        supplier_name VARCHAR(100) NOT NULL,
        contact VARCHAR(100),
        lead_time_days INTEGER DEFAULT 2,
        rating DECIMAL(3, 2) DEFAULT 4.5,
        min_order_qty DECIMAL(10, 2) DEFAULT 5.0
    )
    """,
    """
    CREATE TABLE INGREDIENTS (
        ingredient_id VARCHAR(50) NOT NULL PRIMARY KEY,
        ingredient_name VARCHAR(100) NOT NULL,
        category VARCHAR(50) NOT NULL,
        unit VARCHAR(20) NOT NULL,
        unit_price DECIMAL(10, 2) NOT NULL,
        reorder_level DECIMAL(10, 2) DEFAULT 10.0,
        reorder_quantity DECIMAL(10, 2) DEFAULT 25.0,
        storage_temp DECIMAL(5, 2) DEFAULT 4.0,
        shelf_life_days INTEGER DEFAULT 7
    )
    """,
    """
    CREATE TABLE INVENTORY (
        inventory_id VARCHAR(50) NOT NULL PRIMARY KEY,
        ingredient_id VARCHAR(50) NOT NULL,
        batch_number VARCHAR(50) NOT NULL,
        quantity DECIMAL(10, 2) NOT NULL,
        initial_quantity DECIMAL(10, 2) NOT NULL,
        purchase_date VARCHAR(20) NOT NULL,
        expiry_date VARCHAR(20) NOT NULL,
        unit_price DECIMAL(10, 2) NOT NULL,
        storage_location VARCHAR(50) DEFAULT 'Refrigerator',
        supplier_id VARCHAR(50),
        status VARCHAR(20) DEFAULT 'Active'
    )
    """,
    """
    CREATE TABLE CONSUMPTION (
        consumption_id VARCHAR(50) NOT NULL PRIMARY KEY,
        ingredient_id VARCHAR(50) NOT NULL,
        quantity_used DECIMAL(10, 2) NOT NULL,
        consumption_date VARCHAR(20) NOT NULL,
        dish_name VARCHAR(100),
        notes VARCHAR(255)
    )
    """,
    """
    CREATE TABLE RECIPES (
        recipe_id VARCHAR(50) NOT NULL PRIMARY KEY,
        recipe_name VARCHAR(100) NOT NULL,
        category VARCHAR(50) DEFAULT 'Main Course',
        prep_time INTEGER DEFAULT 30,
        servings INTEGER DEFAULT 4,
        instructions VARCHAR(2000),
        estimated_cost DECIMAL(10, 2) DEFAULT 150.00
    )
    """,
    """
    CREATE TABLE RECIPE_INGREDIENTS (
        recipe_id VARCHAR(50) NOT NULL,
        ingredient_id VARCHAR(50) NOT NULL,
        required_quantity DECIMAL(10, 2) NOT NULL,
        unit VARCHAR(20) NOT NULL,
        PRIMARY KEY (recipe_id, ingredient_id)
    )
    """,
    """
    CREATE TABLE WASTE_RECORDS (
        waste_id VARCHAR(50) NOT NULL PRIMARY KEY,
        ingredient_id VARCHAR(50) NOT NULL,
        batch_number VARCHAR(50),
        quantity_wasted DECIMAL(10, 2) NOT NULL,
        waste_date VARCHAR(20) NOT NULL,
        waste_reason VARCHAR(100) DEFAULT 'Expired',
        monetary_loss DECIMAL(10, 2) NOT NULL
    )
    """,
    """
    CREATE TABLE PURCHASE_ORDERS (
        order_id VARCHAR(50) NOT NULL PRIMARY KEY,
        supplier_id VARCHAR(50) NOT NULL,
        ingredient_id VARCHAR(50) NOT NULL,
        quantity DECIMAL(10, 2) NOT NULL,
        unit_price DECIMAL(10, 2) NOT NULL,
        total_price DECIMAL(10, 2) NOT NULL,
        order_date VARCHAR(20) NOT NULL,
        status VARCHAR(20) DEFAULT 'Suggested',
        approved_by VARCHAR(50)
    )
    """,
    """
    CREATE TABLE DEMAND_FORECASTS (
        forecast_id VARCHAR(50) NOT NULL PRIMARY KEY,
        ingredient_id VARCHAR(50) NOT NULL,
        forecast_date VARCHAR(20) NOT NULL,
        horizon_days INTEGER NOT NULL,
        predicted_demand DECIMAL(10, 2) NOT NULL,
        model_name VARCHAR(50) NOT NULL,
        confidence_lower DECIMAL(10, 2),
        confidence_upper DECIMAL(10, 2)
    )
    """,
    """
    CREATE TABLE VECTOR_STORAGE (
        doc_id VARCHAR(50) NOT NULL PRIMARY KEY,
        doc_type VARCHAR(50) NOT NULL,
        title VARCHAR(200) NOT NULL,
        content VARCHAR(4000) NOT NULL,
        embedding_json VARCHAR(4000)
    )
    """,
    """
    CREATE TABLE STOCK_MOVEMENTS (
        movement_id VARCHAR(50) NOT NULL PRIMARY KEY,
        ingredient_id VARCHAR(50) NOT NULL,
        batch_number VARCHAR(50),
        movement_type VARCHAR(20) NOT NULL,
        quantity DECIMAL(10, 2) NOT NULL,
        movement_date VARCHAR(20) NOT NULL,
        reason VARCHAR(100),
        performed_by VARCHAR(50) DEFAULT 'Manager'
    )
    """,
    """
    CREATE TABLE USERS (
        user_id VARCHAR(50) NOT NULL PRIMARY KEY,
        username VARCHAR(50) NOT NULL,
        full_name VARCHAR(100) NOT NULL,
        role VARCHAR(50) NOT NULL,
        email VARCHAR(100),
        status VARCHAR(20) DEFAULT 'Active',
        password_hash VARCHAR(255),
        security_question VARCHAR(255),
        security_answer VARCHAR(255)
    )
    """
]

def init_database():
    """Initializes tables in IBM Db2 and SQLite."""
    print("Initializing IBM Db2 tables...")
    for ddl in DB2_TABLES:
        table_name = ddl.strip().split()[2]
        print(f"Creating table {table_name}...")
        drop_sql = f"DROP TABLE {table_name}"
        db_client.execute_db2_sql(drop_sql)
        try:
            with db_client._get_sqlite_conn() as sconn:
                sconn.execute(f"DROP TABLE IF EXISTS {table_name}")
                sconn.commit()
        except:
            pass
        
        db_client.execute_db2_sql(ddl)
        
        sqlite_ddl = ddl.replace("DECIMAL(10, 2)", "REAL").replace("DECIMAL(5, 2)", "REAL").replace("DECIMAL(3, 2)", "REAL")
        sqlite_ddl = sqlite_ddl.replace("VARCHAR(2000)", "TEXT").replace("VARCHAR(4000)", "TEXT").replace("VARCHAR", "TEXT")
        try:
            with db_client._get_sqlite_conn() as sconn:
                sconn.execute(sqlite_ddl)
                sconn.commit()
        except Exception as e:
            print(f"SQLite mirror table create error on {table_name}: {e}")

    print("All Database tables initialized successfully!")

if __name__ == "__main__":
    init_database()
