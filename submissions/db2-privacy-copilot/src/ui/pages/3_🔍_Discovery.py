"""
Schema Discovery Page
"""
import streamlit as st
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from app import agents
from app.config import settings

st.set_page_config(page_title="Discovery", page_icon="🔍", layout="wide")

if 'authenticated' not in st.session_state or not st.session_state.authenticated:
    st.warning("Please log in first")
    if st.button("Go to Login"):
        st.switch_page("pages/1_🔐_Login.py")
    st.stop()

st.title("🔍 Schema Discovery")
st.markdown("Automatically map your database schema, foreign keys, and relationships")

st.markdown("<br>", unsafe_allow_html=True)

if st.button("🔄 Scan Schema", type="primary"):
    with st.spinner("Scanning database schema..."):
        try:
            result = agents.discover_schema(settings.db2_schema)
            
            st.success(f"✓ Found {len(result['tables'])} tables with {result['column_count']} columns")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown("### 📊 Tables")
                for table in result['tables']:
                    with st.expander(f"📄 {table}"):
                        cols = result['columns_by_table'].get(table, [])
                        st.write(f"**Columns:** {len(cols)}")
                        
                        for col in cols:
                            nullable = "NULL" if col['nullable'] else "NOT NULL"
                            st.text(f"  • {col['name']} ({col['type']}) {nullable}")
            
            with col2:
                st.markdown("### 🔗 Foreign Keys")
                for fk in result['foreign_keys']:
                    st.info(f"**{fk['child']}** → {fk['parent']}")
                    st.caption(f"FK: {fk['fk_columns']} → PK: {fk['pk_columns']}")
                
                st.markdown("### 📈 Statistics")
                st.metric("Total Tables", len(result['tables']))
                st.metric("Total Columns", result['column_count'])
                st.metric("Foreign Keys", result['fk_count'])
            
        except Exception as e:
            st.error(f"Error: {e}")
