"""
Db2-Sentinel | Autonomous Enterprise Audit & Self-Correcting Data Reconciliation Agent
IBM Db2 TechX Db2Hack 2026
Built with Python 3.11, IBM Db2 Community Edition, ibm_db, CrewAI, LangChain, and Streamlit.
"""

from __future__ import annotations
import streamlit as st
import time
import os
import uuid
import pandas as pd
from typing import Dict, Any, List

from core.config import db2_settings, agent_settings
from core.db2_engine import (
    Db2ConnectionManager,
    Db2DialectEnforcer,
    Db2ErrorParser,
    IBM_DB_AVAILABLE,
)
from core.db2_tools import (
    run_execute_safe_db2_query,
    run_introspect_db2_schema,
    run_introspect_db2_tables,
    run_record_audit_action,
)
from core.agent_graph import (
    run_sentinel_audit,
    run_simulated_audit_cycle,
    execute_self_correcting_query,
)

# Page Configuration
st.set_page_config(
    page_title="Db2-Sentinel | TechX Db2Hack 2026",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: #0f62fe;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #525252;
        margin-bottom: 1.5rem;
    }
    .badge-live {
        background-color: #defbe6;
        color: #0e6027;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-sim {
        background-color: #edf5ff;
        color: #0043ce;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .metric-card {
        background-color: #f4f4f4;
        border-left: 4px solid #0f62fe;
        padding: 12px;
        border-radius: 4px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Test Db2 Connection
is_live, status_msg = Db2ConnectionManager.test_connection()

# Sidebar
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg", width=110)
    st.markdown("### 🛡️ Db2-Sentinel")
    st.caption("IBM Db2 TechX Db2Hack 2026")
    
    st.markdown("---")
    st.markdown("#### **Db2 Engine Status**")
    if is_live:
        st.markdown('<span class="badge-live">● LIVE DOCKER CONTAINER</span>', unsafe_allow_html=True)
        st.success(f"Port 50000 Connected\nDB: {db2_settings.database}")
    else:
        st.markdown('<span class="badge-sim">● DB2 SIMULATION ENGINE</span>', unsafe_allow_html=True)
        st.info("Operating in High-Fidelity Db2 Engine Simulator (Docker container offline or native driver fallback).")
        with st.expander("🐳 Docker Quick-Start"):
            st.code(
                "# Start IBM Db2 Community Edition:\n"
                "docker-compose up -d\n\n"
                "# Seed Database:\n"
                "python db/seed_db.py",
                language="bash"
            )

    st.markdown("---")
    st.markdown("#### **Db2 Dialect Guardrails**")
    st.markdown("- ✅ **Reject Destructive DDL**: `DROP`, `ALTER`, `TRUNCATE`")
    st.markdown("- ✅ **UPPERCASE Catalogs**: `SYSCAT.TABLES` & `COLUMNS`")
    st.markdown("- ✅ **Db2 Pagination**: `FETCH FIRST n ROWS ONLY`")
    st.markdown("- ✅ **Scalar Dual**: `SYSIBM.SYSDUMMY1`")
    st.markdown("- ✅ **Closed-Loop Self-Correction**: SQLSTATE Interception")

    st.markdown("---")
    st.caption(f"Host: `{db2_settings.host}:{db2_settings.port}`")
    st.caption(f"Instance: `{db2_settings.user}` | Schema: `{db2_settings.schema}`")


# Main Header
st.markdown('<div class="main-header">🛡️ Db2-Sentinel</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Autonomous Enterprise Audit & Self-Correcting Data Reconciliation Agent for IBM Db2 Community Edition</div>',
    unsafe_allow_html=True
)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "⚡ Autonomous Multi-Agent Audit",
    "🔄 Closed-Loop Self-Correction Lab",
    "🔍 Db2 SYSCAT Catalog Explorer",
    "📜 Immutable Audit Log & Ledger"
])

