"""
Business Workflow Discovery Page.
Identifies logical business processes from clusters of connected Db2 tables.
"""
import streamlit as st
from ..api_client import CatalogLensAPIClient


def show_workflow_discovery_page(api: CatalogLensAPIClient):
    st.markdown("## 🔄 Business Workflow Discovery")
    st.markdown("Detect high-level business lifecycles and transactions by analyzing clusters of interconnected Db2 tables.")

    use_demo = st.session_state.get("use_demo", True)
    schema_name = st.session_state.get("active_schema", "ENTERPRISE")

    workflows = api.analyze_workflows(schema_name=schema_name, use_demo=use_demo)

    if not workflows:
        st.warning("No workflows detected for the current schema.")
        return

    st.markdown(f"Detected **{len(workflows)}** active business workflows in schema `{schema_name}`:")

    for wf in workflows:
        conf = float(wf.get("confidence", 0.85))
        tables_list = wf.get("tables", [])

        with st.container():
            st.markdown(
                f"""
                <div style="border: 1px solid #393939; border-top: 4px solid #0F62FE; padding: 18px 20px; border-radius: 8px; margin-bottom: 20px; background: rgba(255,255,255,0.01);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <h3 style="margin:0; font-size:20px;">{wf.get('name')}</h3>
                        <span style="background-color:#0043CE; color:white; padding:4px 10px; border-radius:12px; font-weight:600; font-size:13px;">Confidence: {conf*100:.0f}%</span>
                    </div>
                    <p style="color:#C6C6C6; margin-top:8px; font-size:15px;">{wf.get('description')}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Sequence Steps
            col_seq, col_tables = st.columns([2, 1])
            with col_seq:
                st.markdown("#### 🪜 Business Lifecycle Progression")
                for step in wf.get("sequence_steps", []):
                    st.markdown(f"**{step}**")

            with col_tables:
                st.markdown("#### 📦 Participating Tables")
                for t in tables_list:
                    st.markdown(f"- `{t}`")

            # Supporting Relationships & Uncertainties Expander
            with st.expander("Inspect Supporting Relationships & Enterprise Uncertainties", expanded=False):
                st.markdown("##### Supporting Foreign Links:")
                for r in wf.get("supporting_relationships", []):
                    r_type = r.get("relationship_type")
                    st.markdown(f"- **{r.get('source_table')}.{r.get('source_column')}** &rarr; **{r.get('target_table')}.{r.get('target_column')}** `[{r_type}]`")

                st.markdown("##### Business Uncertainties:")
                for u in wf.get("uncertainties", []):
                    st.caption(f"⚠️ {u}")

            st.divider()
