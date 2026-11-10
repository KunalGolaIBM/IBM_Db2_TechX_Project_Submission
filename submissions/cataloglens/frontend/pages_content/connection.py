"""
Db2 Database Connection Management Page.
"""
import streamlit as st
from ..api_client import CatalogLensAPIClient
from backend.core.config import get_settings


def show_connection_page(api: CatalogLensAPIClient):
    settings = get_settings()
    st.markdown("## 🔌 IBM Db2 Connection Dashboard")
    st.markdown("Configure and verify your connection to an IBM Db2 LUW instance or toggle the built-in enterprise demonstration database.")

    st.divider()

    # Mode Selector
    mode = st.radio(
        "Select Operation Mode:",
        ["Enterprise Demonstration Database (Preloaded Offline Snapshot)", "Live IBM Db2 Database (Custom Connection)"],
        index=0 if st.session_state.get("use_demo", True) else 1,
        horizontal=True,
    )
    is_demo = "Demonstration" in mode
    st.session_state["use_demo"] = is_demo

    health = api.get_health()
    driver_installed = health.get("ibm_db_driver_installed", False)

    if not driver_installed:
        st.warning("⚠️ The official 'ibm_db' native driver is not detected. Live connection queries require ibm_db. The Demonstration Database is active and fully functional.")

    if is_demo:
        st.success("✅ **Enterprise Demonstration Database Mode is Active.** 13 tables, 2 views, foreign keys, indexes, and intentional enterprise ambiguities are loaded in memory.")
    else:
        st.info("🌐 **Live IBM Db2 Connection Mode.** Enter credentials below to connect to a live Db2 LUW instance.")

        col1, col2 = st.columns(2)
        with col1:
            host = st.text_input("DB2_HOST", value=st.session_state.get("db2_host", settings.db2_host))
            port = st.number_input("DB2_PORT", value=int(st.session_state.get("db2_port", settings.db2_port)), step=1)
            database = st.text_input("DB2_DATABASE", value=st.session_state.get("db2_database", settings.db2_database))
            schema = st.text_input("DB2_SCHEMA", value=st.session_state.get("active_schema", settings.db2_schema))
        with col2:
            username = st.text_input("DB2_USERNAME", value=st.session_state.get("db2_username", settings.db2_username))
            password = st.text_input("DB2_PASSWORD", value=st.session_state.get("db2_password", ""), type="password")
            security = st.selectbox("DB2_SECURITY", ["", "SSL"], index=0 if not settings.db2_security else 1)

        test_btn = st.button("🔍 Test Db2 Live Connection", type="primary")

        if test_btn:
            with st.spinner("Connecting to IBM Db2 and executing 'SELECT 1 FROM SYSIBM.SYSDUMMY1'..."):
                result = api.test_connection(
                    host=host,
                    port=port,
                    database=database,
                    username=username,
                    password=password,
                    security=security,
                )
                if result.get("success"):
                    st.success(f"🎉 {result.get('message')}")
                    st.session_state["db2_host"] = host
                    st.session_state["db2_port"] = port
                    st.session_state["db2_database"] = database
                    st.session_state["db2_username"] = username
                    st.session_state["db2_password"] = password
                    st.session_state["active_schema"] = schema
                else:
                    st.error(f"❌ Connection Failed: {result.get('message')}")
                    st.caption("Double-check network access, Db2 port (typically 50000 or 50001 SSL), and user credentials.")

    st.divider()

    # Current Connection & Catalog Summary
    schema_name = st.session_state.get("active_schema", "ENTERPRISE")
    meta = api.get_metadata(schema_name=schema_name, use_demo=is_demo)

    st.markdown("### 📊 Active Schema Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Schema Name", meta.get("schema_name", schema_name))
    with c2:
        st.metric("Tables Registered", meta.get("total_tables", 0))
    with c3:
        st.metric("Views Registered", meta.get("total_views", 0))
    with c4:
        st.metric("Total Columns", meta.get("total_columns", 0))
