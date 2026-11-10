"""
PII Classification Page
"""
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app import agents
from app.config import settings

st.set_page_config(page_title="Classification", page_icon="🏷️", layout="wide")

if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in first")
    if st.button("Go to Login"):
        st.switch_page("pages/1_🔐_Login.py")
    st.stop()

st.title("🏷️ PII Classification")
st.markdown("AI-powered detection of personal data using pattern matching and semantic analysis")

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🔍 Run Classification", type="primary"):
    with st.spinner("Classifying columns..."):
        try:
            result = agents.classify_schema(settings.db2_schema)
            
            st.success(f"✓ Classified {result['total_columns']} columns")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Columns", result['total_columns'])
            with col2:
                st.metric("PII Columns", result['pii_columns'])
            with col3:
                st.metric("Need Review", result['needs_review'])
            
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("### 📋 Classification Results")
            
            for label, columns in result['by_label'].items():
                if label == "NOT_PII":
                    continue
                
                with st.expander(f"🏷️ {label} ({len(columns)} columns)"):
                    for col in columns:
                        confidence_pct = f"{col['confidence'] * 100:.1f}%"
                        review_flag = "⚠️ REVIEW" if col['needs_review'] else "✓"
                        
                        st.write(f"{review_flag} **{col['table']}.{col['column']}**")
                        st.caption(f"Confidence: {confidence_pct} | Method: {col['method']}")
            
        except Exception as e:
            st.error(f"Error: {e}")
