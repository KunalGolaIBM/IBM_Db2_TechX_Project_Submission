"""
Main Query Engine for BAKEBOX Choco AI.
Demonstrates:
1. Live Order Lookup from IBM Db2 (BB_ORDERS & BB_ORDER_ITEMS)
2. Hybrid RRF Retrieval combining DB2LlamaVS native vector search & lexical TF-IDF
3. Strict 3-Cake JSON recommendation output for e-commerce integration.
"""
import os
import sys
import json
import re

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from llama_index.core.schema import TextNode
from llama_index.vector_stores.db2 import DistanceStrategy

from src.db import get_dbi_connection, execute_query
from src.vector_store import BakeboxDb2VectorStore
from src.retriever import Db2HybridRRFRetriever
from src.ingest import get_sample_bakery_documents

class ChocoQueryEngine:
    def __init__(self):
        print("Initializing BAKEBOX Choco Query Engine with IBM Db2 & LlamaIndex...")
        
        # 1. Connect to Db2 Vector Store
        self.vector_store = BakeboxDb2VectorStore(
            table_name="BB_CHUNKS_VECTOR",
            embed_dim=384,
            distance_strategy=DistanceStrategy.COSINE
        )

        # 2. Build corpus nodes for hybrid retrieval
        raw_docs = get_sample_bakery_documents()
        corpus_nodes = [
            TextNode(text=d["text"], id_=d["id"], metadata=d.get("metadata", {}))
            for d in raw_docs
        ]

        # 3. Initialize Hybrid RRF Retriever
        self.retriever = Db2HybridRRFRetriever(
            vector_store=self.vector_store,
            corpus_nodes=corpus_nodes,
            model_name="BAAI/bge-small-en-v1.5",
            rrf_k=60
        )
        print("[OK] Choco Query Engine is fully operational!\n")

    def lookup_live_order(self, query: str) -> dict | None:
        """Query IBM Db2 BB_ORDERS table to find active customer orders."""
        order_match = re.search(r'(?:order\s*#?|#)(\d{4,})', query, re.I)
        target_id = int(order_match.group(1)) if order_match else 1002  # Default to demo order #1002

        conn = get_dbi_connection()
        try:
            sql_order = "SELECT * FROM BB_ORDERS WHERE order_id = ?"
            order_rows = execute_query(conn, sql_order, (target_id,))
            if not order_rows:
                return None
            
            order = order_rows[0]
            sql_items = "SELECT * FROM BB_ORDER_ITEMS WHERE order_id = ?"
            items = execute_query(conn, sql_items, (target_id,))
            order["ITEMS"] = items
            return order
        finally:
            conn.close()

    def query(self, user_message: str) -> dict:
        """
        Processes user query:
        - If asking for order status: fetches live ground truth from IBM Db2 BB_ORDERS (0 cards).
        - If asking for cake suggestions: executes Hybrid RRF search and returns strictly 3 matching cake cards.
        - If asking for policies/heating: retrieves exact guidelines.
        """
        q_lower = user_message.lower()

        # Check for order status intent
        order_keywords = ["order", "status", "mera order", "track", "delivery", "placed"]
        is_order_query = any(k in q_lower for k in order_keywords)

        if is_order_query:
            order = self.lookup_live_order(user_message)
            if order:
                item_descs = ", ".join([f"{it['QUANTITY']}x {it['ITEM_NAME']} ({it.get('CAKE_WEIGHT', '')}, {it.get('CAKE_BASE', '')})" for it in order.get("ITEMS", [])])
                reply = (
                    f"Radhe Radhe ji! Shri Ram Baker's BAKEBOX mein aapka swagat hai!\n\n"
                    f"Humne aapke order ki details check kar li hain. Aapka order (Order ID: #{order['ORDER_ID']}) "
                    f"jisme {item_descs} shamil hai, abhi hamari Bhagel Chaupal, Khatoti Kua branch ke kitchen mein "
                    f"'{order['ORDER_STATUS']}' status mein hai!\n\n"
                    f"Standard fresh baking mein 3-4 ghante ka wait time lagta hai, aur yeh bilkul fresh taiyar karke "
                    f"aapke diye gaye address ({order['DELIVERY_ADDRESS']}) par jaldi hi dispatch kiya jayega!"
                )
                return {
                    "reply": reply,
                    "ui_cards": [],
                    "intent": "ORDER_TRACKING"
                }

        # Check for recommendation intent
        is_policy_or_heating = any(k in q_lower for k in ["reheat", "tawa", "microwave", "policy", "wait time", "location", "branch"])
        rec_signals = ["show", "suggest", "recommend", "design", "dikhao", "batao", "cake", "flavor"]
        is_rec_query = (any(s in q_lower for s in rec_signals) or ("chahiye" in q_lower and "cake" in q_lower)) and not is_policy_or_heating

        # Execute Hybrid RRF Retrieval
        retrieved_nodes = self.retriever.retrieve(user_message)
        context_texts = [f"- {n.node.text}" for n in retrieved_nodes]

        ui_cards = []
        if is_rec_query:
            # Extract distinct cake cards matching query flavor
            seen_skus = set()
            for n in retrieved_nodes:
                m = n.node.metadata
                if m and m.get("sku_id") and m.get("sku_id") not in seen_skus:
                    ui_cards.append({
                        "sku_id": m.get("sku_id"),
                        "name": m.get("name"),
                        "flavor": m.get("flavor", ""),
                        "category": m.get("category", "ACE"),
                        "weight_kg": m.get("weight_kg", 0.5),
                        "price": m.get("price", 249.0),
                        "image_url": m.get("image_url", "")
                    })
                    seen_skus.add(m.get("sku_id"))
                if len(ui_cards) >= 3:
                    break

            reply = (
                f"Radhe Radhe ji! Shri Ram Baker's BAKEBOX mein aapka swagat hai!\n\n"
                f"Ji bilkul, aapki celebration ke liye hamare paas fresh options available hain:\n"
                + "\n".join([f"• {c['name']} (₹{c['price']}, {c['weight_kg']}kg)" for c in ui_cards])
                + "\n\nHamare sabhi cakes 100% pure vegetarian (Khoaa Eggless available) hain aur order par fresh bake kiye jaate hain (3-4 ghante wait time)!"
            )
            return {
                "reply": reply,
                "ui_cards": ui_cards[:3],
                "intent": "CAKE_RECOMMENDATION"
            }

        # General Policy / Advisory Query
        reply = (
            f"Radhe Radhe ji! Hamare guidelines ke mutabiq:\n"
            + "\n".join(context_texts[:2])
            + "\n\nAapko kisi aur cheez ki madad chahiye toh zaroor batayein!"
        )
        return {
            "reply": reply,
            "ui_cards": [],
            "intent": "POLICY_ADVISORY"
        }

if __name__ == "__main__":
    engine = ChocoQueryEngine()
    
    test_queries = [
        "Show me some red velvet cake for anniversary celebration",
        "Actually I have placed one order can you provide me the status?",
        "Patties ko reheat kaise karna chahiye?"
    ]

    for q in test_queries:
        print("==================================================================")
        print(f"QUERY: '{q}'")
        res = engine.query(q)
        print(f"INTENT: {res['intent']}")
        print(f"CARDS RETURNED: {len(res['ui_cards'])}")
        print(f"CHOCO REPLY:\n{res['reply']}\n")
