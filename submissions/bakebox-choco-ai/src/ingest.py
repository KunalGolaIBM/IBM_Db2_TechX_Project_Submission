"""
Data Ingestion & Schema Initializer for BAKEBOX Choco AI on IBM Db2 LUW.

Initializes:
1. Transactional Relational Tables: BB_ORDERS (with sargable `phone_last10` index),
   BB_ORDER_ITEMS (ON DELETE CASCADE), BB_CAKES, BB_INVENTORY, BB_RECIPES,
   BB_INGREDIENT_COMPONENTS, BB_AUDIT_LOG, and BB_USER_CONVERSATION_BUFFER.
2. Views & Stored Procedure: V_ACTIVE_BAKERY_ORDERS, V_MASKED_BAKERY_ORDERS,
   and atomic SQL PL SP_RESERVE_CAKE_STOCK (cursor lock WHERE CURRENT OF WITH RS).
3. IBM Db2 Native Vector Table: BB_CHUNKS_VECTOR (`VECTOR(384, FLOAT32)`) via DB2LlamaVS.
"""
import json
import os
import re
import sys

_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

try:
    from llama_index.core.schema import TextNode, NodeRelationship, RelatedNodeInfo
    from llama_index.vector_stores.db2 import DistanceStrategy
except ImportError:
    TextNode = None
    NodeRelationship = None
    RelatedNodeInfo = None

    class DistanceStrategy:
        COSINE = "COSINE"

from src.db import get_dbi_connection, execute_dml, execute_query


def _is_already_exists_error(err: Exception) -> bool:
    err_msg = str(err).lower()
    return "-601" in err_msg or "42710" in err_msg or "already exists" in err_msg or "duplicate" in err_msg


def _create_object_safe(conn, label: str, sql: str) -> None:
    try:
        execute_dml(conn, sql)
        print(f"  -> {label} created successfully.")
    except Exception as exc:
        if _is_already_exists_error(exc):
            print(f"  -> {label} already exists (retained).")
        else:
            print(f"  [WARNING] {label}: {exc}")


