"""
Data Ingestion Pipeline for BAKEBOX Choco AI.
Sets up:
1. IBM Db2 Relational Tables: BB_ORDERS & BB_ORDER_ITEMS
2. IBM Db2 Vector Table via DB2LlamaVS (BB_CHUNKS_VECTOR with native vector(384, FLOAT32))
3. Pre-computes and ingests bakery cakes, store policies, and heating rules.
"""
import os
import sys
import json
try:
    from fastembed import TextEmbedding
    HAS_FASTEMBED = True
except ImportError:
    HAS_FASTEMBED = False
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        pass

from llama_index.core.schema import TextNode, NodeRelationship, RelatedNodeInfo
from llama_index.vector_stores.db2 import DistanceStrategy

from src.db import get_dbi_connection, execute_dml, execute_query
from src.vector_store import BakeboxDb2VectorStore

def init_relational_tables(conn):
    """Create relational order tables in IBM Db2."""
    print("Step 1: Setting up IBM Db2 Relational Tables (BB_ORDERS & BB_ORDER_ITEMS)...")
    
    # BB_ORDERS Table
    orders_sql = """
    CREATE TABLE BB_ORDERS (
        order_id INT NOT NULL PRIMARY KEY,
        user_id INT,
        customer_name VARCHAR(128) NOT NULL,
        customer_phone VARCHAR(32) NOT NULL,
        order_type VARCHAR(32) DEFAULT 'DELIVERY',
        order_status VARCHAR(32) DEFAULT 'BAKING',
        total_amount DECIMAL(10, 2) NOT NULL,
        delivery_address VARCHAR(512),
        special_notes VARCHAR(512),
        created_at TIMESTAMP DEFAULT CURRENT TIMESTAMP
    )
    """
    try:
        execute_dml(conn, orders_sql)
        print("  -> Table BB_ORDERS created successfully.")
    except Exception as e:
        print("  -> Table BB_ORDERS already exists or was retained.")

    # BB_ORDER_ITEMS Table
    items_sql = """
    CREATE TABLE BB_ORDER_ITEMS (
        item_id INT NOT NULL GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1) PRIMARY KEY,
        order_id INT NOT NULL,
        sku_id VARCHAR(64) NOT NULL,
        item_name VARCHAR(256) NOT NULL,
        quantity INT NOT NULL,
        unit_price DECIMAL(10, 2) NOT NULL,
        cake_base VARCHAR(64) DEFAULT 'Khoaa (Eggless)',
        cake_weight VARCHAR(32) DEFAULT '1kg',
        custom_message VARCHAR(256)
    )
    """
    try:
        execute_dml(conn, items_sql)
        print("  -> Table BB_ORDER_ITEMS created successfully.")
    except Exception as e:
        print("  -> Table BB_ORDER_ITEMS already exists or was retained.")

    # Insert sample ground-truth orders for testing
    check_order = execute_query(conn, "SELECT COUNT(*) AS CNT FROM BB_ORDERS WHERE order_id = 1002")
    if not check_order or check_order[0]["CNT"] == 0:
        execute_dml(
            conn,
            """
            INSERT INTO BB_ORDERS 
            (order_id, user_id, customer_name, customer_phone, order_type, order_status, total_amount, delivery_address, special_notes)
            VALUES (1002, 3, 'Rahul Sharma', '+91 9876543210', 'DELIVERY', 'BAKING', 649.00, 'Krishna Nagar, Mathura', '1st Anniversary Celebration')
            """
        )
        execute_dml(
            conn,
            """
            INSERT INTO BB_ORDER_ITEMS 
            (order_id, sku_id, item_name, quantity, unit_price, cake_base, cake_weight, custom_message)
            VALUES (1002, 'BB-RED-02-1kg', 'Red Velvet Heart Special', 1, 649.00, 'Khoaa (Eggless)', '1.0kg', 'Happy 1st Anniversary')
            """
        )
        print("  -> Seeded demo active order #1002 for 'Rahul Sharma' (Status: BAKING at Khatoti Kua kitchen).")


