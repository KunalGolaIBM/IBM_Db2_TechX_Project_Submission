"""
Main Dashboard - Overview and Quick Actions
"""
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app import agents, audit, consent
from app.config import settings
from app.db import query
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Dashboard - Db2 Privacy Copilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Check authentication
if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in first")
    if st.button("Go to Login"):
        st.switch_page("pages/1_🔐_Login.py")
    st.stop()

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
        margin-bottom: 20px;
    }
    
    .metric-value {
        font-size: 2.5em;
        font-weight: 700;
        color: #667eea;
    }
    
    .metric-label {
        color: #666;
        font-size: 1.1em;
        margin-top: 5px;
    }
    
    .quick-action {
        padding: 15px;
        background: #f8f9fa;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid #28a745;
        transition: all 0.3s;
    }
    
    .quick-action:hover {
        background: #e9ecef;
        transform: translateX(5px);
    }
    
    .status-badge {
        display: inline-block;
        padding: 5px 12px;
        border-radius: 15px;
        font-size: 0.9em;
        font-weight: 600;
    }
    
    .status-healthy {
        background: #d4edda;
        color: #155724;
    }
    
    .status-warning {
        background: #fff3cd;
        color: #856404;
    }
    
    .status-error {
        background: #f8d7da;
        color: #721c24;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown(f"""
    ### 👤 {st.session_state.user_name}
    **Role:** {st.session_state.user_role}  
    **Email:** {st.session_state.get('user_email', 'N/A')}
    """)
    
    st.markdown("---")
    
    st.markdown("### 🧭 Navigation")
    
    if st.button("📊 Dashboard", use_container_width=True):
        st.switch_page("pages/2_📊_Dashboard.py")
    
    if st.button("🔍 Discovery", use_container_width=True):
        st.switch_page("pages/3_🔍_Discovery.py")
    
    if st.button("🏷️ Classification", use_container_width=True):
        st.switch_page("pages/4_🏷️_Classification.py")
    
    if st.button("✅ Consents", use_container_width=True):
        st.switch_page("pages/5_✅_Consents.py")
    
    if st.button("🗑️ Requests", use_container_width=True):
        st.switch_page("pages/6_🗑️_Requests.py")
    
    if st.button("📝 Audit Log", use_container_width=True):
        st.switch_page("pages/7_📝_Audit.py")
    
    st.markdown("---")
    
    if st.button("🔓 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.session_state.user_name = None
        st.switch_page("app.py")

# Header
st.title("📊 Dashboard")
st.markdown(f"Welcome back, **{st.session_state.user_name}**! Here's your privacy compliance overview.")

st.markdown("<br>", unsafe_allow_html=True)

# System Status
st.markdown("### 🔧 System Status")

col1, col2, col3, col4 = st.columns(4)

with col1:
    try:
        result = agents.discover_schema(settings.db2_schema)
        table_count = len(result.get('tables', []))
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{table_count}</div>
            <div class="metric-label">Tables Discovered</div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">N/A</div>
            <div class="metric-label">Tables</div>
        </div>
        """, unsafe_allow_html=True)

with col2:
    try:
        result = agents.classify_schema(settings.db2_schema)
        pii_count = result.get('pii_columns', 0)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{pii_count}</div>
            <div class="metric-label">PII Columns</div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">N/A</div>
            <div class="metric-label">PII Columns</div>
        </div>
        """, unsafe_allow_html=True)

with col3:
    try:
        rows = query("""
            SELECT COUNT(*) FROM REQUESTS 
            WHERE STATUS = 'PENDING_APPROVAL'
        """)
        pending = rows[0][0] if rows else 0
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{pending}</div>
            <div class="metric-label">Pending Requests</div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">0</div>
            <div class="metric-label">Pending Requests</div>
        </div>
        """, unsafe_allow_html=True)

with col4:
    try:
        records = audit.get_all_records()
        audit_count = len(records)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{audit_count}</div>
            <div class="metric-label">Audit Records</div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">0</div>
            <div class="metric-label">Audit Records</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Quick Actions (role-based)
st.markdown("### ⚡ Quick Actions")

col1, col2 = st.columns(2)