def init_relational_tables(conn) -> None:
    """Create relational tables, views, indexes, and stored procedure in IBM Db2."""
    print("Step 1: Setting up IBM Db2 Relational Schema, Indexes, Views & Stored Procedure...")

    ddl_objects = [
        ("Table BB_ORDERS", """
        CREATE TABLE BB_ORDERS (
            order_id INT NOT NULL PRIMARY KEY,
            user_id INT,
            customer_name VARCHAR(128) NOT NULL,
            customer_phone VARCHAR(32) NOT NULL,
            phone_last10 VARCHAR(10),
            order_type VARCHAR(32) DEFAULT 'DELIVERY',
            order_status VARCHAR(32) DEFAULT 'BAKING',
            total_amount DECIMAL(10, 2) NOT NULL,
            delivery_address VARCHAR(512),
            special_notes VARCHAR(512),
            created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP
        )"""),
        ("Table BB_ORDER_ITEMS", """
        CREATE TABLE BB_ORDER_ITEMS (
            item_id INT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
            order_id INT NOT NULL,
            sku_id VARCHAR(64) NOT NULL,
            item_name VARCHAR(256) NOT NULL,
            quantity INT NOT NULL,
            unit_price DECIMAL(10, 2) NOT NULL,
            cake_base VARCHAR(64) DEFAULT 'Khoaa (Eggless)',
            cake_weight VARCHAR(32) DEFAULT '1kg',
            custom_message VARCHAR(256),
            CONSTRAINT FK_BB_ORDER FOREIGN KEY (order_id) REFERENCES BB_ORDERS(order_id) ON DELETE CASCADE
        )"""),
        ("Table BB_CAKES", """
        CREATE TABLE BB_CAKES (
            cake_id INT NOT NULL PRIMARY KEY,
            name VARCHAR(256) NOT NULL,
            sku_id VARCHAR(64) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            stock_qty INT NOT NULL DEFAULT 5,
            is_eggless_available SMALLINT DEFAULT 1
        )"""),
        ("Table BB_INVENTORY", """
        CREATE TABLE BB_INVENTORY (
            ingredient_id INT NOT NULL PRIMARY KEY,
            ingredient_name VARCHAR(128) NOT NULL,
            stock_qty DECIMAL(10, 2) NOT NULL DEFAULT 0.0,
            unit VARCHAR(32) DEFAULT 'kg'
        )"""),
        ("Table BB_RECIPES", """
        CREATE TABLE BB_RECIPES (
            recipe_id INT NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            cake_id INT NOT NULL,
            ingredient_id INT NOT NULL,
            ingredient_name VARCHAR(128) NOT NULL,
            qty_needed DECIMAL(10, 2) NOT NULL,
            CONSTRAINT FK_RECIPE_CAKE FOREIGN KEY (cake_id) REFERENCES BB_CAKES(cake_id) ON DELETE CASCADE,
            CONSTRAINT FK_RECIPE_ING FOREIGN KEY (ingredient_id) REFERENCES BB_INVENTORY(ingredient_id) ON DELETE CASCADE
        )"""),
        ("Table BB_INGREDIENT_COMPONENTS", """
        CREATE TABLE BB_INGREDIENT_COMPONENTS (
            parent_ingredient_id INT NOT NULL,
            component_id INT NOT NULL,
            component_name VARCHAR(128) NOT NULL,
            qty_ratio DECIMAL(10, 4) NOT NULL,
            PRIMARY KEY (parent_ingredient_id, component_id),
            CONSTRAINT FK_COMP_PARENT FOREIGN KEY (parent_ingredient_id) REFERENCES BB_INVENTORY(ingredient_id) ON DELETE CASCADE,
            CONSTRAINT FK_COMP_CHILD FOREIGN KEY (component_id) REFERENCES BB_INVENTORY(ingredient_id) ON DELETE CASCADE
        )"""),
        ("Table BB_AUDIT_LOG", """
        CREATE TABLE BB_AUDIT_LOG (
            log_id INT NOT NULL GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            session_id VARCHAR(128) NOT NULL,
            action_type VARCHAR(64) NOT NULL,
            payload CLOB NOT NULL,
            prev_hash VARCHAR(64) NOT NULL,
            current_hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP
        )"""),
        ("Table BB_USER_CONVERSATION_BUFFER", """
        CREATE TABLE BB_USER_CONVERSATION_BUFFER (
            buffer_id INT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL,
            user_id INT DEFAULT 0,
            role VARCHAR(20) NOT NULL,
            content CLOB(32000) NOT NULL,
            ui_cards_json CLOB(32000),
            crag_status VARCHAR(50) DEFAULT 'VERIFIED',
            created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP
        )"""),
        ("View V_ACTIVE_BAKERY_ORDERS", """
        CREATE OR REPLACE VIEW V_ACTIVE_BAKERY_ORDERS AS
        SELECT O.order_id, O.customer_name, O.order_status, O.total_amount, O.created_at,
               COUNT(I.item_id) AS total_items
        FROM BB_ORDERS O
        LEFT JOIN BB_ORDER_ITEMS I ON O.order_id = I.order_id
        GROUP BY O.order_id, O.customer_name, O.order_status, O.total_amount, O.created_at
        """),
        ("View V_MASKED_BAKERY_ORDERS", """
        CREATE OR REPLACE VIEW V_MASKED_BAKERY_ORDERS AS
        SELECT
            order_id,
            SUBSTR(customer_name, 1, 1) || '****' AS masked_customer_name,
            CASE
                WHEN LENGTH(COALESCE(phone_last10, '')) >= 4
                THEN '+91 ******' || RIGHT(phone_last10, 4)
                ELSE '******'
            END AS masked_phone,
            order_type,
            order_status,
            total_amount,
            created_at
        FROM BB_ORDERS
        """),
        ("Index IDX_BB_ORDER_PHONE", "CREATE INDEX IDX_BB_ORDER_PHONE ON BB_ORDERS(phone_last10)"),
        ("Index IDX_BB_ITEM_ORDER", "CREATE INDEX IDX_BB_ITEM_ORDER ON BB_ORDER_ITEMS(order_id)"),
        ("Index IDX_BB_CAKE_SKU", "CREATE INDEX IDX_BB_CAKE_SKU ON BB_CAKES(sku_id)"),
        ("Index IDX_BB_AUDIT_PREV", "CREATE INDEX IDX_BB_AUDIT_PREV ON BB_AUDIT_LOG(prev_hash)"),
        ("Index IDX_BB_AUDIT_CURR", "CREATE INDEX IDX_BB_AUDIT_CURR ON BB_AUDIT_LOG(current_hash)"),
        ("Index IDX_BB_RECIPE_CAKE", "CREATE INDEX IDX_BB_RECIPE_CAKE ON BB_RECIPES(cake_id)"),
        ("Index IDX_BB_COMP_PARENT", "CREATE INDEX IDX_BB_COMP_PARENT ON BB_INGREDIENT_COMPONENTS(parent_ingredient_id)"),
        ("Index IDX_BB_BUF_SESSION", "CREATE INDEX IDX_BB_BUF_SESSION ON BB_USER_CONVERSATION_BUFFER(session_id)"),
        ("Sequence SEQ_BB_ORDER_ID", "CREATE SEQUENCE SEQ_BB_ORDER_ID AS INT START WITH 1105 INCREMENT BY 1 NO CACHE"),
    ]
    for label, sql in ddl_objects:
        _create_object_safe(conn, label, sql)

    # Atomic Db2 SQL PL Stored Procedure: cursor lock stays open for WHERE CURRENT OF
    sp_sql = """
    CREATE OR REPLACE PROCEDURE SP_RESERVE_CAKE_STOCK (
        IN p_cake_id INT,
        IN p_qty INT
    )
    DYNAMIC RESULT SETS 1
    LANGUAGE SQL
    BEGIN
        DECLARE v_current_stock INT DEFAULT -1;
        DECLARE v_success INT DEFAULT 0;
        DECLARE lock_cur CURSOR FOR
            SELECT stock_qty FROM BB_CAKES WHERE cake_id = p_cake_id FOR UPDATE OF stock_qty WITH RS;
        DECLARE res_cur CURSOR WITH RETURN TO CALLER FOR
            SELECT v_success AS SUCCESS FROM SYSIBM.SYSDUMMY1;

        IF p_qty > 0 THEN
            OPEN lock_cur;
            FETCH lock_cur INTO v_current_stock;
            IF v_current_stock >= p_qty THEN
                UPDATE BB_CAKES
                SET stock_qty = stock_qty - p_qty
                WHERE CURRENT OF lock_cur;
                SET v_success = 1;
            END IF;
            CLOSE lock_cur;
        END IF;

        OPEN res_cur;
    END
    """
    _create_object_safe(conn, "Stored Procedure SP_RESERVE_CAKE_STOCK", sp_sql)

    _seed_relational_data(conn)