def get_sample_bakery_documents():
    """Returns essential domain knowledge chunks for Shri Ram Baker (Mathura)."""
    return [
        {
            "id": "CAKE_BB-RED-01-1kg",
            "text": "Red Velvet Crimson Crumb Crown (SKU: BB-RED-01-1kg). Category: ACE. Flavor: Red Velvet. Weight: 1.0kg. Price: Rs 649.0. Visual: Deep crimson cocoa sponge, rich vanilla cream cheese swirl, velvet crumb dusting. Available bases: Khoaa (Eggless), Pure Veg Eggless, Chocolate Eggless, Egg. Preparation time: Standard 3-4 hours fresh baking wait time.",
            "metadata": {
                "sku_id": "BB-RED-01-1kg",
                "name": "Red Velvet Crimson Crumb Crown",
                "flavor": "Red Velvet",
                "price": 649.0,
                "weight_kg": 1.0,
                "category": "ACE",
                "image_url": "/catalog_images/CAKES_BRANDED/ACE/Red%20Velvet/BAKEBOX_ACE_RedVelvet_01.jpg"
            }
        },
        {
            "id": "CAKE_BB-RED-02-1kg",
            "text": "Red Velvet Heart Love Affair (SKU: BB-RED-02-1kg). Category: ACE. Flavor: Red Velvet. Weight: 1.0kg. Price: Rs 649.0. Visual: Romantic heart-shaped crimson crumb velvet with golden edible shimmer and chocolate curls. Available bases: Khoaa (Eggless), Pure Veg Eggless, Chocolate Eggless. Preparation time: Standard 3-4 hours fresh baking wait time.",
            "metadata": {
                "sku_id": "BB-RED-02-1kg",
                "name": "Red Velvet Heart Love Affair",
                "flavor": "Red Velvet",
                "price": 649.0,
                "weight_kg": 1.0,
                "category": "ACE",
                "image_url": "/catalog_images/CAKES_BRANDED/ACE/Red%20Velvet/BAKEBOX_ACE_RedVelvet_02.jpg"
            }
        },
        {
            "id": "CAKE_BB-RED-05-1kg",
            "text": "Red Velvet Berry Fantasy (SKU: BB-RED-05-1kg). Category: ACE. Flavor: Red Velvet. Weight: 1.0kg. Price: Rs 649.0. Visual: Multi-layered velvet sponge infused with wild berry compote and whipped frosting. Available bases: Khoaa (Eggless), Pure Veg Eggless. Preparation time: Standard 3-4 hours fresh baking wait time.",
            "metadata": {
                "sku_id": "BB-RED-05-1kg",
                "name": "Red Velvet Berry Fantasy",
                "flavor": "Red Velvet",
                "price": 649.0,
                "weight_kg": 1.0,
                "category": "ACE",
                "image_url": "/catalog_images/CAKES_BRANDED/ACE/Red%20Velvet/BAKEBOX_ACE_RedVelvet_05.jpg"
            }
        },
        {
            "id": "CAKE_BB-BLK-01-05kg",
            "text": "Black Forest Classic Cherry Gateau (SKU: BB-BLK-01-05kg). Category: ACE. Flavor: Black Forest. Weight: 0.5kg. Price: Rs 249.0. Visual: Rich chocolate layers soaked in sweet cherry syrup with whipped vanilla cream and dark chocolate curls. Available bases: Khoaa (Eggless), Eggless, Egg. Preparation time: Standard 3-4 hours fresh baking wait time.",
            "metadata": {
                "sku_id": "BB-BLK-01-05kg",
                "name": "Black Forest Classic Cherry Gateau",
                "flavor": "Black Forest",
                "price": 249.0,
                "weight_kg": 0.5,
                "category": "ACE",
                "image_url": "/catalog_images/CAKES_BRANDED/ACE/Black%20Forest/BAKEBOX_ACE_BlackForest_01.jpg"
            }
        },
        {
            "id": "CAKE_BB-BLK-02-05kg",
            "text": "Black Forest Lattice Grid (SKU: BB-BLK-02-05kg). Category: ACE. Flavor: Black Forest. Weight: 0.5kg. Price: Rs 249.0. Visual: Chocolate sponge topped with glazed red cherries and hand-piped lattice chocolate grid. Available bases: Khoaa (Eggless), Eggless. Preparation time: Standard 3-4 hours fresh baking wait time.",
            "metadata": {
                "sku_id": "BB-BLK-02-05kg",
                "name": "Black Forest Lattice Grid",
                "flavor": "Black Forest",
                "price": 249.0,
                "weight_kg": 0.5,
                "category": "ACE",
                "image_url": "/catalog_images/CAKES_BRANDED/ACE/Black%20Forest/BAKEBOX_ACE_BlackForest_02.jpg"
            }
        },
        {
            "id": "CAKE_BB-BLK-03-05kg",
            "text": "Black Forest Cherry Drizzle (SKU: BB-BLK-03-05kg). Category: ACE. Flavor: Black Forest. Weight: 0.5kg. Price: Rs 249.0. Visual: Dark cocoa sponge with cherry coulis drizzle and snow-white cream rosettes. Available bases: Khoaa (Eggless), Eggless. Preparation time: Standard 3-4 hours fresh baking wait time.",
            "metadata": {
                "sku_id": "BB-BLK-03-05kg",
                "name": "Black Forest Cherry Drizzle",
                "flavor": "Black Forest",
                "price": 249.0,
                "weight_kg": 0.5,
                "category": "ACE",
                "image_url": "/catalog_images/CAKES_BRANDED/ACE/Black%20Forest/BAKEBOX_ACE_BlackForest_03.jpg"
            }
        },
        {
            "id": "CAKE_BB-PIN-01-05kg",
            "text": "Pineapple Classic Spiral Mirror (SKU: BB-PIN-01-05kg). Category: ACE. Flavor: Pineapple. Weight: 0.5kg. Price: Rs 249.0. Visual: Golden yellow glazed pineapple sponge with real pineapple fruit chunks and maraschino cherries. Available bases: Khoaa (Eggless), Pure Veg Eggless. Preparation time: Standard 3-4 hours fresh baking wait time.",
            "metadata": {
                "sku_id": "BB-PIN-01-05kg",
                "name": "Pineapple Classic Spiral Mirror",
                "flavor": "Pineapple",
                "price": 249.0,
                "weight_kg": 0.5,
                "category": "ACE",
                "image_url": "/catalog_images/CAKES_BRANDED/ACE/Pineapple/BAKEBOX_ACE_Pineapple_01.jpg"
            }
        },
        {
            "id": "POLICY_WAIT_TIME",
            "text": "Store Working Agreement - Fresh Baking Wait Time Policy: All standard fresh cakes at Shri Ram Baker are handcrafted strictly on demand to preserve 100% freshness. Standard preparation and soaking time is 3 to 4 hours after order placement. Ready-to-deliver showcase items dispatch within 1 to 2 hours. Hot patties dispatch within 45 to 60 minutes.",
            "metadata": {"type": "policy", "title": "Baking Wait Time Policy"}
        },
        {
            "id": "POLICY_PATTY_REHEATING",
            "text": "Bakery Snack Advisory - Patty Reheating Instruction: Shri Ram Baker fresh oven patties (Aloo, Paneer, Tandoori, Cheese Mayo) must ALWAYS be reheated on a dry tawa (dry skillet) on medium heat for 2 to 3 minutes to restore the crispy puff pastry flakes. NEVER microwave patties as it makes the pastry rubbery and soggy.",
            "metadata": {"type": "advisory", "title": "Patty Reheating Guidelines"}
        },
        {
            "id": "POLICY_LOCATIONS",
            "text": "Shri Ram Baker Branch Locations: Branch 1 (Main Kitchen): Bhagel Chaupal, Khatoti Kua, Mathura. Branch 2: Gausna, Mathura, Uttar Pradesh. Specializes in 100% pure vegetarian live fresh cakes with Khoaa eggless base.",
            "metadata": {"type": "store_info", "title": "Store Locations and Branches"}
        }
    ]


