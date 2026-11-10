"""LangGraph agent workflow for StockSage Inventory Intelligence.

Architecture:
    User Query -> Intent Classification -> Verified Tool Execution -> Result Synthesis (Gemini)

Strictly separates reasoning from arithmetic:
- LangGraph routes user queries.
- Python & SQL compute verified numbers deterministically.
- Gemini LLM explains insights in natural language without hallucinating figures.
"""

from typing import Any, Dict, List, Optional, TypedDict
import logging
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from src.config import GEMINI_API_KEY
from src.db_connection import db_manager
from src.inventory_tools import (
    get_expiry_risk_analysis,
    get_fast_and_slow_moving_products,
    get_inventory_health_summary,
    get_low_stock_alerts,
    get_reorder_recommendations,
    get_stockout_risk_forecast,
)

logger = logging.getLogger("StockSage.Agent")

# State definition for the LangGraph workflow
class AgentState(TypedDict):
    question: str
    intent: str
    verified_data: Dict[str, Any]
    response: str
    error: Optional[str]


def get_llm():
    """Initialize Gemini LLM instance if API key is provided."""
    if not GEMINI_API_KEY:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=GEMINI_API_KEY,
            temperature=0.2,
        )
    except Exception as e:
        logger.warning("Could not initialize Gemini LLM (%s). Using fallback generator.", e)
        return None


def classify_intent_node(state: AgentState) -> Dict[str, Any]:
    """Node 1: Classify user query into a domain-specific inventory action."""
    query = state["question"].lower()

    # Rule-based fast matching & keyword extraction
    if any(k in query for k in ["expir", "spoil", "batch", "shelf life", "going bad", "rotten"]):
        intent = "expiry_risk"
    elif any(k in query for k in ["run out", "stockout", "next 3 days", "next three days", "days left", "days remaining", "deplet"]):
        intent = "stockout_risk"
    elif any(k in query for k in ["reorder", "order today", "buy more", "purchase", "restock"]):
        intent = "reorder_advice"
    elif any(k in query for k in ["sold most", "sold the most", "most sold", "top sell", "fast moving", "bestseller", "least sold", "slow moving", "velocity"]):
        intent = "fast_slow_moving"
    elif any(k in query for k in ["running low", "low stock", "shortage", "below reorder"]):
        intent = "low_stock"
    elif any(k in query for k in ["health", "summary", "overview", "total stock", "valuation", "kpi"]):
        intent = "overview"
    else:
        # If ambiguous and LLM is present, ask LLM to classify
        llm = get_llm()
        if llm:
            try:
                prompt = (
                    "Classify this retail store owner query into exactly one category: "
                    "['low_stock', 'stockout_risk', 'expiry_risk', 'fast_slow_moving', 'reorder_advice', 'overview', 'general'].\n"
                    f"Query: \"{state['question']}\"\n"
                    "Respond with ONLY the category keyword."
                )
                res = llm.invoke([HumanMessage(content=prompt)]).content.strip().lower()
                intent = res if res in [
                    "low_stock", "stockout_risk", "expiry_risk", "fast_slow_moving", "reorder_advice", "overview"
                ] else "general"
            except Exception:
                intent = "overview"
        else:
            intent = "overview"

    return {"intent": intent}


def fetch_verified_data_node(state: AgentState) -> Dict[str, Any]:
    """Node 2: Deterministically execute the matching verified inventory tool."""
    intent = state.get("intent", "overview")
    data: Dict[str, Any] = {}

    try:
        if intent == "low_stock":
            data["alerts"] = get_low_stock_alerts(db_manager)
        elif intent == "stockout_risk":
            data["forecast"] = get_stockout_risk_forecast(db_manager, days_horizon=3)
        elif intent == "expiry_risk":
            data["expiry"] = get_expiry_risk_analysis(db_manager, warning_days=7, critical_days=3)
        elif intent == "fast_slow_moving":
            data["velocity"] = get_fast_and_slow_moving_products(db_manager, lookback_days=7, top_n=5)
        elif intent == "reorder_advice":
            data["reorder"] = get_reorder_recommendations(db_manager, sales_lookback_days=7)
        elif intent == "overview":
            data["summary"] = get_inventory_health_summary(db_manager)
            data["low_stock"] = get_low_stock_alerts(db_manager)
        else:
            data["summary"] = get_inventory_health_summary(db_manager)
    except Exception as e:
        logger.error("Error executing inventory tool for intent %s: %s", intent, e)
        return {"verified_data": {}, "error": str(e)}

    return {"verified_data": data}


