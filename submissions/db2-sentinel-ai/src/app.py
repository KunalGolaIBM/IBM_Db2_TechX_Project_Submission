"""
Interactive Enterprise Streamlit Dashboard for Db2 Sentinel AI.
Visualizes real-time financial surveillance, multi-agent LangGraph execution traces,
transaction network graph topologies, and automated regulatory SAR filings in IBM Db2.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd
import json
import networkx as nx
from datetime import datetime

from src.db.connection import get_db_manager
from src.db.schema import initialize_schema
from src.db.seed_data import seed_database
from src.db.queries import (
    get_all_transactions,
    get_all_accounts,
    get_pending_alerts,
    get_recent_audit_trail,
    get_transaction_by_id,
)
from src.agents.workflow import SentinelWorkflow
from src.utils.report_exporter import export_sar_to_markdown

# Page configuration
st.set_page_config(
    page_title="Db2 Sentinel AI - AML Surveillance Suite",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern enterprise financial aesthetic
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #0F62FE;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #525252;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #f4f7fb;
        border-radius: 8px;
        padding: 15px;
        border-left: 5px solid #0F62FE;
    }
    .badge-live {
        background-color: #24A148;
        color: white;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .badge-emulated {
        background-color: #F1C21B;
        color: #161616;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .risk-high {
        color: #DA1E28;
        font-weight: bold;
    }
    .risk-medium {
        color: #FF832B;
        font-weight: bold;
    }
    .risk-low {
        color: #24A148;
        font-weight: bold;
    }
</style>
""",
    unsafe_allow_html=True,
)

# Initialize DB and seed data
initialize_schema()
seed_database()
db = get_db_manager()

# Sidebar: System Controls & Demo Cases
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg", width=120)
    st.markdown("### **Db2 Sentinel AI**")
    st.markdown("*Autonomous AML & Financial Intelligence*")
    st.divider()

    # Database Status Indicator
    if db.active_mode == "live":
        st.markdown('<span class="badge-live">● IBM Db2 12.1+ Live Engine</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="badge-emulated">● Db2 High-Fidelity Local Engine</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### **Select Surveillance Target**")
    tx_list = get_all_transactions()
    tx_options = {
        f"{t['TX_ID']} | ${float(t['AMOUNT']):,.0f} | {t['SENDER_ID']} -> {t['RECEIVER_ID']}": t["TX_ID"]
        for t in tx_list
    }
    selected_label = st.selectbox("Transaction Stream", list(tx_options.keys()), index=0)
    selected_tx_id = tx_options[selected_label]

    st.markdown("#### **Preloaded Test Cases**")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("Case 1: Smurfing", use_container_width=True):
            selected_tx_id = "TX-STRUCT-01"
    with col_c2:
        if st.button("Case 2: Circular", use_container_width=True):
            selected_tx_id = "TX-LOOP-01"

    if st.button("Case 3: Sanctions Front", use_container_width=True):
        selected_tx_id = "TX-SANCT-01"

    st.markdown("---")
    investigate_btn = st.button("🚀 Run Multi-Agent Investigation", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("##### **System Architecture Info**")
    st.caption("• **Db2 Vector Search:** Native 384-dim COSINE distance")
    st.caption("• **Db2 SQL CTEs:** Recursive multi-hop cycle tracing")
    st.caption("• **Db2 State Checkpoint:** LangGraph step persistence")
    st.caption("• **Db2 Audit Ledger:** SHA-256 signed tamper-proof trail")

# Top Header Banner
col_title, col_stat = st.columns([3, 1])
with col_title:
    st.markdown('<div class="main-header">Db2 Sentinel AI</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Autonomous Financial Crime Surveillance & Regulatory Compliance Platform powered by IBM Db2</div>',
        unsafe_allow_html=True,
    )
with col_stat:
    st.metric(label="Active Watched Entities", value="8 Accounts", delta="3 High Risk")

# Key KPI Dashboard Cards
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
all_txs = get_all_transactions()
total_vol = sum(float(t["AMOUNT"]) for t in all_txs)
pending_alts = get_pending_alerts()
accounts = get_all_accounts()
frozen_cnt = sum(1 for a in accounts if a.get("STATUS") == "FROZEN")

with kpi1:
    st.metric("Total Monitored Volume", f"${total_vol:,.2f} USD")
with kpi2:
    st.metric("Transactions Intercepted", f"{len(all_txs)} Wires")
with kpi3:
    st.metric("Pending AML Alerts", f"{len(pending_alts)} Cases", delta=f"{len(pending_alts)} Actionable", delta_color="inverse")
with kpi4:
    st.metric("Accounts Frozen (Db2)", f"{frozen_cnt} Entities", delta="Enforced", delta_color="normal")

st.markdown("---")

# Main Multi-Tab Interface
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Transaction Feed & Alerts",
    "🤖 Multi-Agent Investigation Canvas",
    "🕸️ Transaction Network Topology",
    "📄 Regulatory SAR Studio & Audit Log",
    "🔍 Text-to-SQL & Hybrid Vector Explorer",
])

