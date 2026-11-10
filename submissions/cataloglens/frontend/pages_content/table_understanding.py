"""
AI Table Understanding Page.
Executes the agentic LangGraph investigation pipeline to explain
table business purpose, column significance, workflow roles, and evidence.
"""
import streamlit as st
import pandas as pd
from ..api_client import CatalogLensAPIClient
from ..components.evidence_view import render_evidence_ledger


def show_table_understanding_page(api: CatalogLensAPIClient):
    st.markdown("## 🧠 AI Table Understanding")
    st.markdown("Select any table and trigger an agentic LangGraph investigation to discover its business purpose, column significance, and supporting evidence.")

    use_demo = st.session_state.get("use_demo", True)
    schema_name = st.session_state.get("active_schema", "ENTERPRISE")

    meta = api.get_metadata(schema_name=schema_name, use_demo=use_demo)
    table_names = sorted(list(meta.get("tables", {}).keys()))

    if not table_names:
        st.warning("No tables available in the active schema.")
        return

    # Selectors
    col_t, col_q = st.columns([1, 2])
    with col_t:
        selected_table = st.selectbox("Select Table to Investigate:", table_names, index=table_names.index("RETURN_HDR") if "RETURN_HDR" in table_names else 0)
    with col_q:
        question = st.text_input(
            "Optional Investigation Question:",
            value="What business process does this table belong to and what are its key relationships?",
        )

    run_btn = st.button("🚀 Run Agentic Investigation Pipeline", type="primary")

    # Cache key in session state
    report_key = f"investigation_report_{schema_name}_{selected_table}"

    if run_btn:
        progress_bar = st.progress(0, text="Initializing LangGraph Investigation Pipeline...")

        progress_bar.progress(20, text="Node 1/6: MetadataRetriever — Pulling SYSCAT tables, columns, constraints...")
        progress_bar.progress(40, text="Node 2/6: SchemaAnalyzer — Extracting column metrics and ground truth...")
        progress_bar.progress(60, text="Node 3/6: RelationshipInvestigator — Discovering declared & inferred edges...")
        progress_bar.progress(75, text="Node 4/6: Reasoning Engine — Formulating business hypotheses...")
        progress_bar.progress(90, text="Node 5/6: EvidenceValidator — Programmatically validating claims...")

        report = api.analyze_table(
            table_name=selected_table,
            schema_name=schema_name,
            question=question,
            use_demo=use_demo,
        )

        progress_bar.progress(100, text="Node 6/6: ReportGenerator — Investigation Complete!")
        st.session_state[report_key] = report

    report = st.session_state.get(report_key)

    if report:
        st.divider()
        st.success(f"✅ Investigation Report Ready for **`{selected_table}`**")

        tu = report.get("table_understanding") or {}

        # AI Engine Metadata
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.caption(f"Engine Model: **{tu.get('model_used', 'Deterministic heuristic fallback')}**")
        with col_m2:
            st.caption(f"Verified Evidence Claims: **{report.get('total_evidence_claims', 0)}**")
        with col_m3:
            st.caption(f"Referenced Relationships: **{report.get('relevant_relationships_count', 0)}**")

        # 1. Likely Business Purpose
        st.markdown("### 🏢 Likely Business Purpose")
        st.markdown(
            f"""
            <div style="border-left: 4px solid #0F62FE; padding: 12px 16px; background: rgba(15, 98, 254, 0.08); border-radius: 4px; font-size: 16px; line-height: 1.5;">
                {tu.get('likely_business_purpose')}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### 🔄 Likely Business Workflow")
        st.info(tu.get("likely_business_workflow", "Enterprise Order Management"))

        # 2. Important Columns
        st.markdown("### 📌 Column Significance Breakdown")
        cols_data = []
        for c in tu.get("important_columns", []):
            cols_data.append({
                "Column Name": c.get("column_name"),
                "Significance": c.get("significance"),
                "Business Role Description": c.get("role_description"),
            })
        st.dataframe(pd.DataFrame(cols_data), use_container_width=True, hide_index=True)

        # 3. Relationships Summary
        st.markdown("### 🔗 Relationships Summary")
        for r_sum in tu.get("relationships_summary", []):
            st.markdown(f"- {r_sum}")

        # 4. Evidence Ledger
        st.markdown("### 🛡️ Evidence Ledger (Grounded Verification)")
        st.markdown("Every assertion below has been cross-referenced against the catalog metadata:")
        render_evidence_ledger(tu.get("evidence", []))

        # 5. Uncertainties & Verification Questions
        col_u, col_v = st.columns(2)
        with col_u:
            st.markdown("### ⚠️ Known Uncertainties")
            for u in tu.get("uncertainties", []):
                st.warning(u)
        with col_v:
            st.markdown("### ❓ Verification Questions for DB Architect")
            for q in tu.get("verification_questions", []):
                st.markdown(f"- *{q}*")
    else:
        st.info("👆 Click **'Run Agentic Investigation Pipeline'** above to generate an evidence-backed analysis of the selected table.")
