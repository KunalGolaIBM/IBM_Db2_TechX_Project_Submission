"""
Streamlit Web Application: IBM Db2 Vector Search Study Assistant.
Interactive, modern interface for students to query lecture notes,
explore formula derivations, and inspect Db2 vector similarity search results.
"""

import os
import sys
from pathlib import Path

# Add current folder to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from config import Db2RAGConfig
from db2_client import verify_db2_connection
from rag_engine import StudentNotesRAG
from chunker import StudentNotesChunker

st.set_page_config(
    page_title="IBM Db2 Study Assistant | TechX Summit 2026",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(90deg, #0f62fe 0%, #0043ce 50%, #8a3ffc 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #525252;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #f4f7fb;
        border-radius: 8px;
        padding: 12px 16px;
        border-left: 4px solid #0f62fe;
        margin-bottom: 10px;
    }
    .chunk-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        padding: 12px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_rag_engine():
    """Cache the RAG engine instance across app reruns."""
    rag = StudentNotesRAG()
    # Auto-index if not already initialized
    notes_file = Path(__file__).resolve().parent.parent / "data" / "notes.md"
    if notes_file.is_file():
        try:
            rag.index_notes_file(str(notes_file))
        except Exception:
            pass
    return rag


rag_engine = get_rag_engine()

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg", width=110)
    st.markdown("### 🗄️ IBM Db2 Connection")

    is_connected, status_msg = verify_db2_connection()
    if is_connected:
        st.success(f"**Connected**\n\n{status_msg}")
    else:
        st.warning(f"**Standby / Local Mode**\n\n{status_msg}")

    st.markdown("---")
    st.markdown("### ⚙️ Database Parameters")
    st.text(f"Host:     {Db2RAGConfig.DB2_HOST}:{Db2RAGConfig.DB2_PORT}")
    st.text(f"Database: {Db2RAGConfig.DB2_DATABASE}")
    st.text(f"Table:    {Db2RAGConfig.DB2_TABLE_NAME}")
    st.text(f"Vector:   {Db2RAGConfig.EMBEDDING_DIM}-dim ({Db2RAGConfig.DISTANCE_STRATEGY})")

    st.markdown("---")
    st.markdown("### 💡 Quick Exam Prompts")
    quick_prompts = [
        "What is the Friis transmission equation and its decibel form?",
        "Compare Selection Combining vs Maximal Ratio Combining (MRC)",
        "Why is a RAKE receiver useful in CDMA multipath channels?",
        "Explain the Poisson traffic model and Grade of Service (GoS)",
        "What is critical frequency and line-of-sight formula?",
        "How does frequency reuse cluster size affect capacity?"
    ]
    selected_quick = st.selectbox("Choose a sample prompt:", ["Select a prompt..."] + quick_prompts)

    st.markdown("---")
    if st.button("🔄 Re-index Notes to Db2", use_container_width=True):
        with st.spinner("Chunking, embedding and uploading to IBM Db2..."):
            notes_file = Path(__file__).resolve().parent.parent / "data" / "notes.md"
            if notes_file.is_file():
                cnt = rag_engine.index_notes_file(str(notes_file))
                st.success(f"Successfully indexed {cnt} chunks into Db2!")
            else:
                st.error("notes.md not found in data/ directory.")


# --- MAIN TABS ---
st.markdown('<div class="main-header">🎓 IBM Db2 AI Study Tutor</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Scalable Retrieval-Augmented Generation (RAG) powered by <b>IBM Db2 Native Vector Search</b> and <b>LangChain</b></div>',
    unsafe_allow_html=True
)

tab1, tab2, tab3 = st.tabs(["💬 Student Q&A Tutor", "📚 Notes & Vector Explorer", "🏗️ Architecture & Benchmarks"])

# TAB 1: Student Q&A Tutor
with tab1:
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "👋 Hello! I am your **IBM Db2 Exam Tutor**.\n\n"
                    "I answer your engineering questions with high-precision derivations and explanations "
                    "retrieved directly from your study notes in **IBM Db2 Vector Store**. Ask me anything!"
                ),
                "sources": []
            }
        ]

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander(f"🔍 Db2 Vector Citations ({len(msg['sources'])} chunks)"):
                    for src in msg["sources"]:
                        st.markdown(
                            f"**{src['section_title']}** `({src['topic']})` "
                            f"{'• Cosine Score: ' + str(src['score']) if src.get('score') else ''}"
                        )
                        st.caption(src.get("snippet", ""))

    # Input handling
    user_query = None
    if selected_quick and selected_quick != "Select a prompt...":
        user_query = selected_quick
    chat_input = st.chat_input("Ask a question about wireless communications, formulas, or derivations...")
    if chat_input:
        user_query = chat_input

    if user_query:
        # Display user message
        st.session_state.messages.append({"role": "user", "content": user_query, "sources": []})
        with st.chat_message("user"):
            st.markdown(user_query)

        # Assistant response
        with st.chat_message("assistant"):
            with st.spinner("Searching IBM Db2 Vector embeddings..."):
                response = rag_engine.answer_question(user_query)
                st.markdown(response["answer"])

                if response.get("sources"):
                    with st.expander(f"🔍 Db2 Vector Citations ({response['retrieved_count']} chunks)"):
                        for src in response["sources"]:
                            st.markdown(
                                f"**{src['section_title']}** `({src['topic']})` "
                                f"{'• Cosine Score: ' + str(src['score']) if src.get('score') else ''}"
                            )
                            st.caption(src.get("snippet", ""))

                st.caption(f"Synthesized by: `{response['provider']}` | Vector Store: `{response['db2_table']}`")

        st.session_state.messages.append({
            "role": "assistant",
            "content": response["answer"],
            "sources": response.get("sources", [])
        })

