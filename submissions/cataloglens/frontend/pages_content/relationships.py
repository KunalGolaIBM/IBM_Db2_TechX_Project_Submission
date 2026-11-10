"""
Relationship Intelligence Page.
Renders an interactive database relationship graph distinguishing
declared foreign keys (verified facts) from inferred relationships (hypotheses).
"""
import streamlit as st
import pandas as pd
from ..api_client import CatalogLensAPIClient
from ..components.graph_view import render_relationship_graph


def show_relationships_page(api: CatalogLensAPIClient):
    st.markdown("## 🕸️ Intelligent Relationship Discovery")
    st.markdown("Explore explicit database foreign keys alongside candidate inferred relationships detected via naming patterns and structural heuristics.")

    use_demo = st.session_state.get("use_demo", True)
    schema_name = st.session_state.get("active_schema", "ENTERPRISE")

    meta = api.get_metadata(schema_name=schema_name, use_demo=use_demo)
    tables = meta.get("tables", {})
    views = meta.get("views", {})
    relationships = api.get_relationships(schema_name=schema_name, use_demo=use_demo)

    # Filter Controls
    col_filter, col_highlight = st.columns([2, 2])
    with col_filter:
        rel_filter = st.selectbox(
            "Filter Relationships:",
            ["Show All (Declared + Inferred)", "Declared Only (Verified Facts)", "Inferred Only (Candidate Hypotheses)"],
            index=0,
        )
    with col_highlight:
        all_tables = sorted(list(tables.keys()) + list(views.keys()))
        highlight_sel = st.selectbox("Highlight Entity in Graph:", ["None"] + all_tables, index=0)

    filter_mode = "ALL"
    if "Declared Only" in rel_filter:
        filter_mode = "DECLARED_ONLY"
    elif "Inferred Only" in rel_filter:
        filter_mode = "INFERRED_ONLY"

    highlight_name = None if highlight_sel == "None" else highlight_sel

    # Render Interactive Graph
    fig = render_relationship_graph(
        tables=tables,
        views=views,
        relationships=relationships,
        filter_mode=filter_mode,
        highlight_table=highlight_name,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Metrics Summary
    total_decl = len([r for r in relationships if r.get("relationship_type") == "DECLARED"])
    total_inf = len([r for r in relationships if r.get("relationship_type") == "INFERRED"])

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Edges Displayed", len(relationships))
    with c2:
        st.metric("Declared (Verified Facts)", total_decl, help="From SYSCAT.REFERENCES")
    with c3:
        st.metric("Inferred (Hypotheses)", total_inf, help="Detected by heuristic engine")

    st.divider()

    # Detailed Relationships Table
    st.markdown("### 📋 Relationship Ledger")
    rel_rows = []
    for r in relationships:
        r_type = r.get("relationship_type")
        if filter_mode == "DECLARED_ONLY" and r_type != "DECLARED":
            continue
        if filter_mode == "INFERRED_ONLY" and r_type != "INFERRED":
            continue

        rel_rows.append({
            "Status": "✅ FACT" if r_type == "DECLARED" else "💡 INFERRED",
            "Source Table": r.get("source_table"),
            "Source Column": r.get("source_column"),
            "Target Table": r.get("target_table"),
            "Target Column": r.get("target_column"),
            "Confidence": f"{float(r.get('confidence', 1.0))*100:.0f}%",
            "Reason": r.get("reason"),
            "Verification Status": r.get("verification_status"),
        })

    df_rels = pd.DataFrame(rel_rows)
    st.dataframe(df_rels, use_container_width=True, hide_index=True)