# TAB 1: Transaction Feed & Alerts
with tab1:
    st.markdown("### **Real-Time Financial Transaction Ledger (IBM Db2)**")
    df_txs = pd.DataFrame(all_txs)
    if not df_txs.empty:
        display_df = df_txs[[
            "TX_ID", "SENDER_NAME", "RECEIVER_NAME", "AMOUNT", "CURRENCY", "CHANNEL", "TX_TIMESTAMP", "MEMO", "FLAG_ANOMALY"
        ]].copy()
        display_df["AMOUNT"] = display_df["AMOUNT"].apply(lambda x: f"${float(x):,.2f}")
        display_df["FLAG_ANOMALY"] = display_df["FLAG_ANOMALY"].apply(lambda x: "🚨 Suspicious" if x == 1 else "✅ Normal")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    col_acc, col_alts = st.columns(2)
    with col_acc:
        st.markdown("#### **Monitored Accounts Registry**")
        df_acc = pd.DataFrame(accounts)
        if not df_acc.empty:
            acc_view = df_acc[["ACCOUNT_ID", "CUSTOMER_NAME", "ACCOUNT_TYPE", "JURISDICTION", "BALANCE", "RISK_RATING", "STATUS"]].copy()
            acc_view["BALANCE"] = acc_view["BALANCE"].apply(lambda x: f"${float(x):,.2f}")
            st.dataframe(acc_view, use_container_width=True, hide_index=True)
    with col_alts:
        st.markdown("#### **Pending Alert Queue**")
        df_alts = pd.DataFrame(pending_alts)
        if not df_alts.empty:
            alt_view = df_alts[["ALERT_ID", "TX_ID", "RISK_SCORE", "RULE_TRIGGERED", "STATUS"]].copy()
            st.dataframe(alt_view, use_container_width=True, hide_index=True)

# TAB 2: Multi-Agent Investigation Canvas
with tab2:
    st.markdown("### **Autonomous Multi-Agent Investigation Workflow**")
    st.markdown("*Orchestrated via LangGraph with checkpoints persisted directly into IBM Db2.*")

    target_tx = get_transaction_by_id(selected_tx_id)
    if target_tx:
        col_t1, col_t2, col_t3 = st.columns(3)
        with col_t1:
            st.info(f"**Target Wire:** `{target_tx['TX_ID']}`\n\n**Amount:** `${float(target_tx['AMOUNT']):,.2f} {target_tx['CURRENCY']}`")
        with col_t2:
            st.info(f"**Origin:** {target_tx['SENDER_NAME']} (`{target_tx['SENDER_ID']}`)\n\n**Jurisdiction:** {target_tx['SENDER_JURISDICTION']}")
        with col_t3:
            st.info(f"**Beneficiary:** {target_tx['RECEIVER_NAME']} (`{target_tx['RECEIVER_ID']}`)\n\n**Memo:** \"{target_tx['MEMO']}\"")

    if investigate_btn or "investigation_result" not in st.session_state:
        with st.spinner("Executing LangGraph multi-agent forensic pipeline in IBM Db2..."):
            workflow = SentinelWorkflow()
            st.session_state["investigation_result"] = workflow.run_investigation(selected_tx_id, auto_approve=True)

    result = st.session_state.get("investigation_result")
    if result:
        st.markdown("---")
        score = result["risk_score"]

        # Risk Meter
        col_gauge, col_rec = st.columns([1, 2])
        with col_gauge:
            st.markdown(f"#### **Calculated Risk Score: `{score} / 100`**")
            st.progress(score / 100.0)
            if score >= 85:
                st.error("🚨 **CRITICAL RISK DETECTED** - Statutory Intervention Required")
            elif score >= 65:
                st.warning("⚠️ **ELEVATED RISK** - Enhanced Due Diligence / SAR Recommended")
            else:
                st.success("✅ **LOW RISK PROFILE** - Routine Transaction Verified")

        with col_rec:
            st.markdown(f"#### **Supervisor Action: `{result['supervisor_decision']}`**")
            st.write(f"**Recommendation:** `{result['recommended_action']}`")
            st.write(f"**Action Details:** {result['supervisor_notes']}")
            st.code(f"Db2 Cryptographic Audit Signature: {result['audit_signature']}", language="text")

        st.markdown("#### **Agent Step-by-Step Execution Trace (Db2 LangGraph Checkpoints)**")
        for i, log in enumerate(result["agent_logs"]):
            with st.expander(f"Step {i+1}: {log['agent']} ({log['timestamp'][11:19]} UTC)", expanded=True):
                st.markdown(f"**Finding / Operation:** {log['message']}")

        # Forensic Deep-Dive Expanders
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown("##### **Db2 Native Vector Typology Matches**")
            if result["matched_typologies"]:
                for t in result["matched_typologies"]:
                    st.write(f"• **{t['TITLE']}** ({t['CATEGORY']})")
                    st.caption(f"Cosine Similarity: `{t.get('SIMILARITY', 0):.2f}` | Red Flags: {t['RED_FLAGS']}")
            else:
                st.caption("No semantic typologies matched above similarity threshold.")

        with col_f2:
            st.markdown("##### **Db2 Network Cycles & Structuring**")
            if result["circular_loops"]:
                st.error(f"🚨 **Circular Loop Detected:** {result['circular_loops'][0]['full_loop']}")
            else:
                st.caption("No closed circular routing loops identified.")

            st_ev = result.get("structuring_evidence", {})
            if st_ev.get("is_structuring_suspect"):
                st.warning(f"⚠️ **Structuring Cluster:** {st_ev.get('sub_threshold_count')} sub-threshold wires in window.")

