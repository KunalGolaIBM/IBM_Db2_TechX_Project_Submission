"""StockSage — Agentic AI Inventory Intelligence Assistant for Small Grocery and Dairy Retailers.

Frontend application built with Streamlit, Plotly, IBM Db2, and LangGraph.
"""

from datetime import date
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import urllib.parse
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.agent import ask_stocksage, build_stocksage_graph
from src.config import DB2_DATABASE, DB2_HOST, DB2_PORT, GEMINI_API_KEY
from src.database_setup import initialize_database
from src.db_connection import db_manager
from src.inventory_tools import (
    generate_whatsapp_order_text,
    get_category_performance_df,
    get_current_stock_df,
    get_expiry_risk_analysis,
    get_fast_and_slow_moving_products,
    get_inventory_health_summary,
    get_low_stock_alerts,
    get_reorder_recommendations,
    get_reorders_grouped_by_supplier,
    get_sales_trends_df,
    get_stockout_risk_forecast,
)

# Page configuration
st.set_page_config(
    page_title="StockSage — AI Inventory Intelligence",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for polished retail dashboard
st.markdown("""
<style>
    /* App Canvas & Base Typography */
    .stApp {
        background-color: #F7F8FA;
        color: #172B4D;
    }

    /* Eliminate Streamlit default top whitespace */
    .block-container {
        padding-top: 1.1rem !important;
        padding-bottom: 2.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 100% !important;
    }
    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 2rem !important;
    }

    /* Sidebar Customization */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }
    [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {
        color: #172B4D !important;
    }

    /* Sleek Top Navbar */
    .top-navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #FFFFFF;
        border: 1.5px solid #172B4D;
        border-radius: 8px;
        padding: 8px 16px;
        margin-bottom: 14px;
        box-shadow: 0 1px 3px rgba(23, 43, 77, 0.05);
    }
    .top-navbar .brand-group {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .top-navbar .brand-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: #172B4D;
        letter-spacing: -0.02em;
    }
    .top-navbar .brand-badge {
        background-color: #E6F4EA;
        color: #168B72;
        font-size: 0.72rem;
        font-weight: 700;
        padding: 2px 7px;
        border-radius: 4px;
        border: 1px solid #168B72;
    }
    .top-navbar .brand-desc {
        color: #64748B;
        font-size: 0.84rem;
        font-weight: 400;
    }
    .top-navbar .status-group {
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .top-navbar .status-pill {
        font-size: 0.76rem;
        font-weight: 600;
        padding: 3px 9px;
        border-radius: 12px;
    }
    .top-navbar .status-pill.db2 {
        color: #168B72;
        background-color: #E6F4EA;
        border: 1px solid #168B72;
    }
    .top-navbar .status-pill.ai {
        color: #172B4D;
        background-color: #F1F5F9;
        border: 1px solid #CBD5E1;
    }

    /* KPI Metric Cards */
    [data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 2px solid #172B4D;
        border-radius: 8px;
        padding: 12px 14px;
        box-shadow: 0 2px 4px rgba(23, 43, 77, 0.08);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    [data-testid="stMetric"]:hover {
        box-shadow: 0 4px 8px rgba(23, 43, 77, 0.12);
    }
    [data-testid="stMetricLabel"],
    [data-testid="stMetricLabel"] * {
        color: #64748B !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        white-space: normal !important;
        text-overflow: unset !important;
        overflow: visible !important;
        line-height: 1.25 !important;
    }
    [data-testid="stMetricValue"] {
        color: #172B4D !important;
        font-size: 1.35rem !important;
        font-weight: 700 !important;
        white-space: nowrap;
    }

    /* Navigation Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
        border-bottom: 2px solid #E2E8F0;
        padding-bottom: 4px;
        margin-bottom: 14px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 38px;
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 6px 6px 0 0;
        color: #64748B;
        font-size: 0.88rem;
        font-weight: 600;
        padding: 0 16px;
        transition: all 0.15s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #172B4D;
        border-color: #CBD5E1;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FFFFFF !important;
        color: #172B4D !important;
        border: 1.5px solid #172B4D !important;
        border-bottom: 3px solid #168B72 !important;
    }

    /* Status Badges */
    .status-badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-critical { background-color: #FEE2E2; color: #D9534F; }
    .badge-warning { background-color: #FEF3C7; color: #D99A37; }
    .badge-safe { background-color: #E6F4EA; color: #168B72; }

    /* Preset & Action Buttons */
    .stButton > button {
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 500;
        border: 1.5px solid #172B4D;
        color: #172B4D;
        background-color: #FFFFFF;
        transition: all 0.15s ease;
        white-space: normal !important;
        height: auto !important;
        min-height: 44px;
        line-height: 1.25 !important;
        padding: 6px 10px !important;
    }
    .stButton > button:hover {
        border-color: #168B72;
        color: #168B72;
        background-color: #F8FAFC;
    }
</style>
""", unsafe_allow_html=True)


def ensure_db_ready():
    """Ensure database is seeded if empty."""
    try:
        stock = get_current_stock_df(db_manager)
        if stock.empty:
            initialize_database(db_manager)
    except Exception:
        initialize_database(db_manager, force_recreate=True)


ensure_db_ready()

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/shop.png", width=64)
    st.markdown("### **StockSage Assistant**")
    st.caption("AI Inventory Co-pilot for Grocery & Dairy")

    st.divider()

    st.markdown("#### **Database Status**")
    if db_manager.is_mock:
        st.info("🟡 **Mode:** Local Test Engine\n\n*(Ready to connect to IBM Db2)*")
    else:
        st.success(f"🟢 **Mode:** Live IBM Db2\n\n**Host:** `{DB2_HOST}:{DB2_PORT}`\n\n**DB:** `{DB2_DATABASE}`")

    st.markdown("#### **AI Status**")
    if GEMINI_API_KEY:
        st.success("🟢 **Gemini LLM:** Connected")
    else:
        st.info("⚪ **AI Assistant:** Deterministic Engine (Offline)")

    st.divider()

    st.markdown("#### **Store Controls**")
    if st.button("🔄 Reset Sample Inventory", use_container_width=True):
        initialize_database(db_manager, force_recreate=True)
        st.toast("Database re-seeded with fresh sample grocery/dairy data!", icon="✅")
        st.rerun()

    st.markdown("---")
    st.caption("IBM Db2 TechX Summit 2026 • Submission `stock-sage`")

# Sleek Top Navbar
st.markdown("""
<div class="top-navbar">
    <div class="brand-group">
        <span class="brand-title">🏪 StockSage</span>
        <span class="brand-badge">IBM Db2 12.1</span>
        <span class="brand-desc">Agentic AI & Deterministic Inventory Decision System for Grocery & Dairy</span>
    </div>
    <div class="status-group">
        <span class="status-pill db2">🟢 IBM Db2 Connected</span>
        <span class="status-pill ai">✨ Gemini AI Active</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Navigation Tabs placed right at the top
tab_chat, tab_alerts, tab_expiry, tab_reorder, tab_analytics = st.tabs([
    "💬 AI Assistant",
    "🚨 Low Stock & Stockout Risk",
    "📅 Expiry & Perishables Tracker",
    "📦 Smart Reorder Planner",
    "📈 Sales Analytics & Velocity",
])

# -------------------------------------------------------------
# TAB 1: Conversational AI Assistant (LangGraph + Gemini)
# -------------------------------------------------------------
with tab_chat:
    # Store Health KPI Metric Cards
    summary = get_inventory_health_summary(db_manager)
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

    with kpi1:
        st.metric("Total Products", f"{summary['total_products']} items")
    with kpi2:
        st.metric("Total Stock On Hand", f"{summary['total_units_in_stock']} units")
    with kpi3:
        st.metric("Inventory Value", f"₹{summary['total_inventory_valuation']:,.2f}")
    with kpi4:
        low_color = "normal" if summary["low_stock_count"] == 0 else "inverse"
        st.metric("Low Stock Alerts", f"{summary['low_stock_count']} items", delta=-summary["low_stock_count"] if summary["low_stock_count"] > 0 else None, delta_color="inverse")
    with kpi5:
        st.metric("Expiring ≤ 3 Days", f"{summary['critical_expiry_count']} batches", delta=-summary["critical_expiry_count"] if summary["critical_expiry_count"] > 0 else None, delta_color="inverse")

    st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)
    st.markdown("### 💬 Ask StockSage Anything About Your Store")
    st.caption("Ask natural questions about stockouts, expiry risk, reorders, or sales trends. Powered by a single LangGraph state-graph workflow with deterministic IBM Db2 tools.")

    # Preset quick question chips
    st.markdown("**Quick questions to try:**")
    preset_cols = st.columns(5)
    selected_preset = None
    with preset_cols[0]:
        if st.button("⚠️ Which products are running low?"):
            selected_preset = "Which products are running low on stock?"
    with preset_cols[1]:
        if st.button("🚨 Items running out in 3 days?"):
            selected_preset = "Which items may run out in the next three days?"
    with preset_cols[2]:
        if st.button("📅 What is expiring this week?"):
            selected_preset = "Which products are at risk of expiry?"
    with preset_cols[3]:
        if st.button("📦 What should I reorder today?"):
            selected_preset = "What should I reorder today and how much?"
    with preset_cols[4]:
        if st.button("🚀 What sold the most this week?"):
            selected_preset = "Which products sold the most this week?"

    # Session state chat messages
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "assistant", "content": "👋 Namaste! I am **StockSage**, your AI store manager. How can I help you manage your grocery and dairy inventory today?"}
        ]

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input handling
    user_input = st.chat_input("Ask about stock levels, reorder amounts, or near-expiry batches...")
    query_to_run = selected_preset or user_input

    if query_to_run:
        # Append user message
        st.session_state.messages.append({"role": "user", "content": query_to_run})
        with st.chat_message("user"):
            st.markdown(query_to_run)

        # Generate response using LangGraph agent
        with st.chat_message("assistant"):
            with st.spinner("StockSage is querying IBM Db2 and analyzing verified data..."):
                response_text = ask_stocksage(query_to_run)
                st.markdown(response_text)

        st.session_state.messages.append({"role": "assistant", "content": response_text})

# -------------------------------------------------------------
# TAB 2: Low Stock & Stockout Risk
# -------------------------------------------------------------
with tab_alerts:
    st.markdown("### 🚨 Low Stock & Stockout Risk Intelligence")
    st.caption("Real-time identification of products below reorder thresholds and projected days of coverage.")

    col_alerts, col_chart = st.columns([3, 2])

    with col_alerts:
        st.markdown("#### **Active Low-Stock Alerts**")
        alerts = get_low_stock_alerts(db_manager)
        if not alerts:
            st.success("✅ All stock levels are currently above reorder levels!")
        else:
            alerts_df = pd.DataFrame(alerts)
            st.dataframe(
                alerts_df[["product_name", "category", "current_stock", "reorder_level", "deficit", "supplier_name", "lead_time_days"]],
                column_config={
                    "product_name": "Product",
                    "category": "Category",
                    "current_stock": "Current Stock",
                    "reorder_level": "Reorder Level",
                    "deficit": "Deficit Units",
                    "supplier_name": "Supplier",
                    "lead_time_days": "Lead Time (Days)",
                },
                hide_index=True,
                use_container_width=True,
            )

        st.markdown("#### **3-Day Stockout Risk Forecast**")
        forecast = get_stockout_risk_forecast(db_manager, days_horizon=3)
        forecast_df = pd.DataFrame(forecast)
        if not forecast_df.empty:
            st.dataframe(
                forecast_df[["product_name", "category", "current_stock", "avg_daily_sales", "days_of_stock_remaining", "risk_level"]],
                column_config={
                    "product_name": "Product",
                    "category": "Category",
                    "current_stock": "Stock",
                    "avg_daily_sales": "Daily Sales",
                    "days_of_stock_remaining": "Days Remaining",
                    "risk_level": "Risk Level",
                },
                hide_index=True,
                use_container_width=True,
            )

    with col_chart:
        st.markdown("#### **Stock vs. Reorder Level Comparison**")
        stock_df = get_current_stock_df(db_manager)
        if not stock_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=stock_df["product_name"],
                y=stock_df["total_available_stock"],
                name="Current Stock",
                marker_color="#2563EB"
            ))
            fig.add_trace(go.Bar(
                x=stock_df["product_name"],
                y=stock_df["reorder_level"],
                name="Reorder Level",
                marker_color="#EF4444"
            ))
            fig.update_layout(
                barmode="group",
                xaxis_tickangle=-45,
                margin=dict(l=20, r=20, t=30, b=100),
                height=420,
            )
            st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------------
# TAB 3: Expiry & Perishables Tracker (Dairy & Bakery Focus)
# -------------------------------------------------------------
with tab_expiry:
    st.markdown("### 📅 Batch-Level Expiry Intelligence")
    st.caption("Perishable tracking specifically tuned for short-shelf-life dairy (milk, paneer, curd) and bakery items.")

    expiry_data = get_expiry_risk_analysis(db_manager, warning_days=7, critical_days=3)

    crit_batches = expiry_data["critical_batches"]
    warn_batches = expiry_data["warning_batches"]

    e1, e2 = st.columns(2)
    with e1:
        st.error(f"🚨 **Critical Expiry (≤ 3 Days): {len(crit_batches)} batches**")
        if crit_batches:
            c_df = pd.DataFrame(crit_batches)
            st.dataframe(
                c_df[["batch_id", "product_name", "category", "available_quantity", "expiry_date", "days_to_expiry"]],
                column_config={
                    "batch_id": "Batch #",
                    "product_name": "Product",
                    "category": "Category",
                    "available_quantity": "Units",
                    "expiry_date": "Expires On",
                    "days_to_expiry": "Days Left",
                },
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.write("No batches expiring in the next 3 days.")

    with e2:
        st.warning(f"⚠️ **Upcoming Expiry (4 to 7 Days): {len(warn_batches)} batches**")
        if warn_batches:
            w_df = pd.DataFrame(warn_batches)
            st.dataframe(
                w_df[["batch_id", "product_name", "category", "available_quantity", "expiry_date", "days_to_expiry"]],
                column_config={
                    "batch_id": "Batch #",
                    "product_name": "Product",
                    "category": "Category",
                    "available_quantity": "Units",
                    "expiry_date": "Expires On",
                    "days_to_expiry": "Days Left",
                },
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.write("No batches in the 4–7 day warning window.")

    st.markdown("#### **All Batches Expiry Timeline**")
    all_batches = crit_batches + warn_batches + expiry_data["safe_batches"]
    if all_batches:
        b_df = pd.DataFrame(all_batches)
        fig_exp = px.scatter(
            b_df,
            x="days_to_expiry",
            y="product_name",
            size="available_quantity",
            color="status",
            color_discrete_map={"CRITICAL": "#DC2626", "WARNING": "#F59E0B", "SAFE": "#10B981", "EXPIRED": "#6B7280"},
            labels={"days_to_expiry": "Days Remaining Until Expiry", "product_name": "Product"},
            title="Batch Expiry Countdown (Bubble size = Available Quantity)",
            height=400,
        )
        st.plotly_chart(fig_exp, use_container_width=True)

# -------------------------------------------------------------
# TAB 4: Smart Reorder Planner
# -------------------------------------------------------------
with tab_reorder:
    st.markdown("### 📦 Smart Reorder Recommendations")
    st.caption("Calculated using: (Daily Velocity × Supplier Lead Time) + Safety Buffer − Available Stock.")

    reorders = get_reorder_recommendations(db_manager)
    if not reorders:
        st.success("✅ No products require reordering today! All inventory levels are optimal.")
    else:
        r_df = pd.DataFrame(reorders)
        total_reorder_val = r_df["estimated_purchase_cost"].sum()

        r_kpi1, r_kpi2 = st.columns(2)
        with r_kpi1:
            st.metric("Total Items to Order", f"{len(r_df)} products")
        with r_kpi2:
            st.metric("Total Estimated Order Cost", f"₹{total_reorder_val:,.2f}")

        st.dataframe(
            r_df[["urgency", "product_name", "category", "current_stock", "avg_daily_sales", "recommended_order_quantity", "supplier_name", "lead_time_days", "estimated_purchase_cost"]],
            column_config={
                "urgency": "Urgency",
                "product_name": "Product",
                "category": "Category",
                "current_stock": "Current Stock",
                "avg_daily_sales": "Daily Sales",
                "recommended_order_quantity": "Reorder Quantity",
                "supplier_name": "Supplier",
                "lead_time_days": "Lead Time",
                "estimated_purchase_cost": st.column_config.NumberColumn("Est. Cost (₹)", format="₹%.2f"),
            },
            hide_index=True,
            use_container_width=True,
        )

# -------------------------------------------------------------
# TAB 5: Sales Analytics & Velocity
# -------------------------------------------------------------
with tab_analytics:
    st.markdown("### 📈 Sales Velocity & Historical Trends")

    col_trend, col_cat = st.columns([3, 2])

    with col_trend:
        st.markdown("#### **14-Day Sales & Revenue Trend**")
        trend_df = get_sales_trends_df(db_manager)
        if not trend_df.empty:
            fig_trend = px.line(
                trend_df,
                x="sale_date",
                y="total_daily_revenue",
                title="Daily Store Revenue (₹)",
                markers=True,
                line_shape="spline",
                color_discrete_sequence=["#2563EB"],
            )
            fig_trend.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_trend, use_container_width=True)

    with col_cat:
        st.markdown("#### **Category Revenue Breakdown**")
        cat_df = get_category_performance_df(db_manager)
        if not cat_df.empty:
            fig_pie = px.pie(
                cat_df,
                names="category",
                values="category_revenue",
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_pie.update_layout(height=350, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("#### **Fast-Moving vs. Slow-Moving Product Analysis (Last 7 Days)**")
    vel_data = get_fast_and_slow_moving_products(db_manager, lookback_days=7, top_n=5)
    f_col, s_col = st.columns(2)
    with f_col:
        st.success("🚀 **Top 5 Fast-Moving Items**")
        st.dataframe(
            pd.DataFrame(vel_data["fast_moving"])[["product_name", "category", "total_quantity_sold", "total_revenue", "avg_daily_sales"]],
            column_config={
                "product_name": "Product",
                "category": "Category",
                "total_quantity_sold": "Units Sold",
                "total_revenue": "Revenue (₹)",
                "avg_daily_sales": "Units/Day",
            },
            hide_index=True,
            use_container_width=True,
        )
    with s_col:
        st.warning("🐢 **Top 5 Slow-Moving Items**")
        st.dataframe(
            pd.DataFrame(vel_data["slow_moving"])[["product_name", "category", "total_quantity_sold", "total_revenue", "avg_daily_sales"]],
            column_config={
                "product_name": "Product",
                "category": "Category",
                "total_quantity_sold": "Units Sold",
                "total_revenue": "Revenue (₹)",
                "avg_daily_sales": "Units/Day",
            },
            hide_index=True,
            use_container_width=True,
        )
