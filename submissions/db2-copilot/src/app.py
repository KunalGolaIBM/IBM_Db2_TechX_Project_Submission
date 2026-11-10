"""
Db2 Copilot: Refund-Dispute Assistant
Streamlit Web Application
"""
import streamlit as st
import pandas as pd
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db import get_connection, execute_query
from src.copilot import process_dispute_query
import ibm_db

# Configure Streamlit page
st.set_page_config(
    page_title="Db2 Copilot - Refund Dispute Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom high-contrast styling and wrapping
st.markdown(
    """
    <style>
    .main-header { font-size: 2.2rem; font-weight: 800; color: #0043ce; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1.15rem; color: #121619 !important; margin-bottom: 1.5rem; font-weight: 600; line-height: 1.4; }
    
    /* High-contrast Verdict Box */
    .verdict-box {
        background-color: #edf5ff;
        border: 2px solid #a6c8ff;
        border-left: 6px solid #0043ce;
        border-radius: 8px;
        padding: 18px;
        margin-top: 10px;
        color: #121619 !important;
        font-size: 1.05rem;
        line-height: 1.6;
    }
    .verdict-box h1, .verdict-box h2, .verdict-box h3, .verdict-box h4, .verdict-box strong, .verdict-box p, .verdict-box li, .verdict-box td {
        color: #121619 !important;
    }

    /* High-contrast Policy Cards */
    .policy-card {
        background-color: #ffffff;
        border: 1px solid #8d8d8d;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .policy-title {
        color: #002d9c !important;
        font-size: 1.15rem;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .policy-category {
        color: #343a40 !important;
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 8px;
    }
    .policy-content {
        color: #161616 !important;
        font-size: 0.95rem;
        line-height: 1.5;
    }

    /* Wrap SQL display instead of scrolling sideways */
    pre, code, .stCodeBlock, div[data-testid="stCodeBlock"] pre {
        white-space: pre-wrap !important;
        word-break: break-all !important;
        overflow-wrap: break-word !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_db_stats():
    """Fetch counts from Db2 tables."""
    try:
        conn = get_connection()
        c_cnt = execute_query(conn, "SELECT COUNT(*) AS C FROM CUSTOMERS")[0]["c"]
        o_cnt = execute_query(conn, "SELECT COUNT(*) AS C FROM ORDERS")[0]["c"]
        r_cnt = execute_query(conn, "SELECT COUNT(*) AS C FROM REFUNDS")[0]["c"]
        p_cnt = execute_query(conn, "SELECT COUNT(*) AS C FROM POLICIES")[0]["c"]
        a_cnt = execute_query(conn, "SELECT COUNT(*) AS C FROM QUERY_AUDIT")[0]["c"]
        ibm_db.close(conn)
        return {
            "customers": c_cnt,
            "orders": o_cnt,
            "refunds": r_cnt,
            "policies": p_cnt,
            "audits": a_cnt,
            "status": "ONLINE",
        }
    except Exception as e:
        return {"customers": 0, "orders": 0, "refunds": 0, "policies": 0, "audits": 0, "status": f"OFFLINE ({e})"}


def get_recent_audits():
    """Fetch latest queries from QUERY_AUDIT."""
    try:
        conn = get_connection()
        rows = execute_query(
            conn,
            "SELECT audit_id, question, sql_status, created_at, verdict "
            "FROM QUERY_AUDIT ORDER BY audit_id DESC FETCH FIRST 10 ROWS ONLY",
        )
        ibm_db.close(conn)
        return rows
    except Exception:
        return []


# --- SIDEBAR ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg", width=120)
    st.title("Db2 Copilot")
    st.caption("AI-Powered Refund Dispute Resolution")
    st.divider()

    st.subheader("System Status")
    stats = get_db_stats()
    if stats["status"] == "ONLINE":
        st.success("🟢 IBM Db2 12.1 Connected")
    else:
        st.error(f"🔴 Db2: {stats['status']}")

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.metric("Orders", stats["orders"])
        st.metric("Refunds", stats["refunds"])
    with col_s2:
        st.metric("Customers", stats["customers"])
        st.metric("Policies (Vector)", stats["policies"])
    st.metric("Audit Logs", stats["audits"])

    st.divider()
    st.subheader("Architecture")
    st.markdown("- **Engine**: Native `ibm_db` (Pure C Driver)")
    st.markdown("- **Vectors**: Db2 `VECTOR(384, FLOAT32)`")
    st.markdown("- **Embeddings**: FastEmbed (`bge-small-en-v1.5`)")
    st.markdown("- **LLM**: Groq `openai/gpt-oss-120b`")
    st.markdown("- **Deterministic Engine**: Python Date & Policy Math")
    st.markdown("- **Security**: AST SQL Allow-List Guardrail")


# --- MAIN CONTENT ---
st.markdown("<div class='main-header'>⚖️ Db2 Copilot: Refund Dispute Assistant</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='sub-header'>Evaluating live relational e-commerce records & native Db2 vector policy clauses with deterministic policy calculations and Groq LLM synthesis.</div>",
    unsafe_allow_html=True,
)

# Preset scenario buttons with explicit computed values
st.write("**Quick-Test Dispute Scenarios:**")
b_cols = st.columns(5)

# Session state management for instantaneous 1-click execution
if "query_input" not in st.session_state:
    st.session_state.query_input = "Order 101 has a refund request. Check delivery date, dispute date, customer tier, and decide if refund is approved."
if "run_trigger" not in st.session_state:
    st.session_state.run_trigger = False

if b_cols[0].button("📦 Order 101\n(Approved: 4d <= 7d)"):
    st.session_state.query_input = "Order 101 has a refund request. Check delivery date, dispute date, customer tier, and decide if refund is approved."
    st.session_state.run_trigger = True

if b_cols[1].button("⏰ Order 103\n(Denied: 47d > 30d)"):
    st.session_state.query_input = "Check dispute for order 103: customer changed mind. Compare delivery date and dispute request date against the 30-day window."
    st.session_state.run_trigger = True

if b_cols[2].button("🌟 Order 102\n(VIP Exception: 39d < 60d)"):
    st.session_state.query_input = "Order 102 has a refund request for a Smart TV. Check customer tier and determine if the 60-day VIP window exception applies."
    st.session_state.run_trigger = True

if b_cols[3].button("🔍 Novel Query\n(Multiple Refunds)"):
    st.session_state.query_input = "Which customers have more than one refund, and what were the reasons?"
    st.session_state.run_trigger = True

if b_cols[4].button("🚨 Security Test\n(DELETE Attempt)"):
    st.session_state.query_input = "DELETE FROM ORDERS WHERE order_id = 101"
    st.session_state.run_trigger = True

user_query = st.text_area(
    "Enter Dispute Question or SQL Enquiry:",
    value=st.session_state.query_input,
    height=70,
)

btn_analyze = st.button("🔍 Analyze Dispute with Db2 Copilot", use_container_width=True)

# Trigger if either the analyze button was clicked or a preset button was clicked
should_run = btn_analyze or st.session_state.run_trigger
st.session_state.run_trigger = False

if should_run and user_query.strip():
    start_time = time.time()
    with st.spinner("Executing Db2 Copilot Pipeline (Groq Text-to-SQL ➔ Validator ➔ Db2 SQL ➔ Python Math ➔ Vector RAG ➔ Groq Verdict)..."):
        res = process_dispute_query(user_query.strip())
    elapsed = time.time() - start_time

    # Display Verdict Box
    st.markdown("### 📋 Copilot Verdict & Decision")
    if res["status"] == "REJECTED":
        st.error(res["verdict"])
    elif res["status"] in ("GROQ_ERROR", "SQL_ERROR"):
        st.error(res["verdict"])
    else:
        # High contrast rendering
        formatted_verdict = res["verdict"].replace("\n", "<br/>")
        st.markdown(
            f"<div class='verdict-box'>{formatted_verdict}</div>",
            unsafe_allow_html=True,
        )

    st.write("")
    # Tabs for breakdown
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🧮 Python Computed Facts",
        "📊 Db2 Relational Data",
        "📜 Cited Policy Documents (Vector RAG)",
        "🛡️ Executed SQL & Security Validator",
        "🕒 Audit Log History",
    ])

    with tab1:
        st.subheader("Deterministic Calculations in Python (Pre-LLM)")
        if res.get("computed_facts"):
            for f in res["computed_facts"]:
                st.markdown(
                    f"""
                    - **Order ID**: `{f.get('order_id')}` | **Customer**: **{f.get('customer_name')}** ({f.get('customer_tier')})
                    - **Dates**: Delivered on `{f.get('delivery_date')}`, Disputed on `{f.get('dispute_date')}`
                    - **Computed Days Elapsed**: **{f.get('days_elapsed')} days**
                    - **Allowed Policy Window**: **{f.get('applicable_window_days')} days**
                    - **Applied Rule**: {f.get('applied_policy')}
                    - **Computed Policy Decision**: **`{f.get('decision')}`**
                    - **Detailed Policy Justification**: {f.get('justification')}
                    """
                )
        else:
            st.info("No individual order dispute facts computed (e.g., query was an aggregation or security check).")

    with tab2:
        st.subheader("Relational Records Retrieved from Db2")
        if res["data"]:
            df = pd.DataFrame(res["data"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No relational rows returned for this query.")

    with tab3:
        st.subheader("Db2 Vector Similarity Search Results")
        st.caption("Retrieved from table `POLICIES` using `VECTOR_DISTANCE(embedding, query_vector, COSINE)`")
        if res["policies"]:
            for p in res["policies"]:
                score_pct = int(p.get("score", 0) * 100)
                st.markdown(
                    f"""
                    <div class='policy-card'>
                        <div class='policy-title'>Policy #{p.get('policy_id')}: {p.get('policy_title')} 
                            <span style='font-size:0.9rem; color:#0043ce;'>({score_pct}% match / distance: {p.get('distance')})</span>
                        </div>
                        <div class='policy-category'>Category: {p.get('category')}</div>
                        <div class='policy-content'>{p.get('content')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No policy vectors retrieved.")

    with tab4:
        st.subheader("Text-to-SQL & Security Inspection")
        col_v1, col_v2 = st.columns([1, 3])
        with col_v1:
            if res["sql_valid"]:
                st.success("✅ Validator: APPROVED")
            else:
                st.error("❌ Validator: REJECTED")
            st.metric("Execution Latency", f"{elapsed:.2f}s")
            st.metric("Pipeline Status", res["status"])
        with col_v2:
            st.markdown("**Executed SQL Statement (Auto-wrapped):**")
            st.code(res["sql"], language="sql")
            if res["sql_error"]:
                st.warning(f"Validator Note: {res['sql_error']}")

    with tab5:
        st.subheader("Db2 `QUERY_AUDIT` Live Table")
        audits = get_recent_audits()
        if audits:
            df_audit = pd.DataFrame(audits)
            st.dataframe(df_audit, use_container_width=True)
        else:
            st.info("No audit logs found.")

else:
    st.divider()
    st.subheader("Recent Dispute Resolution Audits (from Db2 `QUERY_AUDIT`)")
    audits = get_recent_audits()
    if audits:
        df_audit = pd.DataFrame(audits)
        st.dataframe(df_audit, use_container_width=True)
