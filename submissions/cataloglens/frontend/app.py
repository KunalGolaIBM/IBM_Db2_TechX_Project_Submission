"""
CatalogLens Streamlit Frontend Entrypoint.
Enterprise Database Intelligence and Agentic Exploration Dashboard.
"""
import sys
from pathlib import Path

# Add project root to sys.path so backend imports work reliably
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
from frontend.api_client import CatalogLensAPIClient
from frontend.pages_content import (
    show_overview_page,
    show_connection_page,
    show_schema_explorer_page,
    show_relationships_page,
    show_table_understanding_page,
    show_workflow_discovery_page,
    show_dependency_investigation_page,
    show_architecture_page,
)

# Page configuration
st.set_page_config(
    page_title="CatalogLens — Database Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Enterprise CSS
st.markdown(
    """
    <style>
    .main-header {
        font-size: 26px;
        font-weight: 700;
        color: #F4F4F4;
        margin-bottom: 0px;
    }
    .status-pill-green {
        background-color: #198038;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 600;
    }
    .status-pill-blue {
        background-color: #0F62FE;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 600;
    }
    .status-pill-amber {
        background-color: #BA8500;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize API Client
api_client = CatalogLensAPIClient()

# Initialize session state defaults
if "use_demo" not in st.session_state:
    st.session_state["use_demo"] = False
if "active_schema" not in st.session_state:
    st.session_state["active_schema"] = "ENTERPRISE"

# Sidebar Navigation
with st.sidebar:
    st.markdown("## 🔍 CatalogLens")
    st.caption("v1.0.0 | IBM Db2 Intelligence")

    nav_selection = st.radio(
        "Navigation",
        [
            "1. Overview",
            "2. Database Connection",
            "3. Schema Explorer",
            "4. Relationship Intelligence",
            "5. AI Table Understanding",
            "6. Business Workflow Discovery",
            "7. Dependency Investigation",
            "8. Architecture and About",
        ],
        index=0,
    )

    st.divider()

    # System Diagnostics Pill Box
    st.markdown("### ⚙️ System Status")
    health = api_client.get_health()

    mode_str = "Enterprise Demo" if st.session_state.get("use_demo", True) else "Live Db2 LUW"
    st.markdown(f"Mode: <span class='status-pill-blue'>{mode_str}</span>", unsafe_allow_html=True)
    st.markdown(f"Schema: <code>{st.session_state.get('active_schema', 'ENTERPRISE')}</code>")

    driver_ok = health.get("ibm_db_driver_installed", False)
    st.markdown(
        f"Db2 Driver: <span class='{'status-pill-green' if driver_ok else 'status-pill-amber'}'>{'Installed' if driver_ok else 'Not Found'}</span>",
        unsafe_allow_html=True,
    )

    claude_ok = health.get("anthropic_configured", False)
    st.markdown(
        f"Claude API: <span class='{'status-pill-green' if claude_ok else 'status-pill-amber'}'>{'Connected' if claude_ok else 'Heuristic'}</span>",
        unsafe_allow_html=True,
    )

    st.divider()
    st.caption("IBM Db2 Developer Extension Compatible")


# Route to selected page
if nav_selection.startswith("1."):
    show_overview_page(api_client)
elif nav_selection.startswith("2."):
    show_connection_page(api_client)
elif nav_selection.startswith("3."):
    show_schema_explorer_page(api_client)
elif nav_selection.startswith("4."):
    show_relationships_page(api_client)
elif nav_selection.startswith("5."):
    show_table_understanding_page(api_client)
elif nav_selection.startswith("6."):
    show_workflow_discovery_page(api_client)
elif nav_selection.startswith("7."):
    show_dependency_investigation_page(api_client)
elif nav_selection.startswith("8."):
    show_architecture_page()
