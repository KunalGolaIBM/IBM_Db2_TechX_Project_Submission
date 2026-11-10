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

# Sidebar Configuration
st.sidebar.header("Configuration")

# Demo mode toggle to bypass live Db2 connection requirements when needed
demo_mode = st.sidebar.checkbox("Enable Demo / Mock Mode", value=True)

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

# --- DEMO MODE EXECUTION ---
if demo_mode:
    st.sidebar.info("you're in!!")
    st.success("✅ Connected to IBM Db2 (Mock Cluster Active)")

    user_query = st.text_input(
        "Ask a question about your data:", 
        value="Show the top 3 flights with the worst arrival delays."
    )

    if st.button("Run Analytics Query", type="primary"):
        if user_query:
            with st.spinner("Analyzing data via IBM Db2 engine..."):
                st.markdown("### 🔍 Generated SQL")
                st.code(
                    """SELECT AIRLINE, FLIGHT_NUMBER, ORIGIN, DEST, ARR_DELAY 
FROM FLIGHTS 
ORDER BY ARR_DELAY DESC 
FETCH FIRST 3 ROWS ONLY;""", 
                    language="sql"
                )

                st.markdown("### 📈 Result")
                mock_data = pd.DataFrame([
                    {"AIRLINE": "Delta Air Lines", "FLIGHT_NUMBER": "DL-1420", "ORIGIN": "JFK", "DEST": "LAX", "ARR_DELAY": "184 mins"},
                    {"AIRLINE": "American Airlines", "FLIGHT_NUMBER": "AA-809", "ORIGIN": "ORD", "DEST": "MIA", "ARR_DELAY": "162 mins"},
                    {"AIRLINE": "United Airlines", "FLIGHT_NUMBER": "UA-204", "ORIGIN": "SFO", "DEST": "ORD", "ARR_DELAY": "145 mins"},
                ])
                st.dataframe(mock_data, use_container_width=True)

# --- LIVE DB2 CONNECTION EXECUTION ---
else:
    if not (db2_password and openai_api_key):
        st.warning("⚠️ Please enter your IBM Db2 password and OpenAI API key in the sidebar, or enable Demo Mode.")
    else:
        try:
            agent = get_db2_agent()
            st.success("✅ Connected to live IBM Db2 database!")

            user_query = st.text_input(
                "Ask a question about your data:", 
                value="Show the top 3 flights with the worst arrival delays."
            )
            if st.button("Run Analytics Query", type="primary"):
                if user_query:
                    with st.spinner("Analyzing data via IBM Db2..."):
                        response = agent.invoke({"input": user_query})
                        st.markdown("### 📈 Result")
                        st.write(response["output"])
        except Exception as e:
            st.error(f"Error connecting to Db2: {e}")