# TAB 2: Notes & Vector Explorer
with tab2:
    st.subheader("📚 Notes & Vector Embeddings Explorer")
    st.write("Inspect how the lecture notes are chunked and mapped into IBM Db2 vector columns.")

    notes_file = Path(__file__).resolve().parent.parent / "data" / "notes.md"
    if notes_file.is_file():
        chunker = StudentNotesChunker(
            chunk_size=Db2RAGConfig.CHUNK_SIZE,
            chunk_overlap=Db2RAGConfig.CHUNK_OVERLAP
        )
        sample_docs = chunker.process_file(str(notes_file))

        col1, col2, col3 = st.columns(3)
        col1.metric("Total Chunks Indexed", len(sample_docs))
        col2.metric("Embedding Dimension", f"{Db2RAGConfig.EMBEDDING_DIM}-dim")
        col3.metric("Storage Table", Db2RAGConfig.DB2_TABLE_NAME)

        search_filter = st.text_input("Filter notes by keyword or formula symbol:")
        filtered_docs = [
            d for d in sample_docs
            if not search_filter or search_filter.lower() in d.page_content.lower()
        ]

        st.write(f"Showing **{len(filtered_docs)}** matching passages:")
        for doc in filtered_docs[:10]:
            with st.expander(f"📌 {doc.metadata.get('section_title')} ({doc.metadata.get('topic')})"):
                st.markdown(doc.page_content)
                st.json(doc.metadata)
    else:
        st.info("Notes file not found at data/notes.md.")

# TAB 3: Architecture & Db2 Metrics
with tab3:
    st.subheader("🏗️ Architecture & IBM Db2 Vector Search Design")
    st.markdown("""
    ### System Architecture Flow:
    1. **Document Ingestion**: Markdown study notes are segmented into semantic chunks preserving mathematical equations and Markdown headers.
    2. **Vector Embeddings**: Passages are embedded using HuggingFace `sentence-transformers/all-mpnet-base-v2` (768 dimensions) or `all-MiniLM-L6-v2`.
    3. **IBM Db2 Storage**: Chunks and vectors are stored into IBM Db2 using `langchain-db2` with native `VECTOR(768, FLOAT32)` column type and `COSINE` distance indexing.
    4. **Similarity Retrieval**: When a student enters a query, Db2 performs native SQL vector similarity search via `VECTOR_DISTANCE` and returns top-k nearest notes.
    5. **Multi-Model LLM Generation**: Grounded context notes are provided to watsonx.ai Granite (or Gemini / Ollama / OpenAI) with an exam-focused instruction template.
    """)

    st.markdown("""
    ### Db2 Schema Definition:
    ```sql
    CREATE TABLE STUDENT_NOTES_VS (
        ID VARCHAR(64) NOT NULL PRIMARY KEY,
        TEXT CLOB(1M),
        METADATA CLOB(64K),
        EMBEDDING VECTOR(768, FLOAT32)
    );
    ```
    """)