def _seed_relational_data(conn) -> None:
    """Idempotently seed cakes, ingredients, multi-level BOM recipes, and orders."""
    seed_cakes = [
        (1, "Red Velvet Crimson Crumb Crown", "BB-RED-01-1kg", 649.00, 5, 1),
        (2, "Black Forest Classic Cherry Gateau", "BB-BLK-01-05kg", 249.00, 1, 1),
        (3, "Pineapple Classic Spiral Mirror", "BB-PIN-01-05kg", 249.00, 0, 1),
        (4, "Red Velvet Heart Love Affair", "BB-RED-02-1kg", 649.00, 4, 1),
        (5, "Mathura Oven Fresh Paneer Patty", "BB-SNK-01-PTY", 35.00, 20, 1),
    ]
    for cid, cname, csku, cprice, cqty, ceggless in seed_cakes:
        chk = execute_query(conn, "SELECT COUNT(*) AS CNT FROM BB_CAKES WHERE cake_id = ?", (cid,))
        if not chk or chk[0]["CNT"] == 0:
            execute_dml(
                conn,
                "INSERT INTO BB_CAKES (cake_id, name, sku_id, price, stock_qty, is_eggless_available) VALUES (?, ?, ?, ?, ?, ?)",
                (cid, cname, csku, cprice, cqty, ceggless),
            )

    seed_inventory = [
        (101, "Khoaa Base (Eggless)", 12.00, "kg"),
        (102, "Belgian Dark Cocoa", 8.50, "kg"),
        (103, "Cream Cheese Frosting", 4.00, "kg"),
        (104, "Maraschino Cherries", 0.20, "kg"),
        (105, "Fresh Milk Solids (Mawa)", 10.00, "kg"),
        (106, "Whipped Dairy Cream", 6.00, "kg"),
        (107, "Spiced Paneer Masala Filling", 15.00, "kg"),
    ]
    for iid, iname, iqty, iunit in seed_inventory:
        chk = execute_query(conn, "SELECT COUNT(*) AS CNT FROM BB_INVENTORY WHERE ingredient_id = ?", (iid,))
        if not chk or chk[0]["CNT"] == 0:
            execute_dml(
                conn,
                "INSERT INTO BB_INVENTORY (ingredient_id, ingredient_name, stock_qty, unit) VALUES (?, ?, ?, ?)",
                (iid, iname, iqty, iunit),
            )

    seed_recipes = [
        (1, 101, "Khoaa Base (Eggless)", 0.50),
        (1, 103, "Cream Cheese Frosting", 0.40),
        (2, 101, "Khoaa Base (Eggless)", 0.30),
        (2, 102, "Belgian Dark Cocoa", 0.20),
        (2, 104, "Maraschino Cherries", 0.50),
        (3, 101, "Khoaa Base (Eggless)", 0.30),
        (3, 106, "Whipped Dairy Cream", 0.25),
        (4, 101, "Khoaa Base (Eggless)", 0.50),
        (4, 103, "Cream Cheese Frosting", 0.40),
        (5, 107, "Spiced Paneer Masala Filling", 0.10),
    ]
    chk_rec = execute_query(conn, "SELECT COUNT(*) AS CNT FROM BB_RECIPES", ())
    if not chk_rec or chk_rec[0]["CNT"] == 0:
        for r_cake, r_ing, r_name, r_qty in seed_recipes:
            execute_dml(
                conn,
                "INSERT INTO BB_RECIPES (cake_id, ingredient_id, ingredient_name, qty_needed) VALUES (?, ?, ?, ?)",
                (r_cake, r_ing, r_name, r_qty),
            )

    seed_components = [
        (101, 105, "Fresh Milk Solids (Mawa)", 0.6500),
        (103, 106, "Whipped Dairy Cream", 0.5000),
    ]
    for pid, comp_id, comp_name, ratio in seed_components:
        chk_comp = execute_query(
            conn,
            "SELECT COUNT(*) AS CNT FROM BB_INGREDIENT_COMPONENTS WHERE parent_ingredient_id = ? AND component_id = ?",
            (pid, comp_id),
        )
        if not chk_comp or chk_comp[0]["CNT"] == 0:
            execute_dml(
                conn,
                "INSERT INTO BB_INGREDIENT_COMPONENTS (parent_ingredient_id, component_id, component_name, qty_ratio) VALUES (?, ?, ?, ?)",
                (pid, comp_id, comp_name, ratio),
            )

    orders_file = os.path.join(_pkg_root, "data", "sample_orders.json")
    if os.path.isfile(orders_file):
        with open(orders_file, "r", encoding="utf-8") as f:
            seed_orders = json.load(f)
        for ord_data in seed_orders:
            oid = ord_data["order_id"]
            check_order = execute_query(conn, "SELECT COUNT(*) AS CNT FROM BB_ORDERS WHERE order_id = ?", (oid,))
            if not check_order or check_order[0]["CNT"] == 0:
                raw_phone = ord_data.get("customer_phone", "")
                digits = re.sub(r"\D", "", raw_phone)
                phone_last10 = digits[-10:] if len(digits) >= 10 else digits
                execute_dml(
                    conn,
                    """
                    INSERT INTO BB_ORDERS
                    (order_id, user_id, customer_name, customer_phone, phone_last10, order_type, order_status, total_amount, delivery_address, special_notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        oid,
                        ord_data.get("user_id", 1),
                        ord_data.get("customer_name", "Customer"),
                        raw_phone,
                        phone_last10,
                        ord_data.get("order_type", "DELIVERY"),
                        ord_data.get("order_status", "CONFIRMED"),
                        float(ord_data.get("total_amount", 0.0)),
                        ord_data.get("delivery_address", ""),
                        ord_data.get("special_notes", ""),
                    ),
                )
                for itm in ord_data.get("items", []):
                    execute_dml(
                        conn,
                        """
                        INSERT INTO BB_ORDER_ITEMS
                        (order_id, sku_id, item_name, quantity, unit_price, cake_base, cake_weight, custom_message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            oid,
                            itm.get("sku_id", ""),
                            itm.get("item_name", "Bakery Item"),
                            int(itm.get("quantity", 1)),
                            float(itm.get("unit_price", 0.0)),
                            itm.get("cake_base", "Khoaa (Eggless)"),
                            itm.get("cake_weight", "1.0kg"),
                            itm.get("custom_message", ""),
                        ),
                    )


