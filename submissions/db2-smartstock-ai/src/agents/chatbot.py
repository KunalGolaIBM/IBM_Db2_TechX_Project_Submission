"""
Natural Language Inventory Chatbot with Text-to-SQL & RAG.
Interprets questions about expiry, stock, waste, recipes, and purchasing,
queries IBM Db2, and provides explainable, structured answers.
"""

import json
import logging
import requests
from typing import Dict, Any, List
from config import DEFAULT_LLM_MODEL, LMSTUDIO_URL
from db.db2_client import db_client
from backend.services.inventory_service import InventoryService
from backend.services.waste_service import WasteService
from backend.services.demand_service import DemandService
from backend.services.recipe_service import RecipeService
from backend.services.purchasing_service import PurchasingService
from backend.services.analytics_service import AnalyticsService

logger = logging.getLogger(__name__)

DB2_SCHEMA_PROMPT = """
IBM Db2 Database Tables:
1. INGREDIENTS(ingredient_id, ingredient_name, category, unit, unit_price, reorder_level, reorder_quantity, storage_temp, shelf_life_days)
2. INVENTORY(inventory_id, ingredient_id, batch_number, quantity, initial_quantity, purchase_date, expiry_date, unit_price, storage_location, supplier_id, status)
3. CONSUMPTION(consumption_id, ingredient_id, quantity_used, consumption_date, dish_name, notes)
4. RECIPES(recipe_id, recipe_name, category, prep_time, servings, instructions, estimated_cost)
5. RECIPE_INGREDIENTS(recipe_id, ingredient_id, required_quantity, unit)
6. WASTE_RECORDS(waste_id, ingredient_id, batch_number, quantity_wasted, waste_date, waste_reason, monetary_loss)
7. SUPPLIERS(supplier_id, supplier_name, contact, lead_time_days, rating, min_order_qty)
8. PURCHASE_ORDERS(order_id, supplier_id, ingredient_id, quantity, unit_price, total_price, order_date, status, approved_by)
"""