def synthesize_explanation_node(state: AgentState) -> Dict[str, Any]:
    """Node 3: Synthesize a shopkeeper-friendly explanation of verified metrics."""
    intent = state.get("intent", "overview")
    data = state.get("verified_data", {})
    question = state.get("question", "")
    llm = get_llm()

    # If Gemini LLM is configured, use it to craft a natural explanation
    if llm:
        system_msg = (
            "You are StockSage, an expert Agentic AI Inventory Assistant for small grocery and dairy retailers. "
            "You receive verified, deterministic numbers fetched from an IBM Db2 database. "
            "RULES:\n"
            "1. Be concise, actionable, and friendly for a busy shop owner.\n"
            "2. Never alter or hallucinate quantities or prices. Use the verified data provided verbatim.\n"
            "3. Highlight urgent actions (critical stockouts, expiry warnings, reorder suggestions).\n"
            "4. Format your answer with clear markdown bullet points and bold highlights.\n"
            "5. If currency is mentioned, use Indian Rupees (₹)."
        )
        user_prompt = (
            f"Shopkeeper's Question: \"{question}\"\n"
            f"Identified Category: {intent}\n"
            f"Verified IBM Db2 Data:\n{data}\n\n"
            "Please provide a helpful, structured operational response."
        )

        try:
            resp = llm.invoke([
                SystemMessage(content=system_msg),
                HumanMessage(content=user_prompt),
            ])
            return {"response": resp.content}
        except Exception as e:
            logger.warning("LLM generation failed (%s). Falling back to deterministic template.", e)

    # Deterministic fallback response generation (guarantees offline/local operation)
    if intent == "low_stock":
        alerts = data.get("alerts", [])
        if not alerts:
            resp = "✅ **All stock levels are healthy!** None of your products are currently below their reorder threshold."
        else:
            lines = [f"⚠️ **Found {len(alerts)} products running low on stock:**\n"]
            for a in alerts:
                lines.append(
                    f"- **{a['product_name']}** ({a['category']}): Current stock is **{a['current_stock']} units** "
                    f"(Reorder level: {a['reorder_level']}, Deficit: **{a['deficit']} units**). "
                    f"Supplier: *{a['supplier_name']}* ({a['contact_details']})."
                )
            lines.append("\n💡 **Action:** Contact suppliers to place replenish orders before stock runs dry.")
            resp = "\n".join(lines)

    elif intent == "stockout_risk":
        forecast = data.get("forecast", [])
        critical = [f for f in forecast if f["risk_level"] == "CRITICAL"]
        if not critical:
            resp = "✅ **Low stockout risk!** Based on the last 7 days of sales, no products are projected to run out within 3 days."
        else:
            lines = [f"🚨 **High Stockout Risk Alert:** {len(critical)} products may run out within the next 3 days!\n"]
            for c in critical:
                lines.append(
                    f"- **{c['product_name']}**: Current stock is **{c['current_stock']} units**, "
                    f"selling at **{c['avg_daily_sales']} units/day**. "
                    f"Projected to run out in **{c['days_of_stock_remaining']} days** (est. {c['estimated_stockout_date']})."
                )
            lines.append("\n💡 **Action:** Prioritize ordering these items immediately.")
            resp = "\n".join(lines)

    elif intent == "expiry_risk":
        exp = data.get("expiry", {})
        crit = exp.get("critical_batches", [])
        warn = exp.get("warning_batches", [])
        lines = ["📅 **Batch Expiry Intelligence Report:**\n"]
        if crit:
            lines.append(f"🚨 **Critical Expiry (≤ 3 Days Remaining) — {len(crit)} batches:**")
            for b in crit:
                lines.append(
                    f"- Batch #{b['batch_id']}: **{b['product_name']}** — **{b['available_quantity']} units** "
                    f"expiring on **{b['expiry_date']}** ({b['days_to_expiry']} days left!)."
                )
        if warn:
            lines.append(f"\n⚠️ **Upcoming Expiry (4–7 Days Remaining) — {len(warn)} batches:**")
            for b in warn:
                lines.append(
                    f"- Batch #{b['batch_id']}: **{b['product_name']}** — **{b['available_quantity']} units** "
                    f"expiring on **{b['expiry_date']}**."
                )
        if not crit and not warn:
            lines.append("✅ No batches are at risk of expiring within the next 7 days.")
        else:
            lines.append("\n💡 **Action:** Consider marking down near-expiry dairy items or placing them in front display (FIFO).")
        resp = "\n".join(lines)

    elif intent == "fast_slow_moving":
        vel = data.get("velocity", {})
        fast = vel.get("fast_moving", [])
        slow = vel.get("slow_moving", [])
        lines = [f"📊 **Sales Velocity Report (Past {vel.get('lookback_days', 7)} Days):**\n"]
        lines.append("🚀 **Top Fast-Moving Products:**")
        for f in fast:
            lines.append(f"- **{f['product_name']}**: {f['total_quantity_sold']} units sold (₹{f['total_revenue']:.2f})")
        lines.append("\n🐢 **Slow-Moving / Low-Turnover Products:**")
        for s in slow:
            lines.append(f"- **{s['product_name']}**: {s['total_quantity_sold']} units sold (₹{s['total_revenue']:.2f})")
        resp = "\n".join(lines)

    elif intent == "reorder_advice":
        reorder = data.get("reorder", [])
        if not reorder:
            resp = "✅ **No reorders needed today!** All products have adequate inventory coverage."
        else:
            lines = [f"📦 **Smart Reorder Plan:** We recommend reordering {len(reorder)} products today:\n"]
            total_est_cost = 0.0
            for r in reorder:
                total_est_cost += r["estimated_purchase_cost"]
                badge = "🔴 URGENT" if r["urgency"] == "HIGH" else "🟡 NORMAL"
                lines.append(
                    f"- {badge} **{r['product_name']}**: Reorder **{r['recommended_order_quantity']} units** "
                    f"(Current stock: {r['current_stock']}, Supplier: {r['supplier_name']}, "
                    f"Lead time: {r['lead_time_days']} day(s), Est. cost: ₹{r['estimated_purchase_cost']:.2f})"
                )
            lines.append(f"\n💰 **Total Estimated Order Value: ₹{total_est_cost:,.2f}**")
            resp = "\n".join(lines)

    else:
        summary = data.get("summary", {})
        resp = (
            f"🏪 **StockSage Store Overview:**\n"
            f"- **Total Products Monitored:** {summary.get('total_products', 0)}\n"
            f"- **Total Units on Hand:** {summary.get('total_units_in_stock', 0):,} units\n"
            f"- **Estimated Inventory Value:** ₹{summary.get('total_inventory_valuation', 0):,.2f}\n"
            f"- **Low Stock Alerts:** {summary.get('low_stock_count', 0)} product(s)\n"
            f"- **Critical Expiry Batches:** {summary.get('critical_expiry_count', 0)} batch(es)\n\n"
            f"Ask me questions like *'Which products are running low?'*, *'What should I reorder today?'*, or *'What is expiring this week?'*!"
        )

    return {"response": resp}


# Build LangGraph workflow
def build_stocksage_graph():
    """Assemble single LangGraph with 3 functional nodes and deterministic routing."""
    workflow = StateGraph(AgentState)

    workflow.add_node("classify_intent", classify_intent_node)
    workflow.add_node("fetch_data", fetch_verified_data_node)
    workflow.add_node("synthesize_explanation", synthesize_explanation_node)

    workflow.set_entry_point("classify_intent")
    workflow.add_edge("classify_intent", "fetch_data")
    workflow.add_edge("fetch_data", "synthesize_explanation")
    workflow.add_edge("synthesize_explanation", END)

    return workflow.compile()


# Global agent runner
agent_app = build_stocksage_graph()


def ask_stocksage(question: str) -> str:
    """Convenience helper to invoke the LangGraph agent with a query."""
    initial_state: AgentState = {
        "question": question,
        "intent": "",
        "verified_data": {},
        "response": "",
        "error": None,
    }
    final_state = agent_app.invoke(initial_state)
    return final_state["response"]
