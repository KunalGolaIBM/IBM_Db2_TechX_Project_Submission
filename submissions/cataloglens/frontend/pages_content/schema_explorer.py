"""
Schema Explorer Page.
Allows developers to inspect database tables, views, columns,
data types, nullability, primary keys, foreign keys, constraints, and indexes.
"""
import streamlit as st
import pandas as pd
from ..api_client import CatalogLensAPIClient


def show_schema_explorer_page(api: CatalogLensAPIClient):
    st.markdown("## 🗃️ Db2 Schema Explorer")
    st.markdown("Browse normalized database catalog objects, inspect table definitions, and view declared constraints.")

    use_demo = st.session_state.get("use_demo", True)
    schema_name = st.session_state.get("active_schema", "ENTERPRISE")

    meta = api.get_metadata(schema_name=schema_name, use_demo=use_demo)
    tables = meta.get("tables", {})
    views = meta.get("views", {})

    all_objects = sorted(list(tables.keys()) + list(views.keys()))
    if not all_objects:
        st.warning("No objects found in the active schema.")
        return

    # Object Selector
    col_sel, col_type = st.columns([3, 1])
    with col_sel:
        selected_obj_name = st.selectbox("Select Table or View to Inspect:", all_objects, index=0)

    is_view = selected_obj_name in views
    with col_type:
        st.markdown(f"**Object Type:** `{'VIEW' if is_view else 'TABLE'}`")

    target_obj = views.get(selected_obj_name) if is_view else tables.get(selected_obj_name)

    st.divider()

    # Table Header & Remarks
    col_info, col_stats = st.columns([3, 1])
    with col_info:
        st.markdown(f"### `{selected_obj_name}`")
        if target_obj.get("remarks"):
            st.info(f"**Catalog Description (REMARKS):** {target_obj.get('remarks')}")
        else:
            st.caption("No description found in SYSCAT.TABLES REMARKS.")
    with col_stats:
        card = target_obj.get("card", -1)
        st.metric("Approx. Rows (CARD)", f"{card:,}" if card >= 0 else "N/A")
        st.metric("Total Columns", len(target_obj.get("columns", [])))

    # Tabs for Structural Inspection
    tab_cols, tab_pks, tab_fks, tab_idx, tab_view = st.tabs([
        "Columns & Types",
        "Primary Keys & Constraints",
        "Foreign Keys (Declared)",
        "Indexes",
        "View SQL Definition" if is_view else "Overview",
    ])

    with tab_cols:
        col_rows = []
        for c in target_obj.get("columns", []):
            pk_str = "🔑 PRIMARY KEY" if c.get("is_primary_key") else ""
            fk_str = f"🔗 FK &rarr; {c.get('foreign_key_target')}" if c.get("is_foreign_key") else ""
            scale_val = c.get("scale", 0) or 0
            scale_str = f",{scale_val}" if scale_val > 0 else ""
            type_str = f"{c.get('typename')}({c.get('length')}{scale_str})"
            col_rows.append({
                "Col #": c.get("colno"),
                "Column Name": c.get("colname"),
                "Data Type": type_str,
                "Nullable": "YES" if c.get("nulls") == "Y" else "NO",
                "Default": c.get("default_val") or "",
                "Key Role": pk_str or fk_str or "Standard Column",
                "Description (REMARKS)": c.get("remarks") or "",
            })
        df_cols = pd.DataFrame(col_rows)
        st.dataframe(df_cols, use_container_width=True, hide_index=True)

    with tab_pks:
        pks = target_obj.get("primary_keys", [])
        constraints = target_obj.get("constraints", [])
        if pks:
            st.success(f"**Primary Key Columns:** `{'`, `'.join(pks)}`")
        else:
            st.info("No primary key declared on this object.")

        if constraints:
            st.markdown("#### Table Constraints (SYSCAT.TABCONST)")
            c_rows = []
            for ct in constraints:
                c_rows.append({
                    "Constraint Name": ct.get("constname"),
                    "Type": "Primary Key (P)" if ct.get("const_type") == "P" else ("Check Constraint (K)" if ct.get("const_type") == "K" else ct.get("const_type")),
                    "Columns": ", ".join(ct.get("columns", [])),
                    "Referenced Table": ct.get("ref_table") or "-",
                })
            st.dataframe(pd.DataFrame(c_rows), use_container_width=True, hide_index=True)

    with tab_fks:
        fks = target_obj.get("foreign_keys", [])
        if fks:
            st.markdown(f"Found **{len(fks)}** declared foreign key constraints:")
            fk_rows = []
            for f in fks:
                fk_rows.append({
                    "Constraint Name": f.get("constraint_name"),
                    "Source Column": f.get("source_column"),
                    "Target Table": f.get("target_table"),
                    "Target Column": f.get("target_column"),
                    "On Delete": f.get("delete_rule"),
                    "On Update": f.get("update_rule"),
                })
            st.dataframe(pd.DataFrame(fk_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No explicit foreign keys declared in SYSCAT.REFERENCES for this table. (Check the 'Relationship Intelligence' tab to discover inferred relationships!)")

    with tab_idx:
        idxs = target_obj.get("indexes", [])
        if idxs:
            idx_rows = []
            for i in idxs:
                idx_rows.append({
                    "Index Name": i.get("indname"),
                    "Unique Rule": "Unique (U)" if i.get("uniquerule") == "U" else ("Primary (P)" if i.get("uniquerule") == "P" else "Duplicates Allowed (D)"),
                    "Indexed Columns": i.get("colnames"),
                })
            st.dataframe(pd.DataFrame(idx_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No indexes found in SYSCAT.INDEXES.")

    with tab_view:
        if is_view:
            v_sql = target_obj.get("view_definition") or "-- No view definition retrieved from SYSCAT.VIEWS"
            st.code(v_sql, language="sql")
        else:
            st.markdown(f"**Table Name:** `{selected_obj_name}`")
            st.markdown(f"**Schema:** `{schema_name}`")
            st.markdown(f"**Db2 Object Type:** `T (TABLE)`")