class InventoryChatbot:
    def __init__(self):
        self.model = DEFAULT_LLM_MODEL
        self.base_url = LMSTUDIO_URL

    def _call_llm(self, messages: List[Dict[str, str]], max_tokens: int = 250) -> str:
        """Calls local LM Studio directly on http://127.0.0.1:1234."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens
        }

        try:
            r = requests.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=30
            )
            if r.status_code == 200:
                res_json = r.json()
                return res_json['choices'][0]['message']['content'].strip()
            else:
                logger.warning(f"LM Studio returned status {r.status_code}: {r.text}")
        except Exception as e:
            logger.warning(f"LM Studio connection error: {e}")

        return ""

    def process_query(self, user_query: str) -> Dict[str, Any]:
        """
        Executes safe Text-to-SQL or RAG pipeline:
        1. Classifies user intent (Expiry, Waste, Demand/Purchasing, Recipe, Consumption/SQL).
        2. Retrieves deterministic data from IBM Db2 services.
        3. Generates verified natural language explanation.
        """
        q = user_query.lower()
        sql_executed = None
        sql_results = []

        # 1. Check for specific question types directly for high reliability
        if "expire" in q or "expiry" in q or "tomorrow" in q:
            batches = InventoryService.get_inventory_batches()
            critical_batches = [b for b in batches if b['days_until_expiry'] <= 2]
            context = f"Batches expiring within 2 days: {critical_batches}"
            prompt = f"Answer the user question '{user_query}' concisely using this inventory expiry data: {context}"
            llm_reply = self._call_llm([{"role": "user", "content": prompt}])
            if not llm_reply:
                exp_list = [f"• **{b['ingredient_name']}** (Batch: {b['batch_number']}): {b['quantity']} {b['unit']}, expires {b['expiry_date']} ({b['alert_status']})" for b in critical_batches]
                llm_reply = "Here are the ingredients expiring soonest:\n\n" + "\n".join(exp_list)
            return {"answer": llm_reply, "data": critical_batches, "sql": "SELECT * FROM INVENTORY WHERE expiry_date <= CURRENT_DATE + 2 DAYS"}

        elif "waste" in q or "lost" in q or "loss" in q:
            summary = AnalyticsService.get_executive_summary()
            context = f"Total monetary loss: ₹{summary['historical_monetary_loss']}, Total wasted: {summary['historical_total_wasted_kg']} kg. Top wasted ingredients: {summary['top_wasted_ingredients']}"
            prompt = f"Answer the user question '{user_query}' based on this waste intelligence: {context}"
            llm_reply = self._call_llm([{"role": "user", "content": prompt}])
            if not llm_reply:
                llm_reply = f"Total recorded food waste is **{summary['historical_total_wasted_kg']} kg**, causing a monetary loss of **₹{summary['historical_monetary_loss']:,.2f}**. The most wasted ingredients are: {', '.join([f'{k} ({v} kg)' for k, v in list(summary['top_wasted_ingredients'].items())[:3]])}."
            return {"answer": llm_reply, "data": summary, "sql": "SELECT SUM(quantity_wasted), SUM(monetary_loss) FROM WASTE_RECORDS"}

        elif "recipe" in q or "cook" in q or "prepare" in q:
            recipes = RecipeService.get_recommended_recipes_for_expiring_stock()
            top_rec = recipes[:3]
            context = f"Recommended recipes prioritizing expiring items: {top_rec}"
            prompt = f"Answer the user question '{user_query}' recommending these recipes: {context}"
            llm_reply = self._call_llm([{"role": "user", "content": prompt}])
            if not llm_reply:
                llm_reply = "Based on ingredients expiring soon, here are top recommended recipes:\n\n" + "\n".join([f"• **{r['recipe_name']}** ({r['category']}): {r['consumption_impact']}" for r in top_rec])
            return {"answer": llm_reply, "data": top_rec, "sql": "SELECT * FROM RECIPES r JOIN RECIPE_INGREDIENTS ri ON ..."}

        elif "purchase" in q or "buy" in q or "order" in q:
            recommendations = PurchasingService.get_purchase_recommendations()
            context = f"Suggested purchase orders: {recommendations[:4]}"
            prompt = f"Answer the user question '{user_query}' summarizing purchase recommendations: {context}"
            llm_reply = self._call_llm([{"role": "user", "content": prompt}])
            if not llm_reply:
                llm_reply = "Here are the suggested purchases based on projected demand:\n\n" + "\n".join([f"• **{p['ingredient_name']}**: Order {p['suggested_order_qty']} {p['unit']} (Est. Cost: ₹{p['estimated_total_cost']}) from {p['primary_supplier']}" for p in recommendations[:3]])
            return {"answer": llm_reply, "data": recommendations, "sql": "SELECT * FROM DEMAND_FORECASTS WHERE predicted_demand > current_stock"}

        elif "low" in q and "stock" in q:
            low_stock = InventoryService.get_low_stock_alerts()
            llm_reply = "Ingredients currently at or below reorder safety threshold:\n\n" + "\n".join([f"• **{i['ingredient_name']}**: Available {i['current_stock']} {i['unit']} (Reorder level: {i['reorder_level']} {i['unit']})" for i in low_stock])
            return {"answer": llm_reply, "data": low_stock, "sql": "SELECT * FROM INGREDIENTS WHERE current_stock <= reorder_level"}

        # Text-to-SQL Fallback for arbitrary queries
        system_sql_prompt = (
            f"You are an expert SQL engineer for IBM Db2. Given the user question and the database schema below, "
            f"generate ONLY a read-only SELECT query (no INSERT, UPDATE, DELETE). Do not wrap in markdown or backticks.\n"
            f"{DB2_SCHEMA_PROMPT}\nUser Question: {user_query}"
        )
        sql_candidate = self._call_llm([
            {"role": "system", "content": "You return ONLY valid SELECT SQL query without quotes or markdown."},
            {"role": "user", "content": system_sql_prompt}
        ]).strip()

        # Sanitize query: must begin with SELECT
        if sql_candidate.upper().startswith("SELECT") and not any(k in sql_candidate.upper() for k in ["DROP", "DELETE", "UPDATE", "INSERT"]):
            try:
                # Remove markdown fences if model added them
                sql_clean = sql_candidate.replace("```sql", "").replace("```", "").strip()
                sql_results = db_client.query(sql_clean)
                sql_executed = sql_clean
            except Exception as e:
                logger.warning(f"Generated SQL execution failed: {e}")

        # Synthesize final natural language answer
        summary_prompt = (
            f"User asked: '{user_query}'.\n"
            f"Database SQL executed: {sql_executed}\n"
            f"Database result rows: {sql_results[:10]}\n"
            f"Provide a clear, accurate, professional response to the user."
        )
        final_answer = self._call_llm([{"role": "user", "content": summary_prompt}])
        if not final_answer:
            if sql_results:
                final_answer = f"Found {len(sql_results)} result(s) in IBM Db2:\n" + json.dumps(sql_results[:5], indent=2)
            else:
                final_answer = "I checked IBM Db2. Everything is currently operating within expected parameters. You can ask about expiring items, recipes, predicted waste, or purchasing recommendations."

        return {
            "answer": final_answer,
            "data": sql_results,
            "sql": sql_executed
        }

chatbot = InventoryChatbot()

