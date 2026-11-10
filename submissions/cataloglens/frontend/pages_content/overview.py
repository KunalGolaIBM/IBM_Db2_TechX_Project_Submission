"""
CatalogLens Overview Page.
"""
import streamlit as st
from ..api_client import CatalogLensAPIClient


def show_overview_page(api: CatalogLensAPIClient):
    st.markdown("## 🔍 CatalogLens")
    st.markdown("#### *Making the unknown structure of enterprise databases understandable.*")
    st.caption("An Agentic System for Understanding Undocumented Enterprise Databases | Built for IBM Db2 Ecosystem")

    st.markdown(
        """
        > **Core Philosophy:** *"Don't just ask AI to explain a database. Give AI the evidence needed to understand it."*
        > CatalogLens connects to IBM Db2 LUW catalogs, extracts verifiable structural facts, identifies hidden
        > undocumented relationships, and orchestrates a LangGraph investigation pipeline with deterministic reasoning and an optional Anthropic Claude integration — backing claims with a traceable Evidence Ledger.
        """
    )

    st.divider()

    # System Status & Health Metrics
    health = api.get_health()
    use_demo = st.session_state.get("use_demo", True)
    active_schema = st.session_state.get("active_schema", "ENTERPRISE")

    meta = api.get_metadata(schema_name=active_schema, use_demo=use_demo)
    rels = api.get_relationships(schema_name=active_schema, use_demo=use_demo)

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Database Mode", "Demo Enterprise" if use_demo else "Live Db2 LUW")
    with col2:
        st.metric("Total Tables", meta.get("total_tables", 0))
    with col3:
        st.metric("Total Views", meta.get("total_views", 0))
    with col4:
        decl = len([r for r in rels if r.get("relationship_type") == "DECLARED"])
        st.metric("Declared Relationships", decl, help="Formally defined in SYSCAT.REFERENCES")
    with col5:
        inf = len([r for r in rels if r.get("relationship_type") == "INFERRED"])
        st.metric("Inferred Relationships", inf, help="Discovered through naming and structural analysis")

    st.divider()

    # Core Value Pillars
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### 🏛️ Grounded in IBM Db2")
        st.markdown(
            """
            Queries real Db2 system catalogs:
            - `SYSCAT.TABLES` & `COLUMNS`
            - `SYSCAT.TABCONST` & `KEYCOLUSE`
            - `SYSCAT.REFERENCES` & `INDEXES`
            - `SYSCAT.VIEWS` & `TABDEP`

            Works side-by-side with the **Db2 Developer Extension for VS Code**.
            """
        )
    with c2:
        st.markdown("### 🕸️ Graph & Relationship Discovery")
        st.markdown(
            """
            Solves the enterprise undocumented database problem:
            - Separates **Verified Facts** from **AI Hypotheses**.
            - Discovers missing foreign keys and legacy reference patterns.
            - Computes confidence scores with type-compatibility verification.
            """
        )
    with c3:
        st.markdown("### 🧠 Agentic AI with LangGraph")
        st.markdown(
            """
            Multi-stage typed investigation pipeline:
            - **MetadataRetriever** &rarr; **SchemaAnalyzer**
            - **RelationshipInvestigator** &rarr; **Reasoning Engine**
            - **EvidenceValidator** &rarr; **ReportGenerator**

            Rejects hallucinations and validates all references programmatically.
            """
        )

    st.divider()

    # Enterprise Demonstration Database Guide
    with st.expander("📦 About the Synthetic Enterprise Order-Management Database", expanded=True):
        st.markdown(
            """
            CatalogLens includes a 13-table, 2-view synthetic enterprise order-management system representing a real-world enterprise database:
            - **Core Tables:** `CUSTOMER_MST`, `PRODUCT_MST`, `SUPPLIER_MST`, `WAREHOUSE_MST`, `ORD_HDR`, `ORD_LINE`, `INVENTORY`, `INVENTORY_RESERVATION`, `PAYMENT_METHOD`, `PAYMENT_TXN`, `SHIPMENT_HDR`, `SHIPMENT_ITEM`.
            - **Intentional Ambiguities:** `RETURN_HDR` has no explicit foreign key constraint to `ORD_HDR` in the catalog, and references customers via `CUST_REF_NO` instead of `CUST_ID` to demonstrate inferred relationship discovery!
            - **Reporting Views:** `V_ACTIVE_ORDERS` and `V_INVENTORY_VALUATION`.
            """
        )
