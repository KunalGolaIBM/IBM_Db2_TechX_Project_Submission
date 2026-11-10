"""
Audit Log Page
"""
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app import audit

st.set_page_config(page_title="Audit Log", page_icon="📝", layout="wide")

if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in first")
    if st.button("Go to Login"):
        st.switch_page("pages/1_🔐_Login.py")
    st.stop()

st.title("📝 Audit Log")
st.markdown("SHA256 hash-chained audit trail — tamper-evident by design")

st.markdown("<br>", unsafe_allow_html=True)

col1, col2 = st.columns([1, 3])

with col1:
    if st.button("🔍 Verify Chain", type="primary"):
        try:
            is_valid, error = audit.verify_chain()
            
            if is_valid:
                st.success("✓ Chain is INTACT")
            else:
                st.error(f"✗ Chain is BROKEN\n\n{error}")
        except Exception as e:
            st.error(f"Error: {e}")

with col2:
    st.info("The audit chain uses SHA256 hashing. Any tampering will be detected.")

st.markdown("---")

st.subheader("Recent Audit Records")

limit = st.slider("Number of records", 10, 100, 50)

try:
    records = audit.get_all_records()[-limit:]
    
    if records:
        for record in reversed(records):
            with st.expander(f"#{record.id}: {record.action} by {record.actor}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Actor:** {record.actor}")
                    st.write(f"**Action:** {record.action}")
                    st.write(f"**Subject:** {record.subject}")
                
                with col2:
                    st.write(f"**Created:** {record.created_at}")
                    st.write(f"**Hash:** `{record.hash[:32]}...`")
                
                if record.detail:
                    st.json(record.detail)
    else:
        st.info("No audit records found")
except Exception as e:
    st.error(f"Error: {e}")