# TAB 3: Network Topology
with tab3:
    st.markdown("### **Interactive Money Flow & Entity Graph**")
    st.caption("Visualizes fund routing across accounts in IBM Db2. Circular loops and high-risk entities highlighted.")

    G = nx.DiGraph()
    for acc in accounts:
        G.add_node(acc["ACCOUNT_ID"], label=acc["CUSTOMER_NAME"], risk=acc["RISK_RATING"])

    for tx in all_txs:
        G.add_edge(tx["SENDER_ID"], tx["RECEIVER_ID"], amount=float(tx["AMOUNT"]), memo=tx["MEMO"])

    # Summary table of edges
    edge_data = []
    for u, v, d in G.edges(data=True):
        edge_data.append({
            "From Account": u,
            "To Account": v,
            "Transfer Amount": f"${d['amount']:,.2f}",
            "Transaction Memo": d.get("memo", "")
        })
    st.dataframe(pd.DataFrame(edge_data), use_container_width=True)

    if result and result.get("circular_loops"):
        st.error(f"**Identified Laundering Cycle:** `{result['circular_loops'][0]['full_loop']}`")

# TAB 4: Regulatory SAR Studio & Audit Log
with tab4:
    st.markdown("### **Official Suspicious Activity Report (SAR) Studio**")
    st.caption("Automated statutory compliance filings generated to FinCEN / RBI specifications.")

    if result and result.get("sar_narrative"):
        st.text_area("Regulatory Narrative Filing (FinCEN / RBI Format)", result["sar_narrative"], height=380)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                label="📥 Download Official SAR (Markdown)",
                data=result["sar_narrative"],
                file_name=f"SAR_Filing_{result['tx_id']}.md",
                mime="text/markdown",
            )
    else:
        st.info("Run an investigation to generate the official SAR filing.")

    st.markdown("---")
    st.markdown("### **Immutable IBM Db2 Cryptographic Audit Trail**")
    st.caption("Every agent decision, query, and supervisor sign-off is logged with SHA-256 integrity hashes.")

    audit_records = get_recent_audit_trail(limit=15)
    if audit_records:
        df_audit = pd.DataFrame(audit_records)
        st.dataframe(df_audit, use_container_width=True, hide_index=True)

# TAB 5: Text-to-SQL Explorer
with tab5:
    st.markdown("### **Text-to-SQL & Hybrid Vector Explorer for IBM Db2**")
    st.caption("Ask natural language queries or execute custom SQL against IBM Db2 ledgers.")

    query_presets = [
        "SELECT * FROM ACCOUNTS WHERE RISK_RATING = 'HIGH'",
        "SELECT * FROM TRANSACTIONS WHERE AMOUNT > 9000 AND AMOUNT < 10000",
        "SELECT * FROM SANCTIONS_WATCHLIST",
        "SELECT TYPOLOGY_ID, CODE, TITLE, CATEGORY FROM AML_TYPOLOGIES",
        "SELECT * FROM AUDIT_TRAIL ORDER BY AUDIT_ID DESC",
    ]
    selected_query = st.selectbox("Preset Analytical Db2 Queries", query_presets)
    custom_sql = st.text_area("SQL Statement", selected_query, height=80)

    if st.button("Execute Query on Db2"):
        try:
            res = db.execute_query(custom_sql)
            st.success(f"Query returned {len(res)} row(s).")
            if res:
                st.dataframe(pd.DataFrame(res), use_container_width=True)
        except Exception as e:
            st.error(f"SQL Execution Error: {e}")
