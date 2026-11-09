import os
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI

st.set_page_config(page_title="IntelliDB2 Assistant", page_icon="📊", layout="wide")
st.title("📊 IntelliDB2 – Text-to-SQL Analytics Assistant")
st.caption("IBM Db2Hack 2026 Submission")

st.sidebar.header("Configuration")
db2_host = st.sidebar.text_input("Db2 Host", value="localhost")
db2_port = st.sidebar.text_input("Db2 Port", value="50000")
db2_database = st.sidebar.text_input("Database Name", value="BLUDB")
db2_user = st.sidebar.text_input("Db2 Username", value="db2inst1")
db2_password = st.sidebar.text_input("Db2 Password", type="password")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password")

if openai_api_key:
    os.environ["OPENAI_API_KEY"] = openai_api_key

def get_db2_agent():
    conn_str = f"ibm_db_sa://{db2_user}:{db2_password}@{db2_host}:{db2_port}/{db2_database}"
    engine = create_engine(conn_str)
    db = SQLDatabase(engine)
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
    return create_sql_agent(llm=llm, db=db, verbose=True, agent_type="openai-tools")

if not (db2_password and openai_api_key):
    st.warning("⚠️ Please enter your IBM Db2 password and OpenAI API key in the sidebar.")
else:
    try:
        agent = get_db2_agent()
        st.success("✅ Connected to IBM Db2!")
        
        user_query = st.text_input("Ask a question about your data:", "Show the top 3 flights with the worst arrival delays.")
        if st.button("Run Analytics Query", type="primary"):
            if user_query:
                with st.spinner("Analyzing data via IBM Db2..."):
                    response = agent.invoke({"input": user_query})
                    st.markdown("### 📈 Result")
                    st.write(response["output"])
    except Exception as e:
        st.error(f"Error: {e}")