def run_ingestion():
    """Main execution of the ingestion pipeline."""
    print("==================================================================")
    print("BAKEBOX CHOCO AI — IBM Db2 DATA INGESTION PIPELINE")
    print("==================================================================")
    
    conn = get_dbi_connection()
    try:
        # Step 1: Initialize Relational Tables
        init_relational_tables(conn)

        # Step 2: Initialize Embedding Model
        model_name = "BAAI/bge-small-en-v1.5"
        print(f"\nStep 2: Loading HuggingFace Embedding Model '{model_name}'...")
        if HAS_FASTEMBED:
            fast_model = TextEmbedding(model_name=model_name)
            embed_func = lambda t: list(fast_model.embed([t]))[0].tolist()
        else:
            from sentence_transformers import SentenceTransformer
            st_model = SentenceTransformer(model_name)
            embed_func = lambda t: st_model.encode(t).tolist()

        # Step 3: Prepare Text Nodes with Dense Vectors
        print("\nStep 3: Generating 384-dimensional dense vectors for bakery knowledge chunks...")
        docs = get_sample_bakery_documents()
        text_nodes = []
        for d in docs:
            vec = embed_func(d["text"])
            node = TextNode(
                text=d["text"],
                id_=d["id"],
                embedding=vec,
                relationships={
                    NodeRelationship.SOURCE: RelatedNodeInfo(node_id=d["id"])
                },
                metadata=d.get("metadata", {})
            )
            text_nodes.append(node)
        print(f"  -> Generated embeddings for {len(text_nodes)} knowledge nodes.")

        # Step 4: Ingest into IBM Db2 via DB2LlamaVS
        print("\nStep 4: Ingesting into IBM Db2 native vector table 'BB_CHUNKS_VECTOR' via DB2LlamaVS...")
        try:
            execute_dml(conn, "DROP TABLE BB_CHUNKS_VECTOR")
        except Exception:
            pass
        vs = BakeboxDb2VectorStore(
            table_name="BB_CHUNKS_VECTOR",
            embed_dim=384,
            distance_strategy=DistanceStrategy.COSINE
        )
        vs.add_nodes(text_nodes)
        print("  -> Ingestion complete! Chunks & vectors safely stored in IBM Db2.")

        print("\n==================================================================")
        print("DATA INGESTION SUCCESSFULLY COMPLETED!")
        print("==================================================================")
    finally:
        conn.close()

if __name__ == "__main__":
    run_ingestion()