def get_sample_bakery_documents():
    """
    Return curated domain knowledge chunks for Shri Ram Baker (Mathura).
    Dynamically loads product specifications from data/sample_catalog.json and operational policies
    with standardized `type` and dietary metadata for Db2 BSON predicate pushdown.
    """
    documents = []
    seen_ids = set()

    catalog_file = os.path.join(_pkg_root, "data", "sample_catalog.json")
    if os.path.isfile(catalog_file):
        with open(catalog_file, "r", encoding="utf-8") as f:
            cat_items = json.load(f)
        for item in cat_items:
            doc_id = f"CAKE_{item['sku_id']}"
            bases_str = ", ".join(item.get("available_bases", ["Khoaa (Eggless)"]))
            text = (
                f"{item['name']} (SKU: {item['sku_id']}). Category: {item.get('category', 'ACE')}. "
                f"Flavor: {item.get('flavor', '')}. Weight: {item.get('weight_kg', 1.0)}kg. "
                f"Price: Rs {item.get('price', 0.0)}. Visual: {item.get('description', '')}. "
                f"Available bases: {bases_str}. Sweetness: {item.get('sweetness_level', 'Balanced')}. "
                f"Preparation time: Standard 3-4 hours fresh baking wait time."
            )
            documents.append({
                "id": doc_id,
                "text": text,
                "metadata": {
                    "type": "cake" if item.get("category") != "BAKERY_RAW" else "snack",
                    "sku_id": item["sku_id"],
                    "name": item["name"],
                    "flavor": item.get("flavor", ""),
                    "price": float(item.get("price", 0.0)),
                    "weight_kg": float(item.get("weight_kg", 1.0)),
                    "category": item.get("category", "ACE"),
                    "is_eggless_available": bool(item.get("is_eggless_available", True)),
                    "eggless_flag": 1 if item.get("is_eggless_available", True) else 0,
                    "image_url": f"/catalog_images/CAKES_BRANDED/{item.get('category', 'ACE')}/{item.get('flavor', '').replace(' ', '%20')}/{item['sku_id']}.jpg",
                },
            })
            seen_ids.add(doc_id)

    supplementary = [
        {
            "id": "CAKE_BB-RED-05-1kg",
            "text": "Red Velvet Berry Fantasy (SKU: BB-RED-05-1kg). Category: ACE. Flavor: Red Velvet. Weight: 1.0kg. Price: Rs 649.0. Visual: Multi-layered velvet sponge infused with wild berry compote and whipped frosting. Available bases: Khoaa (Eggless), Pure Veg Eggless. Preparation time: Standard 3-4 hours fresh baking wait time.",
            "metadata": {
                "type": "cake",
                "sku_id": "BB-RED-05-1kg",
                "name": "Red Velvet Berry Fantasy",
                "flavor": "Red Velvet",
                "price": 649.0,
                "weight_kg": 1.0,
                "category": "ACE",
                "is_eggless_available": True,
                "eggless_flag": 1,
                "image_url": "/catalog_images/CAKES_BRANDED/ACE/Red%20Velvet/BAKEBOX_ACE_RedVelvet_05.jpg",
            },
        },
        {
            "id": "CAKE_BB-BLK-02-05kg",
            "text": "Black Forest Lattice Grid (SKU: BB-BLK-02-05kg). Category: ACE. Flavor: Black Forest. Weight: 0.5kg. Price: Rs 249.0. Visual: Chocolate sponge topped with glazed red cherries and hand-piped lattice chocolate grid. Available bases: Khoaa (Eggless), Eggless. Preparation time: Standard 3-4 hours fresh baking wait time.",
            "metadata": {
                "type": "cake",
                "sku_id": "BB-BLK-02-05kg",
                "name": "Black Forest Lattice Grid",
                "flavor": "Black Forest",
                "price": 249.0,
                "weight_kg": 0.5,
                "category": "ACE",
                "is_eggless_available": True,
                "eggless_flag": 1,
                "image_url": "/catalog_images/CAKES_BRANDED/ACE/Black%20Forest/BAKEBOX_ACE_BlackForest_02.jpg",
            },
        },
        {
            "id": "CAKE_BB-BLK-03-05kg",
            "text": "Black Forest Cherry Drizzle (SKU: BB-BLK-03-05kg). Category: ACE. Flavor: Black Forest. Weight: 0.5kg. Price: Rs 249.0. Visual: Dark cocoa sponge with cherry coulis drizzle and snow-white cream rosettes. Available bases: Khoaa (Eggless), Eggless. Preparation time: Standard 3-4 hours fresh baking wait time.",
            "metadata": {
                "type": "cake",
                "sku_id": "BB-BLK-03-05kg",
                "name": "Black Forest Cherry Drizzle",
                "flavor": "Black Forest",
                "price": 249.0,
                "weight_kg": 0.5,
                "category": "ACE",
                "is_eggless_available": True,
                "eggless_flag": 1,
                "image_url": "/catalog_images/CAKES_BRANDED/ACE/Black%20Forest/BAKEBOX_ACE_BlackForest_03.jpg",
            },
        },
        {
            "id": "POLICY_WAIT_TIME",
            "text": "Store Working Agreement - Fresh Baking Wait Time Policy: All standard fresh cakes at Shri Ram Baker are handcrafted strictly on demand to preserve 100% freshness. Standard preparation and soaking time is 3 to 4 hours after order placement. Ready-to-deliver showcase items dispatch within 1 to 2 hours. Hot patties dispatch within 45 to 60 minutes.",
            "metadata": {"type": "policy", "title": "Baking Wait Time Policy"},
        },
        {
            "id": "POLICY_PATTY_REHEATING",
            "text": "Bakery Snack Advisory - Patty Reheating Instruction: Shri Ram Baker fresh oven patties (Aloo, Paneer, Tandoori, Cheese Mayo) must ALWAYS be reheated on a dry tawa (dry skillet) on medium heat for 2 to 3 minutes to restore the crispy puff pastry flakes. NEVER microwave patties as it makes the pastry rubbery and soggy.",
            "metadata": {"type": "advisory", "title": "Patty Reheating Guidelines"},
        },
        {
            "id": "POLICY_LOCATIONS",
            "text": "Shri Ram Baker Branch Locations: Branch 1 (Main Kitchen): Bhagel Chaupal, Khatoti Kua, Mathura. Branch 2: Holigate & Gosna, Mathura, Uttar Pradesh. Specializes in fresh live cakes with authentic Khoaa eggless and egg-based options.",
            "metadata": {"type": "store_info", "title": "Store Locations and Branches"},
        },
        {
            "id": "POLICY_HOURS",
            "text": "Shri Ram Baker Store Hours & Operation: Open daily from 8:00 AM to 11:00 PM, 7 days a week. Fresh live baking kitchen dispatches orders between 9:00 AM and 10:30 PM. Customer support available 24/7 through CHOCO AI.",
            "metadata": {"type": "store_info", "title": "Store Opening Hours"},
        },
        {
            "id": "POLICY_HISTORY",
            "text": "Shri Ram Baker Bakery History & Heritage: Established over 20 years ago in Mathura, Shri Ram Baker's is a trusted family-owned bakery known for pioneering authentic Khoaa Eggless bases, premium wedding cakes, and pure ingredients.",
            "metadata": {"type": "store_info", "title": "Bakery History and Heritage"},
        },
        {
            "id": "POLICY_SNACKS",
            "text": "Shri Ram Baker Savory Snacks & Hot Patties: We bake fresh oven patties including Aloo Patty (Rs 25), Paneer Patty (Rs 35), Tandoori Patty (Rs 40), and Cheese Mayo Patty (Rs 45), along with cookies, rusks, and celebration accessories.",
            "metadata": {"type": "store_info", "title": "Patties and Savory Snacks Menu"},
        },
        {
            "id": "POLICY_HAPPINESS_GUARANTEE",
            "text": "Shri Ram Baker Celebration Happiness Guarantee: 100% on-time dispatch guarantee for pre-scheduled cakes. If any cake design or flavor does not meet our verified quality benchmark, immediate replacement or kitchen store credit is issued within 30 minutes. Customer delight in Mathura is our family heritage.",
            "metadata": {"type": "policy", "title": "Celebration Happiness Guarantee"},
        },
    ]

    for doc in supplementary:
        if doc["id"] not in seen_ids:
            documents.append(doc)
            seen_ids.add(doc["id"])

    return documents