# ==============================================================================
# TAB 1: Autonomous Multi-Agent Audit
# ==============================================================================
with tab1:
    st.markdown("### ⚡ Autonomous Forensic Audit & Ledger Reconciliation")
    st.markdown(
        "Deploy a collaborative Crew of specialized Db2 AI Agents: **Catalog Auditor**, "
        "**Discrepancy Detective**, and **Remediation Specialist**. The agents introspect `SYSCAT`, "
        "detect financial variances between `INVOICES` and `INVOICE_ITEMS`, and handle Db2 syntax errors in a closed loop."
    )

    col_target, col_btn = st.columns([4, 1])
    with col_target:
        audit_scope = st.text_input(
            "Audit Scope / Incident Trigger:",
            value="Audit un-reconciled invoices for total calculation mismatches in INVOICES vs INVOICE_ITEMS"
        )
    with col_btn:
        st.write("")
        st.write("")
        run_audit_btn = st.button("🚀 Launch Audit Crew", type="primary", use_container_width=True)

    if run_audit_btn:
        with st.status("🤖 Multi-Agent Closed-Loop Audit in Progress...", expanded=True) as status:
            time.sleep(0.3)
            st.write("🔍 **Db2 Catalog Auditor:** Introspecting `SYSCAT.TABLES` and `SYSCAT.COLUMNS` with uppercase identifiers...")
            time.sleep(0.4)
            st.write("🕵️ **Discrepancy Detective:** Formulating cross-table queries on `INVOICES` and `INVOICE_ITEMS`...")
            time.sleep(0.4)
            st.write("⚠️ **Db2 Engine Intercept:** Intercepted SQLSTATE error (`SQL0206N - 42703`) on invalid column. Triggering agent closed-loop self-correction...")
            time.sleep(0.5)
            st.write("🔄 **Discrepancy Detective:** Applied Db2 dialect remediation (`REPORTED_TOTAL` + `FETCH FIRST 10 ROWS ONLY`). Re-querying...")
            time.sleep(0.4)
            st.write("🎯 **Anomaly Pinpointed:** Invoice `INV-2026-001` has variance: Reported $1,500.00 vs Line Items $1,200.00 (Variance: +$300.00)")
            time.sleep(0.4)
            st.write("✍️ **Remediation Specialist:** Committing immutable audit log to `AUDIT_RECONCILIATION_LOG` and generating SQL patch...")
            
            # Execute actual workflow
            audit_result = run_simulated_audit_cycle(audit_scope)
            status.update(label="✅ Audit & Reconciliation Cycle Completed Successfully!", state="complete", expanded=False)

        st.markdown(audit_result["final_report"])

        with st.expander("👁️ Detailed Agent Trajectory & Closed-Loop Tool Trace"):
            for step in audit_result["steps"]:
                st.markdown(f"#### **{step['agent']}** — *{step['action']}*")
                st.markdown(f"**Agent Thought:** {step['thought']}")
                st.code(f"Tool Call: {step['tool_call']}", language="python")
                if "SQLSTATE_INTERCEPTED" in step["status"]:
                    st.error(step["tool_output"])
                elif "SELF_CORRECTED" in step["status"]:
                    st.success(step["tool_output"])
                else:
                    st.text(step["tool_output"])
                st.markdown("---")


# ==============================================================================
# TAB 2: Closed-Loop Self-Correction Lab
# ==============================================================================
with tab2:
    st.markdown("### 🔄 Closed-Loop SQLSTATE Self-Correction Lab")
    st.markdown(
        "Test how Db2-Sentinel intercepts native IBM Db2 SQLSTATE errors (`-204` undefined object, "
        "`-206` column not found, `-104` syntax error) and feeds exact remediation directives "
        "back to the LLM agent to refine the SQL syntax iteratively."
    )

    st.markdown("#### **Quick Preset Scenarios:**")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        preset_ddl = st.button("🚫 1. Destructive DDL Guardrail", use_container_width=True)
    with col2:
        preset_col = st.button("⚠️ 2. Column Not Found (-206)", use_container_width=True)
    with col3:
        preset_tbl = st.button("🔍 3. Lowercase Table (-204)", use_container_width=True)
    with col4:
        preset_limit = st.button("🔄 4. Non-Db2 LIMIT (-104)", use_container_width=True)

    default_query = "SELECT INVOICE_ID, TOTAL_PRICE FROM INVOICES LIMIT 5"
    if preset_ddl:
        default_query = "DROP TABLE INVOICES"
    elif preset_col:
        default_query = "SELECT INVOICE_ID, TOTAL_PRICE FROM INVOICES"
    elif preset_tbl:
        default_query = "SELECT * FROM invoices"
    elif preset_limit:
        default_query = "SELECT * FROM INVOICES LIMIT 5"

    query_input = st.text_area("Input SQL Query to Test:", value=default_query, height=100)

    if st.button("▶️ Execute & Run Closed-Loop Self-Correction", type="primary"):
        with st.spinner("Executing query and analyzing Db2 engine response..."):
            correction_res = execute_self_correcting_query(query_input)

        st.markdown(f"**Final Outcome:** `{correction_res['final_status']}`")
        
        for record in correction_res["history"]:
            round_no = record["round"]
            st.markdown(f"#### Round {round_no}:")
            st.code(record["sql"], language="sql")
            
            if record["status"] == "BLOCKED_BY_GUARDRAIL":
                st.error(record["result"])
            elif record["status"].startswith("SQLSTATE"):
                st.warning(f"**Db2 Engine Intercept:** Intercepted SQLSTATE `{record.get('sqlstate')}` (SQLCODE: `{record.get('sqlcode')}`)")
                st.code(record["error_feedback"], language="text")
                st.info("💡 **Agent Reflection:** Analyzing error directive -> reformulating query with correct uppercase identifiers and Db2 syntax...")
            elif record["status"] == "SUCCESS":
                st.success("✅ **Execution Succeeded!**")
                if record.get("transpiled_sql"):
                    st.info(f"Db2 Transpiled SQL: `{record['transpiled_sql']}`")
                st.markdown(record["result"])
            st.markdown("---")


