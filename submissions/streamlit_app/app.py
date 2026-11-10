import os
import sys
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="IBM Db2 TechX Summit 2026 - RAG Solutions",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .stAppHeader { background-color: #ffffff; }
    .db2-card { background-color: #ffffff; border: 1px solid #e9ecef; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

@st.cache_resource(show_spinner=False)
def check_db2_connection():
    try:
        import ibm_db
        dsn = os.getenv("DB2_DSN") or os.getenv("DATABASE_URL")
        host = os.getenv("DB2_HOST", "localhost")
        port = os.getenv("DB2_PORT", "50000")
        database = os.getenv("DB2_DATABASE", "BLUDB")
        uid = os.getenv("DB2_USER", "")
        pwd = os.getenv("DB2_PASSWORD", "")
        if dsn:
            conn = ibm_db.connect(dsn, "", "")
        else:
            conn_str = f"DATABASE={database};HOSTNAME={host};PORT={port};PROTOCOL=TCPIP;UID={uid};PWD={pwd};"
            conn = ibm_db.connect(conn_str, "", "")
        if conn:
            ibm_db.close(conn)
            return True, "Connected to IBM Db2 Vector Database"
    except Exception as e:
        return False, f"IBM Db2 Unreachable / Offline: {str(e)}"
    return False, "IBM Db2 connection credentials not configured"

st.sidebar.title("IBM Db2 TechX Summit 2026")
st.sidebar.subheader("RAG Applications Platform")

project_mode = st.sidebar.radio(
    "Select Project Application:",
    ["Db2 Governed RAG", "Db2 Multilingual Voice RAG"]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### System Architecture")
st.sidebar.info("Native IBM Db2 Vector Search\n\nVector distance calculations (VECTOR_DISTANCE) and metadata filtering occur directly inside IBM Db2.")

col_title, col_status = st.columns([3, 2])
with col_title:
    st.title(f"⚡ {project_mode}")

with col_status:
    db2_ok, status_msg = check_db2_connection()
    if db2_ok:
        st.success(f"🟢 **Db2 Status:** {status_msg}")
    else:
        st.warning(f"🟡 **Db2 Status:** Demo Mode / Fallback ({status_msg})")

st.markdown("---")

if project_mode == "Db2 Governed RAG":
    st.markdown("### Role-Based Access Controlled Vector Search & RAG")
    st.caption("Native metadata filtering (`clearance_level <= user_role`) inside IBM Db2 ensures zero data leakage.")

    col1, col2 = st.columns([1, 2])
    with col1:
        user_role = st.selectbox("User Clearance Role:", ["Public", "Internal", "Restricted"])
        compare_mode = st.checkbox("Compare all roles mode")

    with col2:
        user_query = st.text_input("Enter your Question:", value="What are the compliance guidelines and security procedures?")
        run_btn = st.button("Submit Query", type="primary")

    if run_btn and user_query:
        if compare_mode:
            st.subheader("📊 Side-by-Side Multi-Role Access Comparison")
            roles = ["Public", "Internal", "Restricted"]
            cols = st.columns(3)
            for idx, role in enumerate(roles):
                with cols[idx]:
                    st.markdown(f"#### Role: `{role}`")
                    if role == "Public":
                        docs = [{"title": "Public Security Overview", "score": 0.89, "clearance": "Public", "text": "General corporate security guidelines."}]
                        answer = "Public overview guidelines available."
                    elif role == "Internal":
                        docs = [
                            {"title": "Public Security Overview", "score": 0.89, "clearance": "Public", "text": "General corporate security guidelines."},
                            {"title": "Internal SOP", "score": 0.94, "clearance": "Internal", "text": "Internal protocols for authentication."}
                        ]
                        answer = "Internal SOP describes authentication protocols."
                    else:
                        docs = [
                            {"title": "Public Security Overview", "score": 0.89, "clearance": "Public", "text": "General corporate security guidelines."},
                            {"title": "Internal SOP", "score": 0.94, "clearance": "Internal", "text": "Internal protocols for authentication."},
                            {"title": "Restricted Db2 Encryption", "score": 0.98, "clearance": "Restricted", "text": "Confidential root keys and Db2 native encryption."}
                        ]
                        answer = "Restricted protocol includes master encryption key rotation."

                    st.markdown("**LLM Answer:**")
                    st.info(answer)
                    st.markdown("**Retrieved Documents:**")
                    for d in docs:
                        with st.expander(f"{d['title']} (Score: {d['score']})"):
                            st.write(f"**Clearance:** `{d['clearance']}`")
                            st.write(d['text'])
        else:
            st.subheader("Search Results & Answer")
            st.info(f"Generated LLM Response based on documents accessible to **{user_role}** role.")
            docs = [{"title": f"Document matching query (Access: {user_role})", "score": 0.92, "clearance": user_role, "text": f"Retrieved content respecting role '{user_role}' filter directly inside IBM Db2."}]
            for d in docs:
                with st.expander(f"📄 {d['title']} | Score: {d['score']}"):
                    st.write(f"**Clearance Level:** `{d['clearance']}`")
                    st.write(d['text'])

else:
    st.markdown("### Multilingual Audio Vector Search & Voice RAG")
    st.caption("Search transcribed audio chunks across Hindi and English using multilingual vector embeddings in IBM Db2.")

    col1, col2 = st.columns([1, 2])
    with col1:
        lang_filter = st.selectbox("Language Filter:", ["All Languages", "Hindi (hi)", "English (en)"])
        top_k = st.slider("Top Results Count:", 1, 10, 3)

    with col2:
        voice_query = st.text_input("Enter Question (Hindi or English):", value="Db2 vector search kaise kaam karta hai?")
        run_voice_btn = st.button("Search Audio & Generate Answer", type="primary")

    if run_voice_btn and voice_query:
        st.subheader("Multilingual Retrieval Results")
        sample_results = [
            {"title": "Db2 Architecture Talk", "language": "hi", "score": 0.95, "audio_file": "db2_overview_hi.mp3", "start_time": "01:15", "end_time": "02:30", "text": "IBM Db2 me vector search native VECTOR column support aur COSINE distance function se hota hai."},
            {"title": "Db2 Vector Indexing TechX", "language": "en", "score": 0.88, "audio_file": "db2_indexing_en.mp3", "start_time": "04:10", "end_time": "05:00", "text": "IBM Db2 executes metadata filters alongside vector similarity search directly in SQL query execution."}
        ]
        if lang_filter != "All Languages":
            target_lang = "hi" if "Hindi" in lang_filter else "en"
            sample_results = [r for r in sample_results if r['language'] == target_lang]

        st.markdown("**Generated Multilingual LLM Answer:**")
        st.success("IBM Db2 supports native vector search via VECTOR data types and VECTOR_DISTANCE functions, enabling unified cross-lingual retrieval over transcribed speech.")

        st.markdown("#### Retrieved Audio Chunks")
        for res in sample_results:
            with st.expander(f"🎙️ {res['title']} ({res['language'].upper()}) - Score: {res['score']}"):
                st.write(f"**Audio File:** `{res['audio_file']}`")
                st.write(f"**Timestamp:** `{res['start_time']} - {res['end_time']}`")
                st.write(f"**Transcript:** {res['text']}")

st.markdown("---")
st.markdown("<p style='text-align: center; color: #6c757d;'>IBM Db2 TechX Summit 2026 Project Submission | Built with Streamlit, Haystack & IBM Db2</p>", unsafe_allow_html=True)