def run_ingestion() -> None:
    """Execute full relational + vector ingestion pipeline into IBM Db2."""
    print("==================================================================")
    print("BAKEBOX CHOCO AI — IBM Db2 DATA INGESTION PIPELINE")
    print("==================================================================")

    from src.retriever import get_shared_embedding_fn
    from src.vector_store import BakeboxDb2VectorStore

    conn = get_dbi_connection()
    vs = None
    try:
        init_relational_tables(conn)

        model_name = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-en-v1.5")
        print(f"\nStep 2: Loading embedding engine '{model_name}'...")
        embed_func = get_shared_embedding_fn(model_name)

        print("\nStep 3: Generating 384-dimensional dense vectors for knowledge corpus...")
        docs = get_sample_bakery_documents()
        text_nodes = []
        for d in docs:
            vec = embed_func(d["text"])
            if TextNode is not None:
                node = TextNode(
                    text=d["text"],
                    id_=d["id"],
                    embedding=vec,
                    relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id=d["id"])},
                    metadata=d.get("metadata", {}),
                )
            else:
                from src.retriever import TextNode as FallbackNode
                node = FallbackNode(text=d["text"], id_=d["id"], metadata=d.get("metadata", {}), embedding=vec)
            text_nodes.append(node)
        print(f"  -> Generated embeddings for {len(text_nodes)} knowledge nodes.")

        print("\nStep 4: Idempotently syncing vectors into 'BB_CHUNKS_VECTOR'...")
        vs = BakeboxDb2VectorStore(
            table_name="BB_CHUNKS_VECTOR",
            embed_dim=384,
            distance_strategy=DistanceStrategy.COSINE,
        )
        for d in docs:
            try:
                vs.delete_document(d["id"])
            except Exception:
                pass
        vs.add_nodes(text_nodes)
        print("  -> Ingestion complete!")
    finally:
        if vs is not None:
            vs.close()
        conn.close()


if __name__ == "__main__":
    run_ingestion()