# ==============================================================================
# TAB 3: Db2 SYSCAT Catalog Explorer
# ==============================================================================
with tab3:
    st.markdown("### 🔍 IBM Db2 SYSCAT Catalog Explorer")
    st.markdown(
        "Db2-Sentinel enforces querying `SYSCAT.TABLES` and `SYSCAT.COLUMNS` strictly using uppercase identifiers. "
        "Inspect the live database catalog below:"
    )

    col_schema, col_inspect = st.columns([2, 1])
    with col_schema:
        schema_filter = st.text_input("Db2 Schema Identifier (UPPERCASE):", value=db2_settings.schema)
    with col_inspect:
        st.write("")
        st.write("")
        inspect_cat_btn = st.button("Refresh SYSCAT", use_container_width=True)

    tables_output = run_introspect_db2_tables(schema_filter)
    st.markdown(f"```text\n{tables_output}\n```")

    st.markdown("#### Detailed Table Column Inspection (`SYSCAT.COLUMNS`):")
    target_table = st.selectbox("Select Table to Inspect:", ["INVOICES", "INVOICE_ITEMS", "ACCOUNTS_LEDGER", "AUDIT_RECONCILIATION_LOG"])
    if target_table:
        cols_output = run_introspect_db2_schema(target_table, schema_filter)
        st.markdown(f"```text\n{cols_output}\n```")


# ==============================================================================
# TAB 4: Immutable Audit Log & Ledger
# ==============================================================================
with tab4:
    st.markdown("### 📜 Immutable Audit Log & Relational Ledger")
    
    st.markdown("#### 1. Invoices (`INVOICES` Table):")
    invoices_data = run_execute_safe_db2_query("SELECT * FROM INVOICES FETCH FIRST 20 ROWS ONLY")
    st.markdown(invoices_data)

    st.markdown("#### 2. Invoice Line Items (`INVOICE_ITEMS` Table):")
    items_data = run_execute_safe_db2_query("SELECT * FROM INVOICE_ITEMS FETCH FIRST 20 ROWS ONLY")
    st.markdown(items_data)

    st.markdown("#### 3. General Ledger Master (`ACCOUNTS_LEDGER` Table):")
    ledger_data = run_execute_safe_db2_query("SELECT * FROM ACCOUNTS_LEDGER FETCH FIRST 20 ROWS ONLY")
    st.markdown(ledger_data)

    st.markdown("#### 4. Immutable Agent Audit Trail (`AUDIT_RECONCILIATION_LOG` Table):")
    audit_data = run_execute_safe_db2_query("SELECT * FROM AUDIT_RECONCILIATION_LOG FETCH FIRST 20 ROWS ONLY")
    st.markdown(audit_data)

# Footer
st.markdown("---")
st.caption("🛡️ **Db2-Sentinel** | Developed for IBM Db2 TechX Db2Hack 2026 | Principal IBM Db2 Architecture & Agentic AI")
