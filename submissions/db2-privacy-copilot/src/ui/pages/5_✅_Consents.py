"""
Consent Management Page
"""
import streamlit as st
import sys
import os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app import consent

st.set_page_config(page_title="Consents", page_icon="✅", layout="wide")

if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in first")
    if st.button("Go to Login"):
        st.switch_page("pages/1_🔐_Login.py")
    st.stop()

st.title("✅ Consent Management")
st.markdown("Track and manage user consents with bitemporal precision")

tab1, tab2, tab3 = st.tabs(["Grant Consent", "Withdraw Consent", "View Consents"])

with tab1:
    st.subheader("Grant Consent")
    
    with st.form("grant_form"):
        patient_id = st.number_input("Patient ID", min_value=1, step=1)
        purpose = st.selectbox("Purpose", ["MARKETING", "RESEARCH", "TREATMENT", "ANALYTICS"])
        start_date = st.date_input("Start Date", date.today())
        end_date = st.date_input("End Date", date(2027, 12, 31))
        
        if st.form_submit_button("Grant Consent", type="primary"):
            try:
                consent.grant(
                    patient_id,
                    purpose,
                    start_date.isoformat(),
                    end_date.isoformat()
                )
                st.success(f"✓ Consent granted for patient {patient_id}")
            except Exception as e:
                st.error(f"Error: {e}")

with tab2:
    st.subheader("Withdraw Consent")
    
    with st.form("withdraw_form"):
        patient_id = st.number_input("Patient ID", min_value=1, step=1, key="withdraw_pid")
        purpose = st.selectbox("Purpose", ["MARKETING", "RESEARCH", "TREATMENT", "ANALYTICS"], key="withdraw_purpose")
        effective_date = st.date_input("Effective Date", date.today())
        
        if st.form_submit_button("Withdraw Consent", type="primary"):
            try:
                consent.withdraw(
                    patient_id,
                    purpose,
                    effective_date.isoformat()
                )
                st.success(f"✓ Consent withdrawn for patient {patient_id}")
            except Exception as e:
                st.error(f"Error: {e}")

with tab3:
    st.subheader("View Consents")
    
    patient_id = st.number_input("Patient ID", min_value=1, step=1, key="view_pid")
    
    if st.button("Load Consents"):
        try:
            consents = consent.current_consents(patient_id)
            
            if consents:
                for c in consents:
                    granted_icon = "✅" if c['granted'] else "❌"
                    st.write(f"{granted_icon} **{c['purpose']}**")
                    st.caption(f"Valid: {c['bus_start']} to {c['bus_end']}")
            else:
                st.info(f"No consents found for patient {patient_id}")
        except Exception as e:
            st.error(f"Error: {e}")
