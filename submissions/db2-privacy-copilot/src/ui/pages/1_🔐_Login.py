"""
Login Page - Authentication flow
"""
import streamlit as st
import sys
sys.path.insert(0, "..")

# Page config
st.set_page_config(
    page_title="Login - Db2 Privacy Copilot",
    page_icon="🔐",
    layout="centered",
)

# Custom CSS
st.markdown("""
<style>
    /* Center login form */
    .login-container {
        max-width: 450px;
        margin: 80px auto;
        padding: 40px;
        background: white;
        border-radius: 15px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.1);
    }
    
    .login-header {
        text-align: center;
        margin-bottom: 30px;
    }
    
    .login-header h1 {
        color: #667eea;
        font-size: 2em;
        margin-bottom: 10px;
    }
    
    .role-card {
        padding: 15px;
        background: #f8f9fa;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid #667eea;
        cursor: pointer;
        transition: all 0.3s;
    }
    
    .role-card:hover {
        background: #e9ecef;
        transform: translateX(5px);
    }
    
    .role-title {
        font-weight: 600;
        color: #333;
        font-size: 1.1em;
    }
    
    .role-desc {
        color: #666;
        font-size: 0.9em;
        margin-top: 5px;
    }
    
    [data-testid="stSidebar"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_role' not in st.session_state:
    st.session_state.user_role = None
if 'user_name' not in st.session_state:
    st.session_state.user_name = None

# Check if already logged in
if st.session_state.authenticated:
    st.success(f"✓ Already logged in as {st.session_state.user_name} ({st.session_state.user_role})")
    if st.button("Continue to Dashboard"):
        st.switch_page("pages/2_📊_Dashboard.py")
    if st.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.session_state.user_name = None
        st.rerun()
    st.stop()

# Login header
st.markdown("""
<div class="login-header">
    <h1>🔐 Sign In</h1>
    <p style="color: #666;">Choose your role to access the Privacy Copilot</p>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Role selection
st.markdown("### Select Your Role")

# Define users (in production, this would come from a database)
users = {
    "VIEWER": {
        "name": "Alice Johnson",
        "email": "alice@example.com",
        "desc": "Read-only access to dashboards and reports",
        "permissions": ["View Discovery", "View Classification", "View Audit Logs"]
    },
    "ANALYST": {
        "name": "Bob Smith",
        "email": "bob@example.com",
        "desc": "Can create requests and manage consents",
        "permissions": ["All Viewer permissions", "Create Requests", "Manage Consents", "Run Classification"]
    },
    "DPO": {
        "name": "Charlie Davis",
        "email": "charlie@example.com",
        "desc": "Data Protection Officer - full access",
        "permissions": ["All Analyst permissions", "Approve Requests", "Execute Erasure", "Verify Audit Chain"]
    }
}

# Display role cards
for role, info in users.items():
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown(f"""
            <div style="padding: 15px; background: #f8f9fa; border-radius: 8px; margin: 10px 0; border-left: 4px solid #667eea;">
                <div style="font-weight: 600; color: #333; font-size: 1.1em;">
                    {role} - {info['name']}
                </div>
                <div style="color: #666; font-size: 0.9em; margin-top: 5px;">
                    📧 {info['email']}
                </div>
                <div style="color: #666; font-size: 0.9em; margin-top: 5px;">
                    {info['desc']}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            if st.button(f"Login as {role}", key=f"login_{role}", use_container_width=True):
                st.session_state.authenticated = True
                st.session_state.user_role = role
                st.session_state.user_name = info['name']
                st.session_state.user_email = info['email']
                st.success(f"✓ Logged in as {info['name']}")
                st.balloons()
                st.switch_page("pages/2_📊_Dashboard.py")

st.markdown("<br><br>", unsafe_allow_html=True)

# Demo notice
st.info("""
**Demo Mode**: This is a demonstration system with mock authentication.

In production:
- Use OAuth2/JWT tokens
- Integrate with corporate SSO (SAML)
- Multi-factor authentication for DPO role
- Audit all login attempts
""")

st.markdown("<br>", unsafe_allow_html=True)

# Back button
if st.button("← Back to Landing Page"):
    st.switch_page("app.py")