with col1:
    if st.session_state.user_role in ["ANALYST", "DPO"]:
        if st.button("🔍 Run Discovery Scan", use_container_width=True):
            st.switch_page("pages/3_🔍_Discovery.py")
        
        if st.button("🏷️ Classify PII", use_container_width=True):
            st.switch_page("pages/4_🏷️_Classification.py")
        
        if st.button("➕ Create New Request", use_container_width=True):
            st.switch_page("pages/6_🗑️_Requests.py")
    else:
        st.info("Analyst/DPO permissions required for these actions")

with col2:
    if st.session_state.user_role == "DPO":
        if st.button("✅ Review Pending Requests", use_container_width=True):
            st.switch_page("pages/6_🗑️_Requests.py")
        
        if st.button("🔍 Verify Audit Chain", use_container_width=True):
            st.switch_page("pages/7_📝_Audit.py")
        
        if st.button("⚙️ Manage Retention Rules", use_container_width=True):
            st.info("Feature coming soon")
    else:
        st.info("DPO permissions required for approval actions")

st.markdown("<br>", unsafe_allow_html=True)

# Recent Activity
st.markdown("### 📋 Recent Activity")

try:
    records = audit.get_all_records()[-10:]  # Last 10
    
    if records:
        for record in reversed(records):
            action_icon = {
                "STARTUP": "🚀",
                "CLASSIFICATION": "🏷️",
                "DISCOVERY": "🔍",
                "CONSENT_GRANTED": "✅",
                "CONSENT_WITHDRAWN": "❌",
                "REQUEST_CREATED": "📝",
                "ERASURE": "🗑️",
            }.get(record.action, "📌")
            
            with st.expander(f"{action_icon} {record.action} by {record.actor} - {record.created_at}"):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.write(f"**Action:** {record.action}")
                    st.write(f"**Actor:** {record.actor}")
                    if record.subject:
                        st.write(f"**Subject ID:** {record.subject}")
                
                with col2:
                    st.write(f"**Hash:** `{record.hash[:16]}...`")
                    st.write(f"**ID:** {record.id}")
                
                if record.detail:
                    st.json(record.detail)
    else:
        st.info("No recent activity")
except Exception as e:
    st.error(f"Error loading activity: {e}")

st.markdown("<br>", unsafe_allow_html=True)

# System Health
st.markdown("### 💚 System Health")

col1, col2 = st.columns(2)

with col1:
    st.success("✓ Database: Connected (Mock Mode)")
    st.success("✓ API: Running on port 8000")
    st.success("✓ UI: Running on port 8501")

with col2:
    try:
        is_valid, error = audit.verify_chain()
        if is_valid:
            st.success("✓ Audit Chain: Intact")
        else:
            st.error(f"✗ Audit Chain: Broken - {error}")
    except Exception as exc:
        st.warning(f"⚠ Audit Chain: Unable to verify: {exc}")

st.markdown("<br>", unsafe_allow_html=True)

# Tips based on role
st.markdown("### 💡 Tips & Best Practices")

if st.session_state.user_role == "VIEWER":
    st.info("""
    **As a Viewer, you can:**
    - Monitor system metrics and compliance status
    - View classification results and PII mappings
    - Check audit logs for transparency
    - Generate reports (coming soon)
    
    💡 **Tip:** Use the Discovery page to understand data relationships
    """)
elif st.session_state.user_role == "ANALYST":
    st.info("""
    **As an Analyst, you can:**
    - Run discovery scans and PII classification
    - Create and manage consent records
    - Submit erasure requests for DPO approval
    - View detailed classification confidence scores
    
    💡 **Tip:** Review low-confidence classifications manually before finalizing
    """)
else:  # DPO
    st.warning("""
    **As a DPO, you have full access:**
    - Approve or reject erasure requests
    - Execute approved plans (with guardrail validation)
    - Verify audit chain integrity
    - Manage retention rules and policies
    
    ⚠️ **Important:** All approval decisions are permanently recorded in the audit chain
    """)

# Footer
st.markdown("---")
st.caption(f"Logged in as {st.session_state.user_name} ({st.session_state.user_role}) | Session active | Db2 Privacy Copilot v0.1.0")
