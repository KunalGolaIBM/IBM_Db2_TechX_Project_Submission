"""
Dependency Investigation Page.
Analyzes direct and indirect downstream impacts when modifying tables or columns.
"""
import streamlit as st
import pandas as pd
from ..api_client import CatalogLensAPIClient
from ..components.report_cards import render_severity_badge
from ..components.evidence_view import render_evidence_ledger


def show_dependency_investigation_page(api: CatalogLensAPIClient):
    st.markdown("## 🔍 Dependency Investigation")
    st.markdown("Investigate downstream impacts of altering a table or column. Traces declared foreign keys, inferred relationships, cascading dependencies, and dependent views.")

    use_demo = st.session_state.get("use_demo", True)
    schema_name = st.session_state.get("active_schema", "ENTERPRISE")

    meta = api.get_metadata(schema_name=schema_name, use_demo=use_demo)
    tables = meta.get("tables", {})
    views = meta.get("views", {})

    all_table_names = sorted(list(tables.keys()))
    if not all_table_names:
        st.warning("No tables available in the active schema.")
        return

    # Select target table and optional column
    col_t, col_c = st.columns([1, 1])
    with col_t:
        target_table = st.selectbox("Select Target Table:", all_table_names, index=all_table_names.index("ORD_HDR") if "ORD_HDR" in all_table_names else 0)
    with col_c:
        table_obj = tables.get(target_table, {})
        col_names = ["(Entire Table)"] + [c.get("colname") for c in table_obj.get("columns", [])]
        selected_col = st.selectbox("Select Specific Column (Optional):", col_names, index=0)

    target_query = target_table if selected_col == "(Entire Table)" else f"{target_table}.{selected_col}"

    investigate_btn = st.button("🔎 Run Dependency & Impact Trace", type="primary")

    cache_key = f"dep_investigation_{schema_name}_{target_query}"

    if investigate_btn:
        with st.spinner(f"Analyzing dependency graph and cascading references for '{target_query}'..."):
            result = api.investigate_dependencies(
                target_object=target_query,
                schema_name=schema_name,
                use_demo=use_demo,
            )
            st.session_state[cache_key] = result

    result = st.session_state.get(cache_key)

    if result:
        st.divider()

        # Severity Banner
        severity = result.get("impact_severity", "MEDIUM")
        st.markdown(
            f"""
            <div style="display:flex; justify-content:space-between; align-items:center; border: 1px solid #525252; padding: 14px 20px; border-radius: 8px; margin-bottom: 20px; background: rgba(255,255,255,0.02);">
                <div>
                    <h3 style="margin:0; font-size:20px;">Target Object: <code>{result.get('target_object')}</code></h3>
                    <div style="color:#A8A8A8; font-size:14px; margin-top:4px;">Object Type: <b>{result.get('object_type')}</b></div>
                </div>
                <div>
                    Impact Severity: {render_severity_badge(severity)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Impact Metrics
        c1, c2, c3 = st.columns(3)
        direct_deps = result.get("direct_dependencies", [])
        indirect_deps = result.get("indirect_dependencies", [])
        verified_rels = result.get("verified_relationships", [])
        with c1:
            st.metric("Direct Dependents", len(direct_deps), help="Immediate referencing tables/views")
        with c2:
            st.metric("Indirect Dependents", len(indirect_deps), help="Cascading downstream entities")
        with c3:
            st.metric("Active Foreign Keys", len(verified_rels))

        # 1. Direct Dependencies Table
        st.markdown("### 🎯 Direct Downstream Dependents")
        if direct_deps:
            d_rows = []
            for d in direct_deps:
                d_rows.append({
                    "Dependent Entity": d.get("entity"),
                    "Entity Type": d.get("entity_type"),
                    "Relationship Kind": d.get("relationship_kind"),
                    "Impact Level": d.get("impact_level"),
                    "Description": d.get("description"),
                })
            st.dataframe(pd.DataFrame(d_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No direct downstream dependents found.")

        # 2. Indirect Dependencies Table
        if indirect_deps:
            st.markdown("### 🌊 Indirect Cascading Dependents (Multi-hop)")
            i_rows = []
            for d in indirect_deps:
                i_rows.append({
                    "Cascading Entity": d.get("entity"),
                    "Entity Type": d.get("entity_type"),
                    "Impact Level": d.get("impact_level"),
                    "Description": d.get("description"),
                })
            st.dataframe(pd.DataFrame(i_rows), use_container_width=True, hide_index=True)

        # 3. Potential Impact Areas
        st.markdown("### ⚠️ Potential Impact Areas")
        for area in result.get("potential_impact_areas", []):
            st.warning(area)

        # 4. Recommended Manual Checks
        st.markdown("### 🛠️ Recommended Manual Checks Before Schema Change")
        for check in result.get("recommended_manual_checks", []):
            st.markdown(f"- [ ] {check}")

        # 5. Evidence Ledger
        st.markdown("### 🛡️ Supporting Evidence Ledger")
        render_evidence_ledger(result.get("evidence", []))
    else:
        st.info(f"👆 Click **'Run Dependency & Impact Trace'** above to trace dependencies for `{target_query}`.")
