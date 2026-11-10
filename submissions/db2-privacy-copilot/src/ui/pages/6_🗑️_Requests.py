"""
Rights Requests Page
"""
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app import agents

st.set_page_config(page_title="Requests", page_icon="🗑️", layout="wide")

if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in first")
    if st.button("Go to Login"):
        st.switch_page("pages/1_🔐_Login.py")
    st.stop()

st.title("🗑️ Rights Requests")
st.markdown("Create and manage data subject rights requests (erasure, access)")

tab1, tab2 = st.tabs(["Create Request", "Approve Requests"])

with tab1:
    st.subheader("Create Erasure Request")
    
    subject_id = st.number_input("Subject ID (Patient ID)", min_value=1, step=1)
    
    if st.button("📋 Generate Plan", type="primary"):
        with st.spinner("Generating erasure plan..."):
            try:
                result = agents.plan_erasure(subject_id)
                
                if 'error' in result:
                    st.error(result['error'])
                else:
                    sim = result['simulation']
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Steps", sim['total_steps'])
                    with col2:
                        st.metric("Total Rows", sim['total_rows'])
                    with col3:
                        if sim['has_unverified']:
                            st.warning(f"⚠️ {sim['unverified_rules']} unverified rules")
                        else:
                            st.success("✓ All rules verified")
                    
                    st.markdown("### 📋 Execution Plan")
                    
                    for i, step in enumerate(result['steps'], 1):
                        verified_icon = "✓" if step['rule_verified'] else "⚠️"
                        
                        with st.expander(f"{i}. {step['action']} {step['table']} ({step['est_rows']} rows)"):
                            st.write(f"**Action:** {step['action']}")
                            st.write(f"**Reason:** {step['reason']}")
                            st.write(f"**Estimated Rows:** {step['est_rows']}")
                            st.write(f"**Rule Verified:** {verified_icon}")
                    
                    st.info(f"**Plan Hash:** `{result['plan_hash']}`")
                    st.warning("⚠️ This is a DRY RUN - no data has been modified")
                    
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    st.subheader("Approve Requests")
    
    if st.session_state.user_role != "DPO":
        st.warning("DPO role required to approve requests")
    else:
        st.info("In a production system, pending requests would be listed here for approval.")
        st.markdown("""
        **Approval Workflow:**
        1. DPO reviews the plan
        2. Guardrail validates SQL
        3. Execution in single transaction
        4. Audit trail records everything
        """)
