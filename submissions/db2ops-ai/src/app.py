"""Db2Ops AI Streamlit application."""
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
import logging
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ai.insights import summarize
from src.ai.llm import LLMUnavailable
from src.ai.query_executor import execute_read_query
from src.ai.sql_generator import generate_sql
from src.ai.sql_validator import UnsafeQuery
from src.components.charts import show_dataframe_chart
from src.components.sidebar import CSS, render_sidebar
from src.components.tables import result_table
from src.config import get_settings
from src.database.connection import DatabaseUnavailable, test_connection
from src.database.queries import analytics_frames, live_schema_context, table_preview
from src.database.schema import TABLES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("db2ops")
st.set_page_config(page_title="Db2Ops AI", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)
SUGGESTIONS = ["What is our total revenue?", "Show the top five customers by spending", "Which products generate the highest revenue?", "Show pending payments", "Compare revenue by product category"]


def money(value):
    try:
        return f"₹{float(value):,.0f}"
    except (TypeError, ValueError):
        return "₹—"


def header(title, subtitle):
    st.markdown(f"<div class='eyebrow'>DB2OPS AI / WORKSPACE</div><h1>{title}</h1><p class='muted'>{subtitle}</p>", unsafe_allow_html=True)


def add_history(question, sql, status, elapsed, detail=""):
    st.session_state.query_history.insert(0, {"timestamp": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"), "question": question, "sql": sql, "status": status, "duration_ms": elapsed, "detail": detail})
    st.session_state.query_history[:] = st.session_state.query_history[:100]


def assistant_run(question):
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        generated = ""
        try:
            with st.spinner("Understanding your question and generating Db2 SQL…"):
                recent = st.session_state.messages[-6:]
                history_context = "\n".join(
                    f"{item['role']}: {item['content']}" + (f"\nSQL: {item['sql']}" if item.get("sql") else "")
                    for item in recent
                )
                generated = generate_sql(question, history_context, live_schema_context())
            result_df, elapsed = execute_read_query(generated)
            st.success(f"Query completed · {elapsed:g} ms · {len(result_df)} rows returned")
            st.markdown("**Generated Db2 SQL**")
            st.code(generated, language="sql")
            result_table(result_df, f"query_{len(st.session_state.query_history)}")
            with st.spinner("Summarizing retrieved records…"):
                answer = summarize(question, result_df)
            st.markdown(answer)
            st.caption("Suggestions: ask for a time comparison, a different grouping, or a CSV export.")
            add_history(question, generated, "Success", elapsed)
            st.session_state.messages.append({"role": "user", "content": question})
            st.session_state.messages.append({"role": "assistant", "content": answer, "sql": generated})
        except (LLMUnavailable, DatabaseUnavailable, UnsafeQuery) as exc:
            logger.info("Assistant request stopped: %s", type(exc).__name__)
            st.error(str(exc))
            if generated:
                st.code(generated, language="sql")
            add_history(question, generated, "Rejected" if isinstance(exc, UnsafeQuery) else "Failed", 0, str(exc))
        except Exception as exc:
            logger.error("Assistant request failed (%s)", type(exc).__name__)
            st.error("The request failed. Check your Db2 connection, API configuration, and application log, then try again.")
            add_history(question, generated, "Failed", 0, type(exc).__name__)


def dashboard():
    header("Your data, in focus.", "Live business metrics and a natural language path into IBM Db2.")
    try:
        from src.database.connection import query_dataframe
        with st.spinner("Loading live metrics from Db2…"):
            checks = {
                "Customers": "SELECT COUNT(*) AS N FROM CUSTOMERS",
                "Orders": "SELECT COUNT(*) AS N FROM ORDERS",
                "Revenue": "SELECT COALESCE(SUM(TOTAL_AMOUNT),0) AS N FROM ORDERS WHERE ORDER_STATUS <> 'CANCELLED'",
                "Products": "SELECT COUNT(*) AS N FROM PRODUCTS",
            }
            values = {name: query_dataframe(sql)[0].iloc[0, 0] for name, sql in checks.items()}
        st.markdown("<div class='hero'><div class='eyebrow'>CONNECTION ACTIVE · IBM Db2</div><h2 style='margin:.35rem 0'>Your Data. Your Language.</h2><span class='muted'>Powered by IBM Db2 and LangChain</span></div>", unsafe_allow_html=True)
        cols = st.columns(4)
        cols[0].metric("Customers", f"{int(values['Customers']):,}")
        cols[1].metric("Orders", f"{int(values['Orders']):,}")
        cols[2].metric("Revenue", money(values["Revenue"]))
        cols[3].metric("Products", f"{int(values['Products']):,}")
        c1, c2 = st.columns([1.3, 1])
        with c1:
            st.subheader("Revenue over time")
            monthly = query_dataframe("SELECT YEAR(ORDER_DATE) AS Y, MONTH(ORDER_DATE) AS M, SUM(TOTAL_AMOUNT) AS REVENUE FROM ORDERS WHERE ORDER_STATUS <> 'CANCELLED' GROUP BY YEAR(ORDER_DATE), MONTH(ORDER_DATE) ORDER BY Y,M")[0]
            if not monthly.empty:
                monthly["Month"] = monthly["Y"].astype(str) + "-" + monthly["M"].astype(str).str.zfill(2)
                st.plotly_chart(show_dataframe_chart(monthly, "Month", "REVENUE", "Line"), use_container_width=True)
            else: st.info("No order records yet. Initialize the demo data to see trends.")
        with c2:
            st.subheader("Recent orders")
            recent = query_dataframe("SELECT ORDER_ID, ORDER_DATE, ORDER_STATUS, TOTAL_AMOUNT FROM ORDERS ORDER BY ORDER_DATE DESC FETCH FIRST 7 ROWS ONLY")[0]
            st.dataframe(recent, use_container_width=True, hide_index=True)
        st.subheader("Try asking")
        picks = st.columns(len(SUGGESTIONS[:3]))
        for i, q in enumerate(SUGGESTIONS[:3]):
            if picks[i].button(q, key=f"dash_{i}", use_container_width=True):
                st.session_state.pending_question = q
                st.session_state.nav_page = "AI SQL Assistant"
                st.rerun()
    except DatabaseUnavailable as exc:
        st.markdown("<div class='hero'><div class='eyebrow'>DATABASE DISCONNECTED</div><h2 style='margin:.35rem 0'>Connect IBM Db2 to load live data.</h2><span class='muted'>Dashboard values are never replaced with sample statistics.</span></div>", unsafe_allow_html=True)
        st.warning(str(exc))
        st.markdown("Use **Database Connection** to verify credentials. To initialize schema and seed records, run `python scripts/setup_db.py` from this project folder.")


def ai_assistant():
    header("AI SQL Assistant", "Ask a business question. Review the Db2 SQL. Explore the records.")
    if not st.session_state.messages:
        st.markdown("<div class='hero'><div class='eyebrow'>LANGCHAIN · READ-ONLY SQL</div><h3>What would you like to understand?</h3><span class='muted'>Queries are validated before execution and limited to the application tables.</span></div>", unsafe_allow_html=True)
        cols = st.columns(3)
        for i, q in enumerate(SUGGESTIONS):
            if cols[i % 3].button(q, key=f"suggest_{i}", use_container_width=True):
                st.session_state.pending_question = q
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sql"):
                with st.expander("Generated SQL"):
                    st.code(message["sql"], language="sql")
    pending = st.session_state.pop("pending_question", None)
    question = st.chat_input("Ask about revenue, customers, orders, or products…")
    question = question or pending
    if question:
        assistant_run(question)


def explorer():
    header("Data Explorer", "Inspect the five Db2 application tables and export a bounded preview.")
    table = st.selectbox("Application table", TABLES)
    limit = st.slider("Preview rows", 10, 500, 50, 10)
    try:
        from src.database.connection import query_dataframe
        count = int(query_dataframe(f"SELECT COUNT(*) AS N FROM {table}")[0].iloc[0, 0])
        st.metric("Total records", f"{count:,}")
        df = table_preview(table, limit)
        st.caption(f"Showing {len(df):,} row(s) from {table}")
        result_table(df, f"{table.lower()}_preview")
        cols, _ = query_dataframe("SELECT COLNAME, TYPENAME, LENGTH, NULLS FROM SYSCAT.COLUMNS WHERE TABSCHEMA=CURRENT SCHEMA AND TABNAME=? ORDER BY COLNO", (table,))
        with st.expander("Column definitions"):
            st.dataframe(cols, hide_index=True, use_container_width=True)
    except DatabaseUnavailable as exc:
        st.error(str(exc))


def analytics():
    header("Analytics", "Interactive views calculated directly from Db2 records.")
    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=540)
        date_range = st.date_input("Date range", value=(start_date, end_date))
        if len(date_range) != 2:
            st.info("Choose both a start and end date to load analytics.")
            return
        start_date, end_date = date_range
        if start_date > end_date:
            st.error("Start date must be on or before end date.")
            return
        with st.spinner("Retrieving analytics from Db2…"):
            frames = analytics_frames(start_date, end_date)
        selection = st.selectbox("Analysis", ["Revenue by month", "Top-selling products", "Highest-spending customers", "Revenue by city", "Payment status", "Category performance"])
        mapping = {"Revenue by month": ("monthly","REVENUE"),"Top-selling products":("products","REVENUE"),"Highest-spending customers":("customers","SPEND"),"Revenue by city":("cities","REVENUE"),"Payment status":("payments","PAYMENT_COUNT"),"Category performance":("categories","REVENUE")}
        key, metric = mapping[selection]
        df = frames[key]
        dimension = "SALES_MONTH" if key == "monthly" else ("PAYMENT_STATUS" if key == "payments" else df.columns[0])
        if key == "monthly":
            df = df.copy(); df["PERIOD"] = df["SALES_YEAR"].astype(str) + "-" + df["SALES_MONTH"].astype(str).str.zfill(2); dimension = "PERIOD"
        chart_type = st.selectbox("Chart type", ["Bar", "Line", "Area", "Pie"], index=1 if key == "monthly" else 0)
        st.plotly_chart(show_dataframe_chart(df, dimension, metric, chart_type), use_container_width=True)
        result_table(df, f"analytics_{key}")
        st.subheader("AI insight")
        if st.button("Summarize these results with LangChain"):
            try:
                with st.spinner("Summarizing retrieved Db2 results…"):
                    st.info(summarize(selection, df))
            except LLMUnavailable as exc: st.warning(str(exc))
    except DatabaseUnavailable as exc:
        st.error(str(exc))


def history():
    header("Query History", "This history is held in this Streamlit session only.")
    records = st.session_state.query_history
    if st.button("Clear session history", disabled=not records):
        st.session_state.query_history = []; st.rerun()
    if not records:
        st.info("No queries in this session yet.")
    for i, record in enumerate(records):
        with st.expander(f"{record['timestamp']} · {record['status']} · {record['question']}"):
            st.caption(f"Execution time: {record['duration_ms']} ms")
            if record["sql"]: st.code(record["sql"], language="sql")
            if record["detail"]: st.caption(record["detail"])
            if record["sql"] and st.button("Re-run validated query", key=f"rerun_{i}"):
                try:
                    df, ms = execute_read_query(record["sql"])
                    st.success(f"Completed in {ms:g} ms")
                    result_table(df, f"rerun_{i}")
                    add_history(record["question"], record["sql"], "Success", ms)
                except Exception as exc: st.error(f"Re-run stopped: {exc}")


def connection_page():
    header("Database Connection", "Credentials stay in your local .env file and are never sent to the language model.")
    cfg = get_settings()
    st.markdown(f"**Target:** `{cfg.db2_database}` at `{cfg.db2_hostname}:{cfg.db2_port}` · user `{cfg.db2_uid}`")
    if st.button("Test Db2 connection", type="primary"):
        try:
            with st.spinner("Running SELECT 1 FROM SYSIBM.SYSDUMMY1…"):
                result = test_connection()
            st.success(f"Connected to IBM Db2 database {result['database']}. Test query returned a row.")
        except DatabaseUnavailable as exc: st.error(str(exc))
    st.subheader("Setup")
    st.markdown("1. Install IBM Db2 Community Edition (local instance or IBM's container workflow).\n2. Copy `.env.example` to `.env` and set `DB2_DATABASE`, `DB2_HOSTNAME`, `DB2_PORT`, `DB2_UID`, and `DB2_PWD`.\n3. Initialize application tables with `python scripts/setup_db.py`.\n4. Add `OPENAI_API_KEY` to enable LangChain features.")
    st.caption("This page does not display or log passwords or API keys.")


def about():
    header("About Db2Ops AI", "A LangChain-powered copilot for real IBM Db2 business data.")
    st.markdown("Db2Ops AI translates natural-language questions into Db2 SQL, validates that the query is a single read-only SELECT over the five application tables, executes it through `ibm_db`, and summarizes only the retrieved result rows.")
    st.markdown("**Core stack:** Streamlit · IBM Db2 · ibm_db · LangChain · OpenAI · SQLGlot · Pandas · Plotly")
    st.markdown("**Security boundary:** generated SQL is parsed and constrained before execution; row counts are capped. Use a Db2 account with SELECT-only grants for interactive sessions.")


if "query_history" not in st.session_state: st.session_state.query_history = []
if "messages" not in st.session_state: st.session_state.messages = []
if "page" not in st.session_state: st.session_state.page = "Dashboard"
page = render_sidebar()
st.session_state.page = page
routes = {"Dashboard": dashboard,"AI SQL Assistant": ai_assistant,"Data Explorer": explorer,"Analytics": analytics,"Query History": history,"Database Connection": connection_page,"About": about}
routes[page]()
