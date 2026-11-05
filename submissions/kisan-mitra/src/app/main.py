"""
Kisan Mitra (किसान मित्र) - Streamlit Web Dashboard
IBM Db2Hack 2026 Submission
Features:
- Bilingual interface (Hindi / English)
- Text-to-SQL over IBM Db2 Mandi Prices
- Native Vector Search (VECTOR_DISTANCE) over Official Welfare Scheme PDFs
- Gramin Mitra (ग्रामीण मित्र) AI mode for illiterate & neo-literate farmers:
  * Plain-language village conversational explanations (ग्राम चौपाल शैली)
  * Real High-Fidelity Audio Playback (st.audio with gTTS & macOS offline fallback)
- Transparent SQL query inspector, execution latency badge, and interactive Plotly charts
- Document citation cards with page numbers and cosine distance metrics
"""

import os
import sys
from pathlib import Path

# Add project root directory to sys.path so 'app' package is always resolvable by Streamlit
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import json
import time
import pandas as pd
import plotly.io as pio
import streamlit as st

from app.config import config
from app.db_client import get_db_client
from app.agents.router import get_router
from app.agents.rural_agent import get_rural_agent
from app.agents.audio_service import generate_speech_audio

# Page Configuration
st.set_page_config(
    page_title="Kisan Mitra (किसान मित्र) - IBM Db2 AI Assistant",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1B4D3E 0%, #2E7D32 100%);
        color: white;
        padding: 24px;
        border-radius: 12px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-header h1 {
        color: #FFFFFF !important;
        margin: 0 0 8px 0;
        font-size: 2.2rem;
        font-weight: 700;
    }
    .main-header p {
        color: #E8F5E9 !important;
        margin: 0;
        font-size: 1.05rem;
    }
    .badge-db2 {
        background-color: #052F5F;
        color: #FFFFFF;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        display: inline-block;
        margin-right: 6px;
    }
    .badge-sql {
        background-color: #0288D1;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .badge-rag {
        background-color: #388E3C;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .badge-hybrid {
        background-color: #7B1FA2;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
    }
    .badge-rural {
        background-color: #E65100;
        color: white;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: bold;
    }
    .citation-card {
        background: #F1F8E9;
        border-left: 4px solid #4CAF50;
        padding: 10px 14px;
        margin: 6px 0;
        border-radius: 4px;
        font-size: 0.9rem;
    }
    .voice-hint-box {
        background: #FFF8E1;
        border-left: 4px solid #FFA000;
        padding: 10px 14px;
        margin: 12px 0;
        border-radius: 6px;
        font-size: 0.95rem;
        color: #5D4037;
    }
</style>
""", unsafe_allow_html=True)

# Localization Strings
UI_STRINGS = {
    "hi": {
        "title": "🌾 किसान मित्र (Kisan Mitra)",
        "subtitle": "IBM Db2 चालित भारत के किसानों के लिए AI सहायक",
        "tagline": "मंडी भाव (Text-to-SQL) & सरकारी योजनाएं (Native Db2 Vector Search)",
        "input_placeholder": "अपना सवाल पूछें या बोलें (उदा. 'मथुरा मंडी में आलू का भाव', 'फसल खराब हो गई तो क्या करें')...",
        "quick_header": "💡 आम बोलचाल के सवाल (Quick Rural Prompts):",
        "chat_header": "💬 किसान संवाद (Farmer Consultation)",
        "db2_badge": "IBM Db2 12.1+ AI Powered",
        "sql_inspect": "🔍 IBM Db2 SQL क्वेरी पारदर्शकता (Query Inspector)",
        "sources_inspect": "📚 आधिकारिक सरकारी दिशानिर्देश उद्धरण (Official Citations)",
        "chart_title": "📊 मंडी मूल्य विश्लेषण (Mandi Price Analytics)",
        "send_btn": "पूछें 🚀",
        "clear_btn": "चैट साफ़ करें 🗑️",
        "mode_rural": "🌾 सरल ग्रामीण मोड (Farmer / Audio Mode)",
        "mode_officer": "📊 विस्तृत अधिकारी मोड (Officer / Analytics Mode)",
        "voice_hint": "🔊 <b>आवाज़ में सुनने की सुविधा:</b> हर उत्तर के नीचे दिए गए ऑडियो प्लेयर में <b>'▶️ Play'</b> बटन दबाएं और साफ आवाज़ में पूरा जवाब सुनें!",
    },
    "en": {
        "title": "🌾 Kisan Mitra",
        "subtitle": "Bilingual AI Assistant for Indian Farmers powered by IBM Db2",
        "tagline": "Mandi Market Rates (Text-to-SQL) & Scheme Advisory (Native Db2 Vector RAG)",
        "input_placeholder": "Ask or speak your question (e.g., 'Mathura potato rate today', 'Crop damaged what to do')...",
        "quick_header": "💡 Common Voice & Colloquial Questions:",
        "chat_header": "💬 Farmer Consultation Chat",
        "db2_badge": "IBM Db2 12.1+ AI Powered",
        "sql_inspect": "🔍 IBM Db2 SQL Query Inspector (Transparency)",
        "sources_inspect": "📚 Official Government Policy Citations (Grounding)",
        "chart_title": "📊 Mandi Price Analytics",
        "send_btn": "Ask 🚀",
        "clear_btn": "Clear Chat 🗑️",
        "mode_rural": "🌾 Simple Rural Farmer Mode (Voice Enabled)",
        "mode_officer": "📊 Detailed Officer / Analyst Mode",
        "voice_hint": "🔊 <b>Voice Narration Enabled:</b> Press the <b>'▶️ Play'</b> button on the audio player below each answer to listen aloud.",
    }
}

# Session State Initialization
if "lang" not in st.session_state:
    st.session_state.lang = "hi"
if "user_mode" not in st.session_state:
    st.session_state.user_mode = "rural"
if "autoplay_voice" not in st.session_state:
    st.session_state.autoplay_voice = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "router" not in st.session_state:
    st.session_state.router = get_router()
if "rural_agent" not in st.session_state:
    st.session_state.rural_agent = get_rural_agent()
if "db" not in st.session_state:
    st.session_state.db = get_db_client(read_only=True)

S = UI_STRINGS[st.session_state.lang]


def render_audio_widget(speech_text: str, meta: dict, lang: str = "hi", autoplay: bool = False):
    """
    Renders high-fidelity audio player using native Streamlit st.audio().
    Works 100% reliably in all browsers without iframe sandbox restrictions.
    """
    if not speech_text:
        return
        
    audio_bytes = meta.get("audio_bytes")
    mime_type = meta.get("audio_mime", "audio/mp3")
    
    if not audio_bytes:
        audio_bytes, mime_type = generate_speech_audio(speech_text, lang=lang)
        if audio_bytes:
            meta["audio_bytes"] = audio_bytes
            meta["audio_mime"] = mime_type

    if audio_bytes:
        label = "🔊 **आवाज़ में सुनें (Audio Playback):**" if lang == "hi" else "🔊 **Listen to Answer (Audio):**"
        st.markdown(label)
        st.audio(audio_bytes, format=mime_type, autoplay=autoplay)


def safe_render_table(rows: list):
    """Safely renders tabular records with st.dataframe and graceful st.table fallback."""
    if not rows:
        return
    try:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
    except Exception:
        try:
            df = pd.DataFrame(rows)
            st.table(df)
        except Exception:
            pass


# -----------------------------------------------------------------------------
# SIDEBAR
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg", width=110)
    st.subheader("⚙️ Settings & System Status")
    
    # Mode Selector
    mode_choice = st.radio(
        "👤 उपयोगकर्ता मोड (User Experience Mode):",
        options=["rural", "officer"],
        format_func=lambda x: S["mode_rural"] if x == "rural" else S["mode_officer"],
        index=0 if st.session_state.user_mode == "rural" else 1
    )
    if mode_choice != st.session_state.user_mode:
        st.session_state.user_mode = mode_choice
        st.rerun()

    # Language Selector
    lang_choice = st.radio(
        "🌐 भाषा / Language:",
        options=["hi", "en"],
        format_func=lambda x: "हिंदी (Hindi)" if x == "hi" else "English",
        index=0 if st.session_state.lang == "hi" else 1,
        horizontal=True
    )
    if lang_choice != st.session_state.lang:
        st.session_state.lang = lang_choice
        st.rerun()

    # Auto-play audio toggle
    auto_voice = st.checkbox(
        "🔊 उत्तर आते ही खुद बोलें (Auto-Play Audio)" if st.session_state.lang == "hi" else "🔊 Auto-Play Audio Response",
        value=st.session_state.autoplay_voice
    )
    st.session_state.autoplay_voice = auto_voice

    st.markdown("---")
    
    # Database Status
    st.markdown("### 🗄️ IBM Db2 Status")
    engine_name = "IBM Db2 Native" if st.session_state.db.engine_type == "native_db2" else "Db2 Emulation Engine"
    st.success(f"**Connected**: {engine_name}")
    
    # Live Counts
    try:
        cnt_res = st.session_state.db.execute_query("SELECT COUNT(*) AS total FROM MANDI_PRICES")
        mandi_cnt = cnt_res["rows"][0]["total"] if cnt_res["rows"] else 0
        
        vec_res = st.session_state.db.execute_query("SELECT COUNT(*) AS total FROM DOC_CHUNKS")
        chunks_cnt = vec_res["rows"][0]["total"] if vec_res["rows"] else 0
    except Exception:
        mandi_cnt, chunks_cnt = 0, 0

    st.metric("🌾 Mandi Price Records", f"{mandi_cnt:,}")
    st.metric("📄 Db2 Vector Chunks (384d)", f"{chunks_cnt:,}")

    st.markdown("---")
    st.markdown("### 🔒 Security Guardrails")
    st.info(
        "**Role**: `kisan_ro` (Read-Only User)\n\n"
        "**Permissions**: `SELECT` ONLY\n\n"
        "**Guarantees**: DDL/DML mutation queries (`INSERT`, `UPDATE`, `DROP`, `DELETE`) are strictly rejected at the AST parser level."
    )

    st.markdown("---")
    st.markdown("### 🤖 Model Architecture")
    st.text(f"LLM: {config.LLM_PROVIDER.upper()}")
    st.text(f"Embeddings: MiniLM-384d")
    st.text(f"Db2 Vectors: VECTOR(384, REAL)")
    st.text(f"Audio Engine: Native Streamlit TTS")
    
    if st.button(S["clear_btn"], use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# -----------------------------------------------------------------------------
# MAIN CONTENT AREA
# -----------------------------------------------------------------------------
st.markdown(f"""
<div class="main-header">
    <h1>{S["title"]}</h1>
    <p>{S["subtitle"]} &bull; <b>{S["tagline"]}</b></p>
    <div style="margin-top: 10px;">
        <span class="badge-db2">IBM Db2 12.1+</span>
        <span class="badge-db2">LangChain</span>
        <span class="badge-db2">Native Vector Search</span>
        <span class="badge-db2">Text-to-SQL</span>
        <span class="badge-rural">🌾 ग्रामीण मित्र (Voice AI)</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Voice Hint Banner
st.markdown(f"""
<div class="voice-hint-box">
    {S["voice_hint"]}
</div>
""", unsafe_allow_html=True)

# Quick Prompts tailored for both Rural and Analytical scenarios
st.markdown(f"##### {S['quick_header']}")
col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🥔 मथुरा मंडी में आलू का क्या भाव है?", use_container_width=True):
        st.session_state.pending_query = "Mathura mandi me aaj aloo ka bhav kya hai?"
    if st.button("🌧️ खेत में पानी भर गया, नुकसान का पैसा कैसे मिलेगा?", use_container_width=True):
        st.session_state.pending_query = "khet me paani bhar gya fasal kharab ho gayi to claim kaise karein"

with col2:
    if st.button("💰 6000 वाली किस्त का पैसा कब और कैसे मिलता है?", use_container_width=True):
        st.session_state.pending_query = "6000 wali kist PM-KISAN ka paisa kaise milta hai aur kon aavedan nahi kar sakta?"
    if st.button("💳 केसीसी (KCC) से बिना गारंटी 4% ब्याज पर लोन कैसे लें?", use_container_width=True):
        st.session_state.pending_query = "KCC yojana me 4% byaj par bina zameen guarantee loan kaise milta hai?"

with col3:
    if st.button("🌾 UP में पिछले हफ्ते सबसे महंगा अनाज कौनसा था?", use_container_width=True):
        st.session_state.pending_query = "UP me pichhle hafte sabse mehnga kaunsa anaaj tha?"
    if st.button("⚡ आगरा में गेहूं का भाव और बीमा क्लेम दोनों बताएं", use_container_width=True):
        st.session_state.pending_query = "Agra me gehun ka kya bhav hai aur fasal kharab hone par PMFBY claim kaise karein?"

st.markdown("---")

# Render Conversation History
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"], avatar="👨‍🌾" if msg["role"] == "user" else "🌾"):
        st.markdown(msg["content"])
        
        # If response has metadata
        if "meta" in msg:
            meta = msg["meta"]
            intent = meta.get("intent", "SQL")
            speech_text = meta.get("speech_text", "")
            
            # Voice Audio Player
            if speech_text:
                render_audio_widget(speech_text, meta, lang=st.session_state.lang, autoplay=False)

            # Intent Badge
            badge_class = f"badge-{intent.lower()}"
            st.markdown(f"<span class='{badge_class}'>Intent: {intent}</span>", unsafe_allow_html=True)
            
            # If in Rural Mode, collapse advanced database internals in an expander
            is_rural = (st.session_state.user_mode == "rural")
            
            # SQL Query Transparency Inspector
            if meta.get("generated_sql"):
                expander_label = f"🔍 {S['sql_inspect']} (Latency: {meta.get('latency_ms', 0)} ms)"
                with st.expander(expander_label, expanded=not is_rural):
                    st.code(meta["generated_sql"], language="sql")
                    if meta.get("rows"):
                        safe_render_table(meta["rows"])
            
            # Interactive Plotly Chart
            if meta.get("chart_json"):
                with st.expander(S["chart_title"], expanded=not is_rural):
                    fig = pio.from_json(meta["chart_json"])
                    st.plotly_chart(fig, use_container_width=True)

            # Sources & Citations Panel (RAG)
            if meta.get("sources"):
                with st.expander(f"{S['sources_inspect']} ({len(meta['sources'])} Citations)", expanded=not is_rural):
                    for s in meta["sources"]:
                        st.markdown(f"""
                        <div class="citation-card">
                            <b>📄 {s['doc_name']}</b> &bull; <b>पृष्ठ (Page) {s['page_number']}</b> &bull; 
                            <i>Cosine Distance: {s['distance']}</i> (Similarity: {int((1-s['distance'])*100)}%)<br/>
                            <small>{s['snippet']}</small>
                        </div>
                        """, unsafe_allow_html=True)

# Handle Query Input
user_query = st.chat_input(S["input_placeholder"])

# Check for button click prompt
if getattr(st.session_state, "pending_query", None):
    user_query = st.session_state.pending_query
    st.session_state.pending_query = None

if user_query:
    # 1. Add user message
    st.session_state.messages.append({"role": "user", "content": user_query})
    
    with st.chat_message("user", avatar="👨‍🌾"):
        st.markdown(user_query)

    # 2. Process query via Kisan Mitra Router & Rural Conversational Agent
    with st.chat_message("assistant", avatar="🌾"):
        with st.spinner("विचार कर रहा हूँ / Analyzing on IBM Db2..."):
            # Normalize colloquial rural terms if needed
            normalized_query = st.session_state.rural_agent.normalize_rural_query(user_query)
            result = st.session_state.router.run(normalized_query)
            
            raw_answer = result.get("answer", "")
            
            # If in Rural Mode, transform technical/bureaucratic text into warm village format
            if st.session_state.user_mode == "rural":
                display_answer = st.session_state.rural_agent.simplify_for_farmer(
                    user_query, raw_answer, result.get("intent", "GENERAL")
                )
            else:
                display_answer = raw_answer

            speech_text = st.session_state.rural_agent.to_speech_text(display_answer)
            result["speech_text"] = speech_text
            result["simplified_answer"] = display_answer

        # Display answer
        st.markdown(display_answer)
        
        # Audio Player (renders native HTML5 st.audio player)
        render_audio_widget(
            speech_text, 
            result, 
            lang=st.session_state.lang, 
            autoplay=st.session_state.autoplay_voice
        )

        # Intent Badge
        intent = result.get("intent", "SQL")
        badge_class = f"badge-{intent.lower()}"
        st.markdown(f"<span class='{badge_class}'>Intent: {intent}</span>", unsafe_allow_html=True)
        
        is_rural = (st.session_state.user_mode == "rural")
        
        # Display SQL Inspector
        if result.get("generated_sql"):
            with st.expander(f"🔍 {S['sql_inspect']} (Latency: {result.get('latency_ms', 0)} ms)", expanded=not is_rural):
                st.code(result["generated_sql"], language="sql")
                if result.get("rows"):
                    safe_render_table(result["rows"])
        
        # Display Interactive Plotly Chart
        if result.get("chart_json"):
            with st.expander(S["chart_title"], expanded=not is_rural):
                fig = pio.from_json(result["chart_json"])
                st.plotly_chart(fig, use_container_width=True)

        # Display Document Citations
        if result.get("sources"):
            with st.expander(f"{S['sources_inspect']} ({len(result['sources'])} Citations)", expanded=not is_rural):
                for s in result["sources"]:
                    st.markdown(f"""
                    <div class="citation-card">
                        <b>📄 {s['doc_name']}</b> &bull; <b>पृष्ठ (Page) {s['page_number']}</b> &bull; 
                        <i>Cosine Distance: {s['distance']}</i> (Similarity: {int((1-s['distance'])*100)}%)<br/>
                        <small>{s['snippet']}</small>
                    </div>
                    """, unsafe_allow_html=True)

        # Append assistant message with metadata
        st.session_state.messages.append({
            "role": "assistant",
            "content": display_answer,
            "meta": result
        })
