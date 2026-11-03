import io
import json
import html
import hashlib
import zipfile
import csv
import os
import re
import shutil
import tempfile
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Ensure the project root is importable when Streamlit runs this app.py.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rasa_auth import (
    begin_registration, verify_registration, authenticate,
    begin_password_reset, finish_password_reset,
)

import streamlit as st
from pypdf import PdfReader

try:
    from src.smart_audition_search import search_auditions as haystack_search_auditions
    HAYSTACK_SEARCH_IMPORT_ERROR = None
except Exception as exc:
    haystack_search_auditions = None
    HAYSTACK_SEARCH_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"

st.set_page_config(page_title="RASA AI | Casting Performance Analysis", page_icon="🎬", layout="wide")

st.markdown("""
<style>
:root {
    color-scheme: dark;
}
.stApp {
    background:
        radial-gradient(ellipse at 10% 0%, rgba(77, 91, 190, 0.14), transparent 38%),
        linear-gradient(145deg, #0b0f17 0%, #101521 52%, #0b1018 100%);
    color: #edf2ff;
}
.block-container {
    max-width: 1450px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}
h1, h2, h3, h4 {
    color: #f4f6ff !important;
    letter-spacing: -0.025em;
}
h1 {
    font-weight: 800 !important;
    font-size: clamp(2.5rem, 5vw, 3.6rem) !important;
    background: linear-gradient(90deg, #ffffff 0%, #b9c8ff 55%, #83e5dc 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    padding-bottom: .15rem;
}
h2 {
    font-weight: 720 !important;
    border-bottom: 1px solid rgba(148, 163, 184, .2);
    padding-bottom: .55rem;
    margin-top: 1.1rem !important;
}
h3 {
    font-weight: 650 !important;
}
p, label, .stMarkdown, .stCaption, [data-testid="stWidgetLabel"] {
    color: #d4dced;
}
[data-testid="stCaptionContainer"] p {
    color: #9eabc2 !important;
}
[data-testid="stAlert"] {
    border-radius: 14px;
    border: 1px solid rgba(129, 153, 205, .22);
}
div[data-testid="stTabs"] > div:first-child {
    gap: .4rem;
    border-bottom: 1px solid rgba(148, 163, 184, .22);
}
div[data-testid="stTabs"] button[role="tab"] {
    color: #b8c5dc;
    background: rgba(255,255,255,.025);
    border-radius: 10px 10px 0 0;
    padding: .75rem 1rem;
    font-weight: 650;
    transition: all .18s ease;
}
div[data-testid="stTabs"] button[role="tab"]:hover {
    color: #ffffff;
    background: rgba(125, 145, 255, .10);
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #ffffff;
    background: linear-gradient(180deg, rgba(108, 128, 255, .18), rgba(108, 128, 255, .05));
    border-bottom: 3px solid #8ea0ff;
}
div[data-testid="stTabs"] [data-testid="stTabContent"] {
    padding-top: 1.25rem;
}
div[data-testid="stExpander"] {
    border: 1px solid rgba(148, 163, 184, .22);
    border-radius: 12px;
    background: rgba(255,255,255,.025);
}
.stButton > button, .stDownloadButton > button {
    border-radius: 10px;
    border: 1px solid rgba(151, 166, 255, .45);
    background: linear-gradient(135deg, #5969d9, #4253b7);
    color: white;
    font-weight: 650;
    padding: .55rem 1rem;
    transition: transform .15s ease, filter .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    border-color: #aab5ff;
    filter: brightness(1.12);
    transform: translateY(-1px);
}
input, textarea, [data-baseweb="select"] > div {
    border-radius: 10px !important;
}
hr {
    border-color: rgba(148, 163, 184, .18);
}
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border: 1px solid rgba(148, 163, 184, .18);
    border-radius: 12px;
    overflow: hidden;
}
</style>

""", unsafe_allow_html=True)


# ---------- RASA AI Private Vault authentication + public introduction ----------
def _render_intro_page():
    # One continuous, scrollable introduction panel matching the Detective AI layout.
    intro_html = f"""
    <div class="detective-intro-panel">
      <h1>🎬 RASA AI: Audition Intelligence &amp; Casting Support</h1>
      <p class="intro-lead">
        RASA AI helps filmmakers and casting teams organize screenplay context, define role
        requirements, inspect observable visual and vocal evidence, compare auditions, and
        retrieve saved audition records.
      </p>
      <p>
        Audition evaluation can involve fragmented information across screenplays, role briefs,
        video recordings, audio recordings and reviewer notes. RASA AI brings these materials
        together into a structured workflow so qualified reviewers can inspect evidence, compare
        auditions and document their decisions.
      </p>
      <p>
        The platform combines deterministic screenplay cue extraction, local computer-vision
        measurements, optional audio analysis, audition-library management and Haystack 2.x
        BM25 keyword retrieval. Db2 is an optional integration and is not required to use RASA AI.
      </p>

      <h2 class="restricted-heading">CAUTION: RESTRICTED ACCESS — AUTHORIZED USERS ONLY</h2>
      <p>This platform is designed with privacy and confidentiality as core principles.</p>
      <ul class="privacy-list">
        <li><b>Private Vault:</b> Each registered user has a separate account and local data area
          for their audition records and reports.</li>
        <li><b>Secure Authentication:</b> Access requires a registered Gmail ID and a unique
          RASA AI password. New accounts require email OTP verification.</li>
        <li><b>Data Confidentiality:</b> Account-specific audition libraries, activity logs and
          report data are stored separately on the machine running RASA AI.</li>
        <li><b>Restricted Access:</b> The application separates users' records by account. Keep
          the host computer, backups and account credentials secure.</li>
        <li><b>Local-first operation:</b> Db2 is optional. Users who choose the Db2 integration
          must configure access to their own Db2 instance.</li>
      </ul>
      <p><b>IMPORTANT:</b> Users are responsible for ensuring that they have the necessary legal
        authority, permissions and consent before uploading, processing or analyzing audition
        recordings, screenplay materials or personal information.</p>
      <p>
        RASA AI is a human decision-support tool. Computer-vision measurements, optional
        expression labels, vocal features and text-retrieval scores are experimental signals —
        not validated measures of acting quality, personality, emotion, diagnosis or role
        suitability. Casting decisions must remain with qualified human reviewers.
      </p>
      <p><b>By accessing this platform, you agree to use audition materials responsibly,
        ethically and in accordance with applicable laws.</b></p>

      <h2>THE MEANING OF RASA</h2>
      <p>
        In the context of <b>Navarasa</b>, <b>Rasa</b> (Sanskrit for “essence,” “juice” or “taste”)
        refers to the aesthetic flavour or emotional experience evoked in the spectator by a work
        of art. It is distinct from <i>Bhava</i>, the emotion expressed by the performer; Rasa is
        the refined sentiment tasted and relished by the audience.
      </p>
      <h2>NAVARASA — THE NINE HUMAN EXPRESSIONS</h2>
      <p>
        Navarasa literally means “nine rasas,” representing nine fundamental aesthetic moods
        associated with the <i>Natyashastra</i> tradition.
      </p>
      <div class="rasa-grid">
        <div><b>Shringara</b><span>Love / Beauty</span></div>
        <div><b>Hasya</b><span>Laughter / Joy</span></div>
        <div><b>Karuna</b><span>Compassion / Sorrow</span></div>
        <div><b>Raudra</b><span>Anger / Fury</span></div>
        <div><b>Veera</b><span>Heroism / Courage</span></div>
        <div><b>Bhayanaka</b><span>Fear / Terror</span></div>
        <div><b>Bibhatsa</b><span>Disgust / Aversion</span></div>
        <div><b>Adbhuta</b><span>Wonder / Amazement</span></div>
        <div><b>Shanta</b><span>Peace / Tranquility</span></div>
      </div>
      <p class="muted-note">
        The original Natyashastra described eight rasas; Shanta was added by later aestheticians
        and became part of the Navarasa framework.
      </p>

      <h2>RASA AI CAPABILITIES</h2>
      <h3>1. Screenplay analysis</h3>
      <ul>
        <li>Enter a story or screenplay as text, or upload a text-based PDF.</li>
        <li>Extract selectable PDF text using pypdf.</li>
        <li>Use deterministic, rule-based analysis to identify role and scene cues.</li>
        <li>Review character candidates and suggested audition tests; download analysis as JSON.</li>
      </ul>
      <h3>2. Character cues and role requirements</h3>
      <ul>
        <li>Inspect candidate characters and cues extracted from the screenplay.</li>
        <li>Define role requirements and a character emotion-performance brief for human review.</li>
        <li>Keep intended portrayal separate from any optional model-generated visual label.</li>
      </ul>
      <h3>3. Video analysis</h3>
      <ul>
        <li>Upload an audition video and label the actor or audition.</li>
        <li>Run local computer-vision analysis on sampled video frames.</li>
        <li>Review observable pose/movement and facial-geometry features when landmarks are visible.</li>
        <li>Inspect timestamped observations and evidence-quality notes.</li>
        <li>Optional FER expression labels may be available if the package/model is installed.</li>
      </ul>
      <p>
        Video measurements are sensitive to lighting, framing, camera angle, occlusion, speech,
        tracking quality and scene context. Facial geometry values are not emotion labels.
      </p>
      <h3>4. Vocal analysis</h3>
      <ul>
        <li>Run experimental audio-only analysis when the required audio tools are installed.</li>
        <li>Inspect acoustic summaries, pitch and signal-energy patterns where available.</li>
        <li>Review timestamped vocal evidence and download output as JSON.</li>
      </ul>
      <p>Vocal measurements are acoustic features, not reliable detectors of emotion, intent or acting ability.</p>
      <h3>5. Combined evidence timeline</h3>
      <p>Combine current-session video and vocal evidence on a shared timeline. Timestamps are review aids, not automated judgments.</p>
      <h3>6. Audition library and comparison</h3>
      <ul>
        <li>Save and review audition reports locally within the signed-in user's private data area.</li>
        <li>Compare auditions and filter by text, character, review status and shortlist state where available.</li>
        <li>Add reviewer decisions, shortlist markers and reviewer notes; export records where offered.</li>
        <li>Shortlisting is human-managed, not an automated casting recommendation.</li>
      </ul>
      <h3>7. Haystack retrieval</h3>
      <ul>
        <li>Search saved audition reports with Haystack 2.x BM25 keyword retrieval.</li>
        <li>Filter by character, review status and shortlisted-only state.</li>
        <li>Inspect retrieved records and BM25 scores; export current results to CSV.</li>
      </ul>
      <p>BM25 scores represent textual relevance, not acting quality, role fit or probability of success.</p>
      <h3>8. Db2 database integration — optional</h3>
      <p>
        RASA AI works without Db2. Users who want this optional connector must have access to
        their own Db2 instance and configure valid connection details. The initial connector
        targets Db2 LUW-style catalog queries; compatibility must be confirmed with the chosen service.
      </p>
      <h2>APPLICATION WORKFLOW</h2>
      <ol>
        <li>Add a screenplay or story.</li>
        <li>Review character cues and define role requirements.</li>
        <li>Upload and analyze an audition video.</li>
        <li>Optionally analyze audition audio.</li>
        <li>Inspect the evidence timeline and compare auditions.</li>
        <li>Add reviewer notes, review status and shortlist decisions.</li>
        <li>Use Haystack Retrieval to find saved records.</li>
        <li>Optionally configure Db2 and manually sync audition records.</li>
      </ol>
      <h2>TECHNOLOGY STACK</h2>
      <p><b>Python · Streamlit · pypdf · OpenCV · MediaPipe · NumPy · librosa (optional) ·
      FER (optional) · Haystack 2.x · ibm_db</b></p>
      <p class="muted-note">
        Current screenplay analysis is deterministic/rule-based. Haystack retrieval is BM25
        keyword search and does not require an LLM.
      </p>
      <h2>OPTIONAL DB2 SETUP</h2>
      <p>
        Configure Db2 only if you want to use the optional database tab. Use the host, port,
        database, username, password and TLS instructions supplied by your Db2 provider.
        Do not commit credentials or share passwords.
      </p>
      <pre>$env:DB2_HOST = "your-db2-host"
$env:DB2_PORT = "50000"
$env:DB2_DATABASE = "your-database"
$env:DB2_USER = "your-username"
$env:DB2_PASSWORD = "your-password"
$env:DB2_SSL = "true"</pre>
      <ol>
        <li>Start RASA AI with <code>streamlit run app.py</code>.</li>
        <li>Open <b>Db2 Database</b> and check the connection.</li>
        <li>Initialize the audition table.</li>
        <li>Sync the local audition library to Db2.</li>
        <li>Load recent Db2 records to inspect read-back.</li>
      </ol>
      <p class="muted-note">
        Do not treat the Db2 connector as production-ready until connection, schema creation,
        synchronization and read-back have been tested against the real instance.
      </p>
      <p class="closing-line">JAI HIND IN</p>
    </div>
    """
    # Render the complete introduction as one balanced HTML block.
    # Normalize indentation so HTML is rendered as markup, not as a code block.
    intro_html = "\n".join(line.lstrip() for line in intro_html.splitlines()).strip()
    st.markdown(intro_html, unsafe_allow_html=True)


# Detective AI-inspired layout: fixed-width left vault sidebar + one long intro card.
st.markdown("""
<style>
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg,#191d26 0%,#121720 100%);
    border-right: 1px solid rgba(133,157,205,.16);
    width: 370px;
}
section[data-testid="stSidebar"] > div { padding: 2.1rem 1.15rem 1.5rem; }
section[data-testid="stSidebar"][aria-expanded="false"] {
    width: 0 !important;
    min-width: 0 !important;
    margin-left: 0 !important;
}
section[data-testid="stSidebar"][aria-expanded="false"] > div {
    width: 0 !important;
    min-width: 0 !important;
    overflow: hidden !important;
}
.block-container {
    max-width: none;
    width: 100%;
    padding-top: 5.1rem;
    padding-bottom: 3rem;
    padding-left: 3.5rem;
    padding-right: 3.5rem;
}
.stImage img { width: min(100%, 860px) !important; height: auto !important; object-fit: contain; }
.detective-intro-panel {
    background: linear-gradient(145deg,#0e131b 0%,#0b1017 100%);
    border: 1px solid rgba(132,145,165,.19);
    border-radius: 24px;
    padding: 48px 42px 54px;
    color: #f5f7fb;
    font-size: 1.04rem;
    line-height: 1.9;
    overflow-wrap: anywhere;
}
.detective-intro-panel h1 {
    color:#f8f9fc; font-size:clamp(2.15rem,3.1vw,3.25rem);
    line-height:1.13; font-weight:850; letter-spacing:-.035em;
    margin:0 0 2.7rem; border:0;
}
.detective-intro-panel h2 {
    color:#f4f6fb; font-size:2rem; font-weight:800;
    line-height:1.2; margin:2.6rem 0 1rem; border:0;
}
.detective-intro-panel h3 {
    color:#e9efff; font-size:1.22rem; font-weight:750;
    margin:1.6rem 0 .35rem;
}
.detective-intro-panel p { color:#edf1f8; margin:.75rem 0 1.1rem; }
.detective-intro-panel .intro-lead { font-size:1.12rem; }
.detective-intro-panel .restricted-heading {
    color:#ffad9e; font-size:clamp(1.55rem,2.5vw,2.35rem);
    letter-spacing:.025em; margin-top:3rem; white-space:normal;
}
.detective-intro-panel ul,.detective-intro-panel ol {
    padding-left:1.8rem; margin:1rem 0 1.5rem;
}
.detective-intro-panel li { padding-left:.25rem; margin:.7rem 0; color:#edf1f8; }
.detective-intro-panel b { color:#fff; }
.detective-intro-panel .rasa-grid {
    display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.65rem;
    margin:1.2rem 0;
}
.detective-intro-panel .rasa-grid div {
    display:flex; flex-direction:column; gap:.1rem;
    border:1px solid rgba(132,157,207,.24); border-radius:12px;
    padding:.8rem 1rem; background:rgba(29,41,60,.45);
}
.detective-intro-panel .rasa-grid span,.detective-intro-panel .muted-note {
    color:#9aa8bd; font-size:.9rem;
}
.detective-intro-panel .closing-line { color:#ffcf54; font-weight:850; letter-spacing:.04em; margin-top:2rem; }
.detective-intro-panel pre {
    white-space:pre-wrap; padding:1rem 1.2rem; border-radius:10px;
    background:#171d28; border:1px solid rgba(132,157,207,.24); color:#dce7fb;
}
.vault-brand { padding:.4rem .1rem 1.4rem; margin-bottom:.6rem; }
.vault-card {
    background:linear-gradient(145deg,#111821,#0c1118);
    border:1px solid rgba(132,145,165,.17); border-radius:22px;
    padding:1.15rem 1.2rem; margin:.7rem 0 1.8rem;
}
.vault-card p { color:#e0e6ef; font-size:.94rem; line-height:1.7; margin:.6rem 0 0; }
.vault-card .vault-badge {
    display:inline-block; color:#f3f6ff; font-size:.78rem; font-weight:800;
    letter-spacing:.04em; padding:.45rem .85rem; border-radius:22px;
    border:1px solid rgba(110,145,205,.38); background:#202a3a;
}
section[data-testid="stSidebar"] h2 { font-size:1.35rem; }
section[data-testid="stSidebar"] label { color:#f1f4fa; }
section[data-testid="stSidebar"] input {
    background:#171c25 !important; border:1px solid rgba(132,145,165,.18) !important;
    border-radius:12px !important; min-height:3rem;
}
section[data-testid="stSidebar"] div.stButton > button,
section[data-testid="stSidebar"] div.stFormSubmitButton > button {
    min-height:3.35rem; border-radius:16px; border:1px solid rgba(132,145,165,.2);
    background:linear-gradient(145deg,#20242d,#1a1e26); color:#fff;
    font-weight:650;
}
@media (max-width: 900px) {
  section[data-testid="stSidebar"] { width:300px; }
  .block-container { padding-left:1rem; padding-right:1rem; padding-top:2rem; }
  .detective-intro-panel { padding:1.5rem; }
  .detective-intro-panel .rasa-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
</style>
""", unsafe_allow_html=True)

if "rasa_user" not in st.session_state:
    st.session_state["rasa_user"] = None

if not st.session_state["rasa_user"]:
    with st.sidebar:
        st.markdown(
            '<div class="vault-brand"><h2 style="margin:0;border:0">⚙️ Case Indexer</h2></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="vault-card"><span class="vault-badge">PRIVATE VAULT</span>'
            '<h3 style="margin:.95rem 0 .2rem;color:#fff">Case Indexer</h3>'
            '<p>Each user must enter their Gmail ID and a strictly unique password to access '
            'RASA AI and their private audition vault.</p></div>',
            unsafe_allow_html=True,
        )
        st.markdown("### Unlock Private Vault")
        with st.form("rasa_signin_form"):
            login_email = st.text_input("Gmail ID", placeholder="yourname@gmail.com")
            login_password = st.text_input("Unique password", type="password")
            sign_in = st.form_submit_button("Unlock my private vault", use_container_width=True)
        if sign_in:
            user = authenticate(login_email, login_password)
            if user:
                st.session_state["rasa_user"] = user
                st.session_state["rasa_auth_notice"] = "Your private vault is unlocked."
                st.rerun()
            else:
                st.error("The Gmail ID or password is incorrect.")

        with st.expander("Create account / Forgot password"):
            auth_mode = st.radio(
                "Account action", ["Create Account", "Forgot Password"],
                label_visibility="collapsed", key="rasa_auth_mode",
            )
            if auth_mode == "Create Account":
                with st.form("rasa_register_form"):
                    register_email = st.text_input("Gmail ID for registration")
                    register_password = st.text_input("Create a password (at least 4 characters)", type="password")
                    register_confirm = st.text_input("Confirm password", type="password")
                    request_code = st.form_submit_button("Send verification OTP", use_container_width=True)
                if request_code:
                    if register_password != register_confirm:
                        st.error("The passwords do not match.")
                    else:
                        try:
                            begin_registration(register_email, register_password)
                            st.session_state["rasa_pending_email"] = register_email.strip().lower()
                            st.success("Verification code sent. Check your Gmail inbox.")
                        except Exception as exc:
                            st.error(str(exc))
                if st.session_state.get("rasa_pending_email"):
                    with st.form("rasa_verify_register_form"):
                        otp = st.text_input("6-digit verification code", max_chars=6)
                        verify = st.form_submit_button("Verify Gmail & create vault", use_container_width=True)
                    if verify:
                        try:
                            user = verify_registration(st.session_state["rasa_pending_email"], otp)
                            st.session_state["rasa_user"] = user
                            st.session_state.pop("rasa_pending_email", None)
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))
            else:
                with st.form("rasa_forgot_form"):
                    reset_email = st.text_input("Registered Gmail ID")
                    send_reset = st.form_submit_button("Send password reset OTP", use_container_width=True)
                if send_reset:
                    try:
                        begin_password_reset(reset_email)
                        st.session_state["rasa_reset_email"] = reset_email.strip().lower()
                        st.success("Password reset code sent to your Gmail.")
                    except Exception as exc:
                        st.error(str(exc))
                if st.session_state.get("rasa_reset_email"):
                    with st.form("rasa_reset_verify_form"):
                        reset_otp = st.text_input("6-digit reset code", max_chars=6)
                        new_password = st.text_input("New password (at least 4 characters)", type="password")
                        confirm_new_password = st.text_input("Confirm new password", type="password")
                        finish_reset = st.form_submit_button("Verify code & reset password", use_container_width=True)
                    if finish_reset:
                        if new_password != confirm_new_password:
                            st.error("The passwords do not match.")
                        else:
                            try:
                                finish_password_reset(
                                    st.session_state["rasa_reset_email"], reset_otp, new_password
                                )
                                st.session_state.pop("rasa_reset_email", None)
                                st.success("Password reset. Sign in with your new password.")
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
        st.caption("Private local storage · Gmail verification required for new accounts")

    _render_intro_page()
    st.stop()



# ---------- Authenticated RASA AI workspace polish ----------
st.markdown("""
<style>
/* Give the working area a deliberate, spacious dashboard layout. */
.block-container {
    padding-top: 2.6rem !important;
    padding-bottom: 4rem !important;
    padding-left: clamp(1.25rem, 3vw, 3.25rem) !important;
    padding-right: clamp(1.25rem, 3vw, 3.25rem) !important;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #171e2b 0%, #111722 100%);
    border-right: 1px solid rgba(135, 164, 220, .20);
}
section[data-testid="stSidebar"] > div {
    padding: 2rem 1.1rem 1.5rem;
}
section[data-testid="stSidebar"] h3 {
    color: #f4f7ff !important;
    font-size: 1.12rem !important;
    font-weight: 780 !important;
    letter-spacing: -.015em;
}
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #aebbd1;
    overflow-wrap: anywhere;
}
section[data-testid="stSidebar"] .stButton > button {
    min-height: 3.1rem;
    width: 100%;
    border-radius: 13px;
    background: linear-gradient(135deg, #263b63, #1d2b48);
    border: 1px solid rgba(130, 166, 235, .34);
    color: #f7faff;
    font-weight: 700;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    border-color: #8eb8ff;
    background: linear-gradient(135deg, #304b7a, #23385d);
}

/* Workspace title block */
.rasa-workspace-header {
    position: relative;
    overflow: hidden;
    padding: 1.55rem 1.8rem 1.45rem;
    margin: .15rem 0 1.55rem;
    border-radius: 22px;
    border: 1px solid rgba(135, 164, 220, .24);
    background:
      radial-gradient(ellipse at 92% 0%, rgba(93, 139, 221, .19), transparent 42%),
      linear-gradient(135deg, rgba(24, 35, 54, .98), rgba(13, 19, 30, .98));
    box-shadow: 0 18px 48px rgba(0, 0, 0, .18);
}
.rasa-workspace-kicker {
    color: #91b8ff;
    text-transform: uppercase;
    font-size: .72rem;
    font-weight: 850;
    letter-spacing: .19em;
    margin-bottom: .45rem;
}
.rasa-workspace-title {
    color: #f5f7ff;
    font-size: clamp(2.2rem, 4vw, 3.15rem);
    line-height: 1.05;
    letter-spacing: -.045em;
    font-weight: 900;
    margin: 0;
}
.rasa-workspace-subtitle {
    color: #aebbd1;
    font-size: .96rem;
    margin-top: .75rem;
}
.rasa-workspace-subtitle span {
    color: #dce8ff;
    font-weight: 650;
}

/* Workflow navigation: clean, legible, and horizontally scrollable. */
div[data-testid="stTabs"] {
    margin-top: .25rem;
}
div[data-testid="stTabs"] > div:first-child {
    gap: .3rem;
    border-bottom: 1px solid rgba(137, 160, 200, .24);
    padding: 0 .15rem;
}
div[data-testid="stTabs"] button[role="tab"] {
    min-height: 3.1rem;
    padding: .78rem .95rem;
    border-radius: 11px 11px 0 0;
    color: #aebbd1;
    font-size: .9rem;
    font-weight: 680;
    white-space: nowrap;
    background: transparent;
    border: 0;
}
div[data-testid="stTabs"] button[role="tab"]:hover {
    color: #f6f8ff;
    background: rgba(105, 147, 220, .10);
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #ffffff;
    background: linear-gradient(180deg, rgba(91, 139, 220, .22), rgba(91, 139, 220, .045));
    box-shadow: inset 0 -3px 0 #83adff;
}
div[data-testid="stTabs"] [data-testid="stTabContent"] {
    padding-top: 1.8rem;
}

/* Form fields and content surfaces */
div[data-testid="stTextArea"] textarea,
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stDateInput"] input,
div[data-testid="stFileUploader"] section {
    background: rgba(24, 31, 44, .92) !important;
    border-color: rgba(135, 160, 202, .25) !important;
    border-radius: 13px !important;
}
div[data-testid="stTextArea"] textarea:focus,
div[data-testid="stTextInput"] input:focus {
    border-color: #83adff !important;
    box-shadow: 0 0 0 1px rgba(131, 173, 255, .22) !important;
}
.stButton > button, .stDownloadButton > button,
div[data-testid="stFormSubmitButton"] button {
    border-radius: 12px;
    font-weight: 720;
    min-height: 2.8rem;
}
div[data-testid="stExpander"] {
    border-radius: 14px;
    border-color: rgba(135, 160, 202, .22);
    background: rgba(19, 27, 40, .55);
}
div[data-testid="stAlert"] {
    border-radius: 13px;
}
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border-radius: 14px;
    border: 1px solid rgba(135, 160, 202, .22);
    overflow: hidden;
}
@media (max-width: 850px) {
    .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }
    .rasa-workspace-header {
        padding: 1.25rem;
        border-radius: 17px;
    }
    div[data-testid="stTabs"] button[role="tab"] {
        padding: .68rem .72rem;
        font-size: .82rem;
    }
}

/* ---------- RASA AI blue workspace theme across every workflow section ---------- */
:root {
    --rasa-blue: #83adff;
    --rasa-blue-bright: #a8c7ff;
    --rasa-blue-deep: #263f70;
    --rasa-panel: #151e2d;
    --rasa-panel-soft: #192437;
    --rasa-line: rgba(135, 164, 220, .25);
}
h1, h2, h3, h4,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3 {
    color: #f3f6ff !important;
    font-weight: 850 !important;
    letter-spacing: -.025em !important;
}
h1 { font-size: clamp(2rem, 3vw, 2.65rem) !important; }
h2 { font-size: clamp(1.55rem, 2.3vw, 2rem) !important; }
h3 { font-size: 1.22rem !important; }
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stCaptionContainer"] {
    line-height: 1.7;
}
[data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] {
    scroll-margin-top: 1.5rem;
}
div[data-testid="stRadio"] label,
div[data-testid="stCheckbox"] label {
    color: #dce7fb !important;
}
div[data-testid="stTextArea"] label,
div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label,
div[data-testid="stMultiSelect"] label,
div[data-testid="stFileUploader"] label,
div[data-testid="stNumberInput"] label,
div[data-testid="stSlider"] label,
div[data-testid="stDateInput"] label,
div[data-testid="stRadio"] > label,
div[data-testid="stCheckbox"] > label {
    color: #dce7fb !important;
    font-weight: 680 !important;
}
div[data-testid="stTextArea"] textarea,
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input,
div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background: #182335 !important;
    border: 1px solid rgba(132, 164, 220, .28) !important;
    color: #f2f6ff !important;
    border-radius: 12px !important;
}
div[data-testid="stTextArea"] textarea:focus,
div[data-testid="stTextInput"] input:focus {
    border-color: #83adff !important;
    box-shadow: 0 0 0 2px rgba(131, 173, 255, .13) !important;
}
.stButton > button,
.stDownloadButton > button,
div[data-testid="stFormSubmitButton"] button {
    color: #f7faff !important;
    background: linear-gradient(135deg, #35599a, #294579) !important;
    border: 1px solid rgba(145, 181, 246, .48) !important;
    border-radius: 12px !important;
    font-weight: 760 !important;
    transition: transform .16s ease, filter .16s ease, box-shadow .16s ease;
}
.stButton > button:hover,
.stDownloadButton > button:hover,
div[data-testid="stFormSubmitButton"] button:hover {
    filter: brightness(1.13);
    transform: translateY(-1px);
    box-shadow: 0 8px 22px rgba(36, 76, 143, .24);
}
.stButton > button:focus,
.stDownloadButton > button:focus {
    box-shadow: 0 0 0 2px rgba(131, 173, 255, .28) !important;
}
div[data-testid="stExpander"] {
    background: linear-gradient(145deg, rgba(25, 37, 57, .94), rgba(17, 26, 41, .94)) !important;
    border: 1px solid var(--rasa-line) !important;
    border-radius: 15px !important;
}
div[data-testid="stExpander"] summary {
    color: #eaf1ff !important;
    font-weight: 720 !important;
}
div[data-testid="stAlert"] {
    border-radius: 13px !important;
}
div[data-testid="stAlert"][data-testid="stAlert"] {
    border-color: var(--rasa-line);
}
div[data-testid="stTabs"] [data-testid="stTabContent"] {
    padding: 1.9rem .15rem 2.5rem !important;
}
div[data-testid="stTabs"] button[role="tab"] {
    font-weight: 720 !important;
}
div[data-testid="stProgressBar"] > div > div {
    background: linear-gradient(90deg, #527fc9, #91baff) !important;
}
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border: 1px solid var(--rasa-line) !important;
    border-radius: 14px !important;
    overflow: hidden;
}
hr {
    border-color: rgba(135, 164, 220, .2) !important;
}

/* Stronger visual hierarchy: section banners and elevated workflow surfaces. */
.rasa-section-heading {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin: .1rem 0 1.55rem;
    padding: 1.15rem 1.35rem;
    border: 1px solid rgba(130, 169, 239, .30);
    border-left: 4px solid #82adff;
    border-radius: 17px;
    background:
      radial-gradient(circle at 100% 0%, rgba(82, 132, 219, .17), transparent 38%),
      linear-gradient(125deg, rgba(27, 42, 66, .98), rgba(16, 25, 40, .98));
    box-shadow: 0 12px 30px rgba(0, 0, 0, .16);
}
.rasa-section-index {
    flex: 0 0 2.8rem;
    width: 2.8rem;
    height: 2.8rem;
    display: grid;
    place-items: center;
    border-radius: 12px;
    color: #dce9ff;
    background: linear-gradient(145deg, #426db2, #263f70);
    border: 1px solid rgba(164, 194, 246, .35);
    font-size: .9rem;
    font-weight: 900;
    letter-spacing: .04em;
    box-shadow: inset 0 1px 0 rgba(255,255,255,.12);
}
.rasa-section-copy { min-width: 0; }

/* Important screenplay evidence notes should be as readable as the main content. */
.rasa-important-note {
    margin: .55rem 0 .8rem;
    padding: .7rem .9rem;
    border-left: 3px solid #83adff;
    border-radius: 8px;
    background: rgba(35, 53, 80, .58);
    color: #e2eaf8;
    font-size: 1rem;
    line-height: 1.65;
    font-weight: 500;
    overflow-wrap: anywhere;
}
.rasa-important-note strong {
    color: #a9c8ff;
    font-weight: 800;
}
.rasa-section-eyebrow {
    margin-bottom: .24rem;
    color: #91b8ff;
    font-size: .68rem;
    line-height: 1.2;
    font-weight: 850;
    letter-spacing: .17em;
}
.rasa-section-title {
    color: #f4f7ff;
    font-size: clamp(1.35rem, 2.2vw, 1.85rem);
    line-height: 1.2;
    font-weight: 900;
    letter-spacing: -.035em;
}
.rasa-workspace-header {
    padding: 2rem 2.15rem 1.85rem;
    min-height: 190px;
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.rasa-workspace-title {
    font-weight: 950 !important;
    font-size: clamp(2.65rem, 5vw, 3.8rem) !important;
    letter-spacing: -.055em !important;
}
.rasa-workspace-subtitle {
    font-size: 1rem;
}
div[data-testid="stTabs"] [data-testid="stTabContent"] {
    padding: 1.75rem 1.1rem 2.4rem !important;
    border: 1px solid rgba(126, 157, 211, .15);
    border-top: 0;
    border-radius: 0 0 20px 20px;
    background: linear-gradient(180deg, rgba(18, 27, 42, .40), rgba(12, 19, 30, .18));
}
div[data-testid="stTabs"] > div:first-child {
    padding: .35rem .35rem 0;
    border: 1px solid rgba(126, 157, 211, .18);
    border-radius: 15px 15px 0 0;
    background: linear-gradient(90deg, rgba(24, 37, 58, .96), rgba(15, 24, 38, .96));
}
div[data-testid="stTabs"] button[role="tab"] {
    min-height: 3.35rem;
    padding: .82rem 1rem;
    font-size: .9rem;
    font-weight: 780 !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #fff !important;
    background: linear-gradient(180deg, rgba(77, 121, 195, .32), rgba(54, 88, 145, .13)) !important;
    box-shadow: inset 0 -3px 0 #8db6ff !important;
}
div[data-testid="stTextArea"] textarea {
    min-height: 235px;
    padding: 1rem !important;
    line-height: 1.65;
    background: linear-gradient(145deg, #1b2638, #151f30) !important;
}
div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
div[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    min-height: 2.85rem;
    background: linear-gradient(145deg, #1b2638, #151f30) !important;
}
div[data-testid="stFileUploader"] section {
    padding: 1.2rem;
    background: linear-gradient(145deg, rgba(28, 43, 66, .82), rgba(18, 29, 46, .82)) !important;
    border: 1px dashed rgba(133, 172, 239, .48) !important;
}
div[data-testid="stExpander"] {
    margin: .55rem 0;
    background: linear-gradient(145deg, rgba(25, 39, 61, .90), rgba(16, 26, 42, .90)) !important;
    box-shadow: 0 8px 22px rgba(0,0,0,.10);
}
.stButton > button, .stDownloadButton > button,
div[data-testid="stFormSubmitButton"] button {
    min-height: 2.95rem;
    padding: .55rem 1.15rem;
    background: linear-gradient(135deg, #416fc0, #2d4f91) !important;
    border: 1px solid rgba(151, 187, 249, .48) !important;
    box-shadow: 0 7px 18px rgba(32, 70, 135, .18);
}
[data-testid="stMetric"] {
    padding: 1rem 1.1rem;
    border-radius: 15px;
    border: 1px solid rgba(129, 163, 220, .24);
    background: linear-gradient(145deg, rgba(28, 42, 64, .90), rgba(17, 27, 43, .90));
}
[data-testid="stMetricLabel"] { color: #a9c4f2 !important; font-weight: 700; }
[data-testid="stMetricValue"] { color: #f5f8ff !important; font-weight: 900; }
@media (max-width: 850px) {
    .rasa-section-heading { padding: .95rem; gap: .75rem; }
    .rasa-section-title { font-size: 1.25rem; }
    div[data-testid="stTabs"] [data-testid="stTabContent"] { padding: 1.2rem .5rem !important; }
}

</style>
""", unsafe_allow_html=True)

# Authenticated session: switch all local persistence paths to this account's directory.
_current_user = st.session_state["rasa_user"]
_USER_DATA_DIR = Path(__file__).resolve().parent / "rasaai_private_data" / "users" / _current_user["user_id"]
_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDITION_LIBRARY_PATH = _USER_DATA_DIR / "rasaai_audition_library.json"
AUDITION_HISTORY_DIR = _USER_DATA_DIR / "rasaai_audition_history"
AUDITION_ACTIVITY_PATH = _USER_DATA_DIR / "rasaai_audition_activity.json"

with st.sidebar:
    st.markdown("### 🔐 Private Vault")
    st.markdown(
        '<div style="padding:.85rem .9rem;margin:.35rem 0 1rem;'
        'border:1px solid rgba(135,164,220,.22);border-radius:14px;'
        'background:rgba(255,255,255,.035);">'
        '<div style="font-size:.68rem;font-weight:800;letter-spacing:.14em;'
        'color:#8fb7ff;text-transform:uppercase;margin-bottom:.35rem;">Signed in</div>'
        f'<div style="font-size:.88rem;color:#e8efff;overflow-wrap:anywhere;">'
        f'{html.escape(_current_user["email"])}</div></div>',
        unsafe_allow_html=True,
    )
    if st.button("Log out", use_container_width=True, key="rasa_logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# Audition comparisons persist inside the signed-in user's private local folder. No cloud service is used.
# These paths are assigned above from the authenticated user's unique account ID.
MAX_LIBRARY_SNAPSHOTS = 20


def load_audition_library():
    """Load saved audition reports, returning an empty list if no library exists yet."""
    try:
        if AUDITION_LIBRARY_PATH.exists():
            with AUDITION_LIBRARY_PATH.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return [item for item in data if isinstance(item, dict)]
    except (OSError, json.JSONDecodeError) as exc:
        st.warning(f"Could not read the local audition library: {exc}")
    return []


def create_library_snapshot():
    """Preserve the current library before it is overwritten."""
    if not AUDITION_LIBRARY_PATH.exists():
        return
    AUDITION_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    snapshot_path = AUDITION_HISTORY_DIR / f"audition_library_{stamp}.json"
    shutil.copy2(AUDITION_LIBRARY_PATH, snapshot_path)
    snapshots = sorted(
        AUDITION_HISTORY_DIR.glob("audition_library_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_snapshot in snapshots[MAX_LIBRARY_SNAPSHOTS:]:
        old_snapshot.unlink(missing_ok=True)


def list_library_snapshots():
    """Return newest snapshots first."""
    if not AUDITION_HISTORY_DIR.exists():
        return []
    return sorted(
        AUDITION_HISTORY_DIR.glob("audition_library_*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def save_audition_library(items):
    """Persist JSON and snapshot the previous version before overwriting it."""
    try:
        AUDITION_LIBRARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if AUDITION_LIBRARY_PATH.exists():
            create_library_snapshot()
        temp_path = AUDITION_LIBRARY_PATH.with_suffix(".json.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(items, handle, indent=2, ensure_ascii=False)
        temp_path.replace(AUDITION_LIBRARY_PATH)
        return True
    except OSError as exc:
        st.error(f"Could not save the local audition library: {exc}")
        return False



def run_local_health_checks():
    """Return simple local environment checks without changing application data."""
    checks = []
    import sys
    checks.append({
        "Check": "Python version",
        "Status": "Pass" if sys.version_info >= (3, 10) else "Warning",
        "Details": sys.version.split()[0],
    })
    for module_name, label in [
        ("numpy", "NumPy"),
        ("cv2", "OpenCV"),
        ("mediapipe", "MediaPipe"),
        ("streamlit", "Streamlit"),
        ("pypdf", "pypdf"),
    ]:
        try:
            module = __import__(module_name)
            checks.append({
                "Check": f"{label} import",
                "Status": "Pass",
                "Details": str(getattr(module, "__version__", "version not exposed")),
            })
        except Exception as exc:
            checks.append({
                "Check": f"{label} import",
                "Status": "Fail",
                "Details": f"{type(exc).__name__}: {exc}",
            })
    try:
        test_path = AUDITION_LIBRARY_PATH.parent / ".rasaai_write_test.tmp"
        test_path.write_text("ok", encoding="utf-8")
        test_path.unlink(missing_ok=True)
        checks.append({
            "Check": "Project folder write access",
            "Status": "Pass",
            "Details": str(AUDITION_LIBRARY_PATH.parent),
        })
    except OSError as exc:
        checks.append({
            "Check": "Project folder write access",
            "Status": "Fail",
            "Details": f"{type(exc).__name__}: {exc}",
        })
    return checks

def load_audition_activity():
    """Load the local activity log, returning an empty list if it is not present."""
    try:
        if AUDITION_ACTIVITY_PATH.exists():
            with AUDITION_ACTIVITY_PATH.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return [entry for entry in data if isinstance(entry, dict)]
    except (OSError, json.JSONDecodeError) as exc:
        st.warning(f"Could not read the local activity log: {exc}")
    return []


def record_audition_activity(action, item, details=None):
    """Append a minimal local event for important library/review actions."""
    try:
        events = load_audition_activity()
        events.append({
            "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "action": str(action),
            "actor_label": item.get("actor_label") or item.get("video_file") or "Unnamed audition",
            "character": item.get("selected_character") or "Unassigned",
            "review_status": item.get("reviewer_decision", "Not reviewed"),
            "shortlisted": bool(item.get("shortlisted", False)),
            "details": str(details or ""),
        })
        AUDITION_ACTIVITY_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp_path = AUDITION_ACTIVITY_PATH.with_suffix(".json.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(events[-1000:], handle, indent=2, ensure_ascii=False)
        temp_path.replace(AUDITION_ACTIVITY_PATH)
        return True
    except OSError as exc:
        st.warning(f"Could not write the local activity log: {exc}")
        return False


def build_audition_html_report(item):
    """Build a standalone, downloadable HTML report for one saved audition."""
    def safe(value):
        if value is None or value == "":
            return "Not available"
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, indent=2)
        return html.escape(str(value)).replace("\\n", "<br>")

    actor = item.get("actor_label") or item.get("video_file") or "Unnamed audition"
    character = item.get("selected_character") or "Unassigned"
    pose_rate = item.get("pose_detection_rate")
    pose_percent = f"{pose_rate * 100:.1f}%" if isinstance(pose_rate, (int, float)) else "Not available"
    evidence_notes = item.get("evidence_quality_notes", [])
    metric_keys = [
        ("Duration (seconds)", "duration_seconds_estimate"),
        ("Pose detection rate", None),
        ("Normalized landmark movement index", "mean_normalized_landmark_movement_index"),
        ("Mean shoulder tilt index", "mean_shoulder_tilt_index"),
        ("Torso lateral offset", "mean_torso_lateral_offset"),
        ("Samples with wrist above shoulder", "fraction_samples_with_wrist_above_shoulder"),
    ]
    metric_rows = []
    for label, key in metric_keys:
        value = pose_percent if key is None else item.get(key)
        metric_rows.append(f"<tr><th>{safe(label)}</th><td>{safe(value)}</td></tr>")

    notes_html = "".join(f"<li>{safe(note)}</li>" for note in evidence_notes) or "<li>No evidence-quality notes recorded.</li>"
    reviewer_notes = safe(item.get("reviewer_notes", ""))
    timestamp_rows = item.get("samples", item.get("timestamped_samples", []))
    if not isinstance(timestamp_rows, list):
        timestamp_rows = []
    sample_html = ""
    if timestamp_rows:
        keys = list(timestamp_rows[0].keys()) if isinstance(timestamp_rows[0], dict) else []
        if keys:
            header = "".join(f"<th>{safe(key)}</th>" for key in keys)
            body = "".join(
                "<tr>" + "".join(f"<td>{safe(row.get(key))}</td>" for key in keys) + "</tr>"
                for row in timestamp_rows if isinstance(row, dict)
            )
            sample_html = f"<h2>Timestamped observations</h2><table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RasaAI Audition Review — {safe(actor)}</title>
<style>
body{{font-family:Arial,sans-serif;max-width:1000px;margin:32px auto;padding:0 20px;color:#202124;line-height:1.5}}
h1,h2{{color:#202124}} .meta{{color:#5f6368}} table{{border-collapse:collapse;width:100%;margin:12px 0 24px}}
th,td{{border:1px solid #dadce0;padding:8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}}
th{{background:#f1f3f4}} .notice{{border-left:4px solid #888;padding:10px 14px;background:#f8f9fa}}
@media print{{body{{margin:0;max-width:none}}}}
</style></head><body>
<h1>RasaAI — Audition Review Report</h1>
<p class="meta">Generated from the local audition library. This report supports human review and is not an automated casting decision.</p>
<h2>Audition details</h2>
<table><tbody>
<tr><th>Actor / label</th><td>{safe(actor)}</td></tr>
<tr><th>Character</th><td>{safe(character)}</td></tr>
<tr><th>Video file</th><td>{safe(item.get("video_file"))}</td></tr>
<tr><th>Review status</th><td>{safe(item.get("reviewer_decision", "Not reviewed"))}</td></tr>
<tr><th>Shortlisted</th><td>{safe(bool(item.get("shortlisted", False)))}</td></tr>
<tr><th>Reviewer notes</th><td>{reviewer_notes}</td></tr>
</tbody></table>
<h2>Observable measurements</h2><table><tbody>{''.join(metric_rows)}</tbody></table>
<h2>Evidence-quality notes</h2><ul>{notes_html}</ul>
{sample_html}
<div class="notice"><strong>Limitations:</strong> Measurements are exploratory and sensitive to framing, lighting, occlusion, clip duration, and pose-detector limitations. They do not establish talent, emotion, personality, or casting suitability. Human review is required.</div>
</body></html>"""


def create_library_backup_bytes(items):
    """Serialize the current library into a versioned backup file."""
    payload = {
        "format": "rasaai-audition-library-backup",
        "schema_version": 1,
        "created_at_local": __import__("datetime").datetime.now().astimezone().isoformat(timespec="seconds"),
        "record_count": len(items),
        "auditions": items,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")


def parse_library_backup(uploaded_file):
    """Validate a backup before any restore operation is allowed."""
    try:
        payload = json.loads(uploaded_file.getvalue().decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"Backup is not valid UTF-8 JSON: {exc}"

    if not isinstance(payload, dict):
        return None, "Backup must be a JSON object."
    if payload.get("format") != "rasaai-audition-library-backup":
        return None, "This file is not a recognized RasaAI audition-library backup."
    if payload.get("schema_version") != 1:
        return None, "This backup uses an unsupported schema version."
    auditions = payload.get("auditions")
    if not isinstance(auditions, list) or not all(isinstance(item, dict) for item in auditions):
        return None, "Backup auditions must be a list of JSON objects."

    return auditions, None


def audition_record_key(item):
    """Return a conservative duplicate key for a saved audition."""
    return (
        str(item.get("actor_label") or "").strip().casefold(),
        str(item.get("video_file") or "").strip().casefold(),
        str(item.get("selected_character") or "").strip().casefold(),
    )


def inspect_audition_library(items):
    """Report likely duplicates and incomplete records without changing data."""
    duplicate_groups = {}
    incomplete = []
    for index, item in enumerate(items):
        key = audition_record_key(item)
        # Do not flag records with no identifying information as duplicates of one another.
        if any(key):
            duplicate_groups.setdefault(key, []).append(index)

        missing = []
        if not item.get("video_file"):
            missing.append("video filename")
        if not item.get("selected_character"):
            missing.append("character assignment")
        if not isinstance(item.get("pose_detection_rate"), (int, float)):
            missing.append("pose detection rate")
        if not item.get("analysis_method"):
            missing.append("analysis method metadata")
        if missing:
            incomplete.append({"index": index, "item": item, "missing": missing})

    duplicates = [
        {"indices": indices, "items": [items[index] for index in indices]}
        for indices in duplicate_groups.values() if len(indices) > 1
    ]
    return duplicates, incomplete


def build_audition_export_bundle(items):
    """Build a ZIP with the saved library, summary CSV/JSON, and per-audition HTML reports."""
    buffer = io.BytesIO()
    summary_rows = []
    for index, item in enumerate(items, start=1):
        pose_rate = item.get("pose_detection_rate")
        summary_rows.append({
            "Record": index,
            "Actor / label": item.get("actor_label") or item.get("video_file") or "Unnamed audition",
            "Character": item.get("selected_character") or "Unassigned",
            "Review status": item.get("reviewer_decision", "Not reviewed"),
            "Shortlisted": bool(item.get("shortlisted", False)),
            "Reviewer notes": item.get("reviewer_notes", ""),
            "Duration (s)": item.get("duration_seconds_estimate"),
            "Pose detection (%)": round(pose_rate * 100, 1)
            if isinstance(pose_rate, (int, float)) else None,
            "Video file": item.get("video_file", ""),
        })

    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "rasaai_audition_library_backup.json",
            create_library_backup_bytes(items),
        )

        csv_buffer = io.StringIO(newline="")
        fieldnames = list(summary_rows[0].keys()) if summary_rows else [
            "Record", "Actor / label", "Character", "Review status",
            "Shortlisted", "Reviewer notes", "Duration (s)",
            "Pose detection (%)", "Video file",
        ]
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)
        archive.writestr("audition_summary.csv", csv_buffer.getvalue().encode("utf-8-sig"))

        archive.writestr(
            "audition_summary.json",
            json.dumps({
                "total_saved_auditions": len(items),
                "auditions": summary_rows,
            }, indent=2, ensure_ascii=False),
        )

        for index, item in enumerate(items, start=1):
            label = item.get("actor_label") or item.get("video_file") or f"audition_{index}"
            safe_label = re.sub(r"[^A-Za-z0-9_-]+", "_", str(label)).strip("_") or f"audition_{index}"
            archive.writestr(
                f"individual_reports/{index:03d}_{safe_label}.html",
                build_audition_html_report(item),
            )
    return buffer.getvalue()


if "rasa_audition_comparisons" not in st.session_state:
    st.session_state["rasa_audition_comparisons"] = load_audition_library()

st.markdown(
    f"""
    <section class="rasa-workspace-header">
      <div class="rasa-workspace-kicker">Audition intelligence · Casting support</div>
      <h1 class="rasa-workspace-title">🎬 RASA AI</h1>
      <div class="rasa-workspace-subtitle">
        Private workspace <span>·</span> Signed in as
        <span>{html.escape(_current_user['email'])}</span>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)
st.session_state.pop("rasa_auth_notice", None)  # Clear the one-time notice without a green banner.


def _rasa_section_heading(number: str, eyebrow: str, title: str) -> None:
    """Render a consistent blue section banner inside the authenticated workspace."""
    st.markdown(
        f"""
        <div class="rasa-section-heading">
          <div class="rasa-section-index">{html.escape(number)}</div>
          <div class="rasa-section-copy">
            <div class="rasa-section-eyebrow">{html.escape(eyebrow)}</div>
            <div class="rasa-section-title">{html.escape(title)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


workflow_tabs = st.tabs([
    "Screenplay",
    "Character Cues",
    "Role Requirements",
    "Video Analysis",
    "Vocal Analysis",
    "Evidence Timeline",
    "Haystack Retrieval",
    "Db2 Database",
])


# ---------- Traditional NLP / deterministic screenplay parsing ----------

# ---------- Screenplay-grounded character performance intelligence ----------
# These are observable script cues, not personality or emotion diagnoses.
ROLE_KEYWORDS = {
    "high movement": [
        "runs", "running", "chases", "fights", "jumps", "dances", "falls",
        "struggles", "rushes", "lunges", "stumbles", "sprints", "moves quickly",
    ],
    "hand gestures": [
        "points", "pointing", "gestures", "waves", "raises a hand",
        "raises his hand", "raises her hand", "clenches a fist", "reaches",
        "signals", "grabs", "holds out", "pushes away",
    ],
    "stillness / controlled posture": [
        "stands still", "stands motionless", "sits silently", "freezes",
        "does not move", "remains motionless", "holds still", "standing still",
        "stares", "doesn't move",
    ],
    "physical tension": [
        "shakes", "trembles", "trembling", "paces", "clenches", "clenching",
        "tightens", "breathes heavily", "hands trembling", "fists tighten",
        "jaw tightens", "wrings her hands", "wrings his hands",
    ],
    "visible expression changes (review manually)": [
        "smiles", "laughs", "cries", "weeps", "frowns", "grimaces", "gasps",
        "winces", "looks away", "tears", "eyes widen",
    ],
    "dialogue-heavy scene": [],
}

AUDITION_TESTS = {
    "high movement": "Recreate the written movement safely, then repeat it with controlled pacing. Review clarity and continuity rather than intensity.",
    "hand gestures": "Deliver the same line once with the scripted gesture and once with restrained movement. Compare whether the gesture supports the line.",
    "stillness / controlled posture": "Deliver the line while holding the written stillness. Check whether attention and intention remain readable without extra movement.",
    "physical tension": "Recreate only the physical action written in the script. Check whether tension is legible without forcing or exaggerating it.",
    "visible expression changes (review manually)": "Perform the beat as written. Ask the reviewer to note the visible change and the exact moment it occurs; do not assume an emotion from the gesture alone.",
    "dialogue-heavy scene": "Read a representative passage with the scripted pauses and delivery directions. Review pace, intelligibility and consistency.",
    "shared blocking / spatial relationship": "Recreate the relative positions and shared blocking with the scene partner. Review spacing, orientation and continuity for both performers.",
    "gaze / eyeline direction": "Recreate the scripted eyeline toward each named scene partner. Review direction, timing and continuity without assuming an emotion.",
    "interaction / reaction partner": "Play the moment as the named interaction or reaction partner. Review whether the response timing fits the other character's action and the scene context.",
    "physical interaction / contact partner": "Rehearse the contact or interaction safely with the scene partner, checking timing, consent, continuity and the written action.",
}

CHARACTER_INTERPRETATIONS = {
    "high movement": ("Physical urgency / active movement", "Can the performer execute the scripted movement clearly and safely without losing the scene's objective?"),
    "hand gestures": ("Expressive use of hands and gesture", "Do gestures feel motivated by the scene, or do they distract from the dialogue?"),
    "stillness / controlled posture": ("Stillness / controlled physical presence", "Can the performer sustain a readable, intentional stillness without becoming visually disengaged?"),
    "physical tension": ("Visible physical tension", "Can tension be communicated through the specific written action without exaggeration?"),
    "visible expression changes (review manually)": ("Observable expression changes", "Can the performer make the written physical beat readable while keeping the interpretation open to the director?"),
    "dialogue-heavy scene": ("Dialogue-led performance", "Can the performer sustain the passage with clear phrasing, pace and the script's stated delivery?"),
    "shared blocking / spatial relationship": ("Shared blocking / spatial relationship", "Can the performer maintain the written position, spacing and orientation relative to the scene partner?"),
    "gaze / eyeline direction": ("Gaze / eyeline direction", "Does the performer direct their gaze toward the named character at the scripted moment, with consistent eyeline?"),
    "interaction / reaction partner": ("Interaction / reaction partner", "Does the performer respond at the appropriate beat as the named recipient of the other character's action or gaze?"),
    "physical interaction / contact partner": ("Physical interaction / contact partner", "Is the performer's part of the physical interaction clear, safe, consensual and consistent with the written action?"),
}

_ACTION_VERBS = {
    "high movement", "hand gestures", "stillness / controlled posture",
    "physical tension", "visible expression changes (review manually)",
}
_SCENE_HEADING_RE = re.compile(
    r"^\s*(?:SCENE\s+\d+\s*[-–—:]?\s*)?(?:INT\.|EXT\.|INT/EXT\.|INT\./EXT\.)",
    re.I,
)
_TRANSITION_RE = re.compile(r"^\s*(?:CUT TO:|FADE IN:|FADE OUT\.?|DISSOLVE TO:|SMASH CUT TO:|THE END)\s*$", re.I)


def _character_name_pattern(name):
    return re.compile(r"(?<![\w])" + re.escape(name) + r"(?![\w])", re.I)


def _split_sentences(text):
    """Small deterministic sentence splitter suitable for screenplay action lines."""
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text) if part.strip()]


def _cue_hits(text):
    """Return cue labels and matched script words from one evidence sentence."""
    found = []
    lower = text.casefold()
    for label, words in ROLE_KEYWORDS.items():
        hits = [
            word for word in words
            if re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", lower)
        ]
        if hits:
            found.append((label, hits))
    return found


def extract_character_specific_cues(story, character_name, all_character_names=None):
    """
    Attribute only screenplay action sentences that explicitly name this character.
    Dialogue is attributed by screenplay speaker cue; ambiguous pronouns are not guessed.
    """
    all_names = list(all_character_names or [character_name])
    patterns = {name: _character_name_pattern(name) for name in all_names}
    target_pattern = patterns[character_name]
    evidence_by_label = {}
    dialogue_blocks = 0
    dialogue_words = 0
    ambiguous_actions = []

    lines = story.splitlines()
    first_scene_index = next(
        (i for i, candidate in enumerate(lines) if _SCENE_HEADING_RE.match(candidate.strip())),
        0,
    )
    current_speaker = None
    in_dialogue = False
    pending_action = []

    def flush_action_block(block):
        if not block:
            return
        joined = " ".join(x.strip() for x in block if x.strip())
        for sentence in _split_sentences(joined):
            mentioned = [name for name, pattern in patterns.items() if pattern.search(sentence)]
            if character_name.casefold() not in {name.casefold() for name in mentioned}:
                continue

            def add_item(label, hits, source):
                evidence_by_label.setdefault(label, []).append({
                    "excerpt": sentence[:320],
                    "matched_words": hits[:4],
                    "source": source,
                })

            if len(mentioned) == 1:
                for label, hits in _cue_hits(sentence):
                    if label != "dialogue-heavy scene":
                        add_item(label, hits, "Explicitly named character in action text")
                continue

            # Shared blocking: both explicitly named characters participate in
            # the spatial arrangement, so each receives the same blocking cue.
            blocking_pattern = re.compile(
                r"\b(?:sits?|sitting|sat|stands?|standing|stood|kneels?|kneeling|"
                r"faces?|facing|stands? opposite|sits? opposite|next to|beside|"
                r"across from|in front of|behind|side by side|approaches?|"
                r"approach|meets?|meet)\b",
                re.I,
            )
            if blocking_pattern.search(sentence):
                add_item(
                    "shared blocking / spatial relationship",
                    [blocking_pattern.search(sentence).group(0)],
                    "Shared blocking explicitly names this character and another character",
                )

            # Directional gaze: attribute the action to the named subject, while
            # recording the named recipient as the interaction/reaction partner.
            gaze_match = re.search(
                r"\b(" + "|".join(re.escape(n) for n in mentioned) +
                r")\b\s+(?:slowly\s+| briefly\s+)?"
                r"(looks?|glances?|stares?|gazes?)\s+"
                r"(?:directly\s+|briefly\s+)?(?:at|toward|to)\s+"
                r"(.+?)(?=[,;.]|$)",
                sentence,
                re.I,
            )
            if gaze_match:
                actor = next((n for n in mentioned if n.casefold() == gaze_match.group(1).casefold()), None)
                recipients = [
                    n for n in mentioned
                    if n.casefold() != (actor or "").casefold()
                    and re.search(
                        r"\b(?:at|toward|to)\s+" + re.escape(n) + r"\b",
                        sentence,
                        re.I,
                    )
                ]
                if actor and actor.casefold() == character_name.casefold():
                    add_item("gaze / eyeline direction", [gaze_match.group(2)], "Named character performs a directional gaze")
                if any(n.casefold() == character_name.casefold() for n in recipients):
                    add_item("interaction / reaction partner", ["is the named gaze target"], "Named as the recipient of another character's gaze")

            # Clear physical contact: attribute the action to its grammatical
            # subject and give the named recipient a partner cue, not the action.
            contact_match = re.search(
                r"\b(" + "|".join(re.escape(n) for n in mentioned) +
                r")\b\s+(grabs?|holds?|pushes?|pulls?|touches?|takes?|"
                r"reaches? for|shakes hands with)\s+(.+?)(?=[,;.]|$)",
                sentence,
                re.I,
            )
            if contact_match:
                actor = next((n for n in mentioned if n.casefold() == contact_match.group(1).casefold()), None)
                recipients = [
                    n for n in mentioned
                    if n.casefold() != (actor or "").casefold()
                    and _character_name_pattern(n).search(contact_match.group(3))
                ]
                if actor and actor.casefold() == character_name.casefold():
                    add_item("hand gestures", [contact_match.group(2)], "Named character performs a physical interaction")
                if any(n.casefold() == character_name.casefold() for n in recipients):
                    add_item("physical interaction / contact partner", ["is the named contact partner"], "Named as the recipient of another character's physical action")

            # If the sentence names multiple characters but no relationship/action
            # could be reliably parsed, retain it for manual review.
            classified = bool(blocking_pattern.search(sentence) or gaze_match or contact_match)
            if not classified:
                ambiguous_actions.append(sentence[:240])

    for line_index, raw_line in enumerate(lines):
        if line_index < first_scene_index:
            continue
        line = raw_line.strip()
        if not line:
            flush_action_block(pending_action)
            pending_action = []
            in_dialogue = False
            current_speaker = None
            continue
        if _SCENE_HEADING_RE.match(line) or _TRANSITION_RE.match(line):
            flush_action_block(pending_action)
            pending_action = []
            in_dialogue = False
            current_speaker = None
            continue

        # Inline dialogue format: **MAYA:** spoken dialogue on the same line.
        inline_cue = re.match(
            r"^\*{0,2}([A-Z][A-Z0-9 ._'’-]{1,35}?)"
            r"(?:\s*\(([^)]*)\))?\s*:\*{0,2}\s+(.+)$",
            line,
        )
        if inline_cue:
            candidate = normalize_name(inline_cue.group(1))
            known = next((n for n in all_names if n.casefold() == candidate.casefold()), None)
            if known:
                flush_action_block(pending_action)
                pending_action = []
                current_speaker = known
                in_dialogue = True
                spoken_text = inline_cue.group(3).strip()
                if known.casefold() == character_name.casefold():
                    dialogue_blocks += 1
                    dialogue_words += len(re.findall(r"[A-Za-z0-9]+", spoken_text))
                    parenthetical = (inline_cue.group(2) or "").strip()
                    if parenthetical:
                        for label, hits in _cue_hits(parenthetical):
                            evidence_by_label.setdefault(label, []).append({
                                "excerpt": parenthetical[:320],
                                "matched_words": hits[:4],
                                "source": "Speaker parenthetical",
                            })
                continue

        # A character cue may also be a standalone ALL-CAPS line.
        cue_match = re.match(
            r"^\*{0,2}([A-Z][A-Z0-9 ._'’-]{1,35}?)"
            r"(?:\s*\(([^)]*)\))?\s*:?\*{0,2}$",
            line,
        )
        if cue_match:
            candidate = normalize_name(cue_match.group(1))
            known = next((n for n in all_names if n.casefold() == candidate.casefold()), None)
            if known:
                flush_action_block(pending_action)
                pending_action = []
                current_speaker = known
                in_dialogue = True
                if known.casefold() == character_name.casefold():
                    dialogue_blocks += 1
                    parenthetical = (cue_match.group(2) or "").strip()
                    if parenthetical:
                        for label, hits in _cue_hits(parenthetical):
                            evidence_by_label.setdefault(label, []).append({
                                "excerpt": parenthetical[:320],
                                "matched_words": hits[:4],
                                "source": "Speaker parenthetical",
                            })
                continue

        # Parentheticals immediately beneath a speaker cue describe delivery/action.
        if in_dialogue and current_speaker:
            if line.startswith("(") and line.endswith(")"):
                if current_speaker.casefold() == character_name.casefold():
                    for label, hits in _cue_hits(line):
                        evidence_by_label.setdefault(label, []).append({
                            "excerpt": line[:320],
                            "matched_words": hits[:4],
                            "source": "Speaker parenthetical",
                        })
                continue
            # Dialogue belongs to the current speaker until a blank line or next cue.
            if current_speaker.casefold() == character_name.casefold():
                dialogue_words += len(re.findall(r"\b[\w'-]+\b", line))
            continue

        # Outside a dialogue block, treat text as action. Attribution requires a name.
        pending_action.append(line)

    flush_action_block(pending_action)

    cues = []
    for label, evidence_items in evidence_by_label.items():
        # Keep distinct evidence, avoiding repeated duplicate sentences.
        unique = []
        seen = set()
        for item in evidence_items:
            key = item["excerpt"].casefold()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        title, watchpoint = CHARACTER_INTERPRETATIONS.get(
            label, (label.replace("/", " / ").title(), "Review the written evidence in scene context.")
        )
        cues.append({
            "requirement": label,
            "characteristic": title,
            "evidence_items": unique[:8],
            "evidence_in_context": "Evidence: " + " | ".join(item["excerpt"] for item in unique[:3]),
            "context_excerpt": "\n".join(item["excerpt"] for item in unique[:3]),
            "audition_test": AUDITION_TESTS[label],
            "director_watchpoint": watchpoint,
            "status": "screenplay-supported interpretation — director review required",
        })

    # A shared conversation cue is based only on screenplay speaker turns,
    # never on the meaning or sentiment of dialogue text.
    scene_speakers = set()
    for raw_line in lines[first_scene_index:]:
        line_text = raw_line.strip()
        inline_speaker = re.match(
            r"^\*{0,2}([A-Z][A-Z0-9 ._'’-]{1,35}?)"
            r"(?:\s*\([^)]*\))?\s*:\*{0,2}\s+\S",
            line_text,
        )
        standalone_speaker = re.match(
            r"^\*{0,2}([A-Z][A-Z0-9 ._'’-]{1,35}?)"
            r"(?:\s*\([^)]*\))?\s*:?\*{0,2}$",
            line_text,
        )
        speaker_match = inline_speaker or standalone_speaker
        if speaker_match:
            candidate = normalize_name(speaker_match.group(1))
            known = next((n for n in all_names if n.casefold() == candidate.casefold()), None)
            if known:
                scene_speakers.add(known)

    partners = [n for n in all_names if n.casefold() != character_name.casefold()
                and any(s.casefold() == n.casefold() for s in scene_speakers)]
    if (character_name.casefold() in {s.casefold() for s in scene_speakers}
            and partners and dialogue_blocks >= 1):
        partner_names = ", ".join(partners)
        evidence = (
            f"{character_name} has dialogue speaker turns in the same screenplay "
            f"as {partner_names}; review listening, response timing and turn-taking."
        )
        cues.append({
            "requirement": "dialogue exchange / scene partner interaction",
            "characteristic": "Dialogue exchange / scene partner interaction",
            "evidence_items": [{
                "excerpt": evidence,
                "matched_words": [],
                "source": "Screenplay speaker-cue sequence; dialogue meaning not evaluated",
            }],
            "evidence_in_context": evidence,
            "context_excerpt": "",
            "audition_test": "Rehearse the exchange with a scene partner. Review listening, pauses, interruption timing and response handoffs without judging the dialogue's emotional meaning.",
            "director_watchpoint": "Does the performer listen and respond at the appropriate conversational beat while maintaining clear turn-taking?",
            "status": "structural screenplay observation — director review required",
        })

    # Dialogue volume is a structural fact, not a personality inference.
    if dialogue_blocks >= 2 or dialogue_words >= 35:
        title, watchpoint = CHARACTER_INTERPRETATIONS["dialogue-heavy scene"]
        cues.append({
            "requirement": "dialogue-heavy scene",
            "characteristic": title,
            "evidence_items": [{
                "excerpt": f"{dialogue_blocks} dialogue block(s), approximately {dialogue_words} spoken word(s) attributed to {character_name}.",
                "matched_words": [],
                "source": "Screenplay speaker-cue structure",
            }],
            "evidence_in_context": f"{dialogue_blocks} dialogue block(s); approximately {dialogue_words} spoken word(s).",
            "context_excerpt": "",
            "audition_test": AUDITION_TESTS["dialogue-heavy scene"],
            "director_watchpoint": watchpoint,
            "status": "structural screenplay observation",
        })

    return cues, ambiguous_actions


def extract_pdf_text(uploaded_file):
    reader = PdfReader(io.BytesIO(uploaded_file.getvalue()))
    return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip(), len(reader.pages)


def normalize_name(name):
    name = re.sub(r"\([^)]*\)", "", name).strip(" .:-\t")
    name = re.sub(r"\s+", " ", name)
    return name[:60]


def parse_screenplay(story, manually_entered_names=""):
    """
    Deterministic screenplay parser.
    It attributes action only when the character is explicitly named and dialogue by speaker cue.
    Ambiguous pronouns are deliberately left unattributed rather than copied across profiles.
    """
    lines = [line.rstrip() for line in story.splitlines()]
    names = []
    cue_pattern = re.compile(
        r"^[ \t]{0,12}\*{0,2}([A-Z][A-Z0-9 ._'’-]{1,35}?)"
        r"(?:\s*\([^)]*\))?\s*:?\*{0,2}[ \t]*$"
    )
    excluded = {
        "INT", "EXT", "INT./EXT", "EXT./INT", "CUT TO", "FADE IN", "FADE OUT",
        "CONTINUED", "CONT'D", "THE END", "MONTAGE", "DAY", "NIGHT", "LATER",
        "CONTINUOUS", "MORNING", "EVENING",
    }
    # Ignore title, genre, cast-list and metadata lines before the screenplay
    # body. Character speaker cues are collected from the first scene onward.
    first_scene_index = next(
        (i for i, candidate in enumerate(lines) if _SCENE_HEADING_RE.match(candidate.strip())),
        None,
    )
    screenplay_marker_index = next(
        (i for i, candidate in enumerate(lines) if candidate.strip().casefold() == "screenplay"),
        None,
    )
    if first_scene_index is not None:
        character_scan_start = first_scene_index
    elif screenplay_marker_index is not None:
        character_scan_start = screenplay_marker_index + 1
    else:
        character_scan_start = 0

    for line_index, line in enumerate(lines):
        if line_index < character_scan_start:
            continue
        stripped = line.strip()
        if not stripped or len(stripped) > 38:
            continue
        match = cue_pattern.match(line)
        if not match:
            # Also accept inline dialogue labels such as **MAYA:** followed by dialogue.
            inline_match = re.match(
                r"^\s*\*{0,2}([A-Z][A-Z0-9 ._'’-]{1,35}?)"
                r"(?:\s*\([^)]*\))?\s*:\*{0,2}\s+\S",
                line,
            )
            if not inline_match:
                continue
            raw = normalize_name(inline_match.group(1))
        else:
            raw = normalize_name(match.group(1))
        upper = raw.upper()
        if upper in excluded or upper in {"SCREENPLAY", "SCRIPT", "THE END", "END", "TITLE"}:
            continue
        if upper.startswith(("INT. ", "EXT. ", "INT/EXT")):
            continue
        if any(upper.startswith(prefix) for prefix in ["INT ", "EXT ", "FADE ", "CUT ", "DISSOLVE ", "SMASH CUT"]):
            continue
        if upper in {"CONTINUED", "CONTINUOUS", "SAME", "LATER", "DAY", "NIGHT", "MORNING", "EVENING"}:
            continue
        # A character cue must introduce dialogue; this excludes title cards,
        # screenplay labels, scene headings and closing markers.
        following = line_index + 1
        while following < len(lines) and not lines[following].strip():
            following += 1
        while following < len(lines) and re.fullmatch(r"\s*\([^)]{1,100}\)\s*", lines[following]):
            following += 1
        if following >= len(lines):
            continue
        next_text = lines[following].strip()
        if (not next_text or cue_pattern.match(lines[following])
                or _SCENE_HEADING_RE.match(next_text)
                or next_text.upper().startswith(("FADE ", "CUT TO", "DISSOLVE ", "SMASH CUT"))):
            continue
        if len(raw.split()) > 4:
            continue
        if raw.casefold() not in {n.casefold() for n in names}:
            names.append(raw.title() if raw.isupper() else raw)

    for raw in re.split(r"[,;\n]+", manually_entered_names or ""):
        name = normalize_name(raw)
        if name and name.casefold() not in {n.casefold() for n in names}:
            names.append(name)

    names = names[:20]
    scene_count = sum(1 for line in lines if _SCENE_HEADING_RE.match(line))
    character_profiles = []
    for name in names:
        cues, ambiguous = extract_character_specific_cues(story, name, names)
        name_re = _character_name_pattern(name)
        explicit_mentions = len(name_re.findall(story))
        speaker_mentions = sum(
            1 for line in lines
            if normalize_name(re.sub(r"\([^)]*\)", "", line.strip())).casefold() == name.casefold()
        )
        characteristics = list(dict.fromkeys(
            cue["characteristic"] for cue in cues
        ))
        watchpoints = list(dict.fromkeys(
            cue["director_watchpoint"] for cue in cues
        ))
        character_profiles.append({
            "name": name,
            "mention_count": explicit_mentions + speaker_mentions,
            "role_in_story": "Not inferred automatically",
            "character_description": (
                "Potential performance characteristics are derived only from the evidence listed below. "
                "They are audition considerations, not fixed personality labels."
                if cues else
                "The screenplay did not provide enough clearly attributable evidence for an automatic profile."
            ),
            "potential_characteristics": characteristics,
            "director_watchpoints": watchpoints,
            "performance_requirements": cues,
            "ambiguous_action_count": len(ambiguous),
            "ambiguous_action_examples": ambiguous[:5],
            "limitations": (
                "Actions are attributed only when this character is explicitly named in an action sentence, "
                "or when a delivery direction appears in this character's speaker block. Ambiguous pronouns "
                "and unclear shared actions are not guessed. Clearly named participants in shared blocking or interactions receive separate role-specific cues. Dialogue content is not treated as proof of personality."
            ),
        })

    return {
        "method": "Deterministic screenplay-structure and explicit-evidence analysis; no LLM or trained semantic model",
        "story_characters": character_profiles,
        "screenplay_scene_heading_count": scene_count,
        "notes": [
            "Character dialogue is attributed from standalone screenplay speaker cues.",
            "Stage directions are attributed when the character is explicitly named; shared blocking and interactions are split into role-specific cues when the participants and action are clear.",
            "Ambiguous pronouns (for example, 'she', 'he' or 'they') are not guessed or copied between characters.",
            "Potential characteristics are cautious performance prompts supported by visible screenplay evidence, not personality diagnoses.",
            "Dialogue content alone is not used to claim a character is brave, dishonest, loving, aggressive or otherwise psychologically defined.",
            "Review every suggested interpretation against the complete scene before using it in casting.",
        ],
    }


def build_requirement_evidence(targets, video_report):
    """Compare role targets with observable video features; this is not a talent score."""
    movement = video_report.get("mean_normalized_landmark_movement_index")
    wrist_fraction = video_report.get("fraction_samples_with_wrist_above_shoulder")
    shoulder_tilt = video_report.get("mean_shoulder_tilt_index")
    evidence_rows = []
    for target in targets:
        observed = None
        metric = "Not available"
        interpretation = "No corresponding measurement is available."
        threshold = None
        if target == "More visible body movement":
            metric, observed, threshold = "Mean normalized landmark movement index", movement, 0.025
            if observed is None:
                interpretation = "Movement measurement unavailable."
            elif observed >= threshold:
                interpretation = "Movement index is at or above the exploratory threshold."
            else:
                interpretation = "Movement index is below the exploratory threshold."
        elif target == "Less visible body movement / controlled stillness":
            metric, observed, threshold = "Mean normalized landmark movement index", movement, 0.025
            if observed is None:
                interpretation = "Movement measurement unavailable."
            elif observed < threshold:
                interpretation = "Movement index is below the exploratory threshold."
            else:
                interpretation = "Movement index is at or above the exploratory threshold."
        elif target == "Frequent hands above shoulder level":
            metric, observed, threshold = "Fraction of sampled frames with a wrist above shoulder", wrist_fraction, 0.25
            if observed is None:
                interpretation = "Hand measurement unavailable."
            elif observed >= threshold:
                interpretation = "Wrist-above-shoulder observation is at or above the exploratory threshold."
            else:
                interpretation = "Wrist-above-shoulder observation is below the exploratory threshold."
        elif target == "More level shoulder alignment":
            metric, observed, threshold = "Mean shoulder tilt index", shoulder_tilt, 0.04
            if observed is None:
                interpretation = "Shoulder measurement unavailable."
            elif observed < threshold:
                interpretation = "Measured shoulder tilt is below the exploratory threshold."
            else:
                interpretation = "Measured shoulder tilt is at or above the exploratory threshold."
        evidence_rows.append({
            "Role requirement": target,
            "Measured feature": metric,
            "Observed value": round(observed, 4) if isinstance(observed, (int, float)) else observed,
            "Exploratory threshold": threshold,
            "Rule-based observation": interpretation,
        })
    return evidence_rows



def build_timestamped_evidence(targets, video_report):
    """Summarize timestamps where a measurable target's proxy is observed."""
    observations = video_report.get("sample_observations", [])
    rows = []
    for target in targets:
        matches = []
        for item in observations:
            if not item.get("pose_detected"):
                continue
            if target == "More visible body movement":
                value = item.get("movement_since_previous_sample_index")
                if isinstance(value, (int, float)) and value >= 0.025:
                    matches.append(item.get("timestamp_seconds"))
            elif target == "Less visible body movement / controlled stillness":
                value = item.get("movement_since_previous_sample_index")
                if isinstance(value, (int, float)) and value < 0.025:
                    matches.append(item.get("timestamp_seconds"))
            elif target == "Frequent hands above shoulder level" and item.get("wrist_above_shoulder") is True:
                matches.append(item.get("timestamp_seconds"))
            elif target == "More level shoulder alignment":
                value = item.get("shoulder_tilt_index")
                if isinstance(value, (int, float)) and value < 0.04:
                    matches.append(item.get("timestamp_seconds"))
        if matches:
            times = ", ".join(f"{t:.1f}s" for t in matches[:20] if isinstance(t, (int, float)))
            note = f"Proxy observed at {len(matches)} sampled timestamp(s): {times}"
            if len(matches) > 20:
                note += f" … (+{len(matches) - 20} more)"
        elif target in ("More visible body movement", "Less visible body movement / controlled stillness"):
            note = "No matching sampled movement observations were found. The first detected pose has no previous sample for comparison, and samples without comparable landmarks are omitted."
        else:
            note = "No matching observation found in sampled frames, or pose was not detected."
        rows.append({"Role requirement": target, "Timestamp evidence": note})
    return rows


# ---------- Story input ----------
with workflow_tabs[0]:
    _rasa_section_heading("01", "SCREENPLAY WORKSPACE", "Add a film story / screenplay")
    source = st.radio("Story input method", ["Paste story / screenplay", "Upload screenplay PDF"], horizontal=True)
    story_text = ""
    if source == "Paste story / screenplay":
        story_text = st.text_area("Paste screenplay text", height=230, placeholder="For best automatic character-cue detection, use screenplay format with character names on their own ALL-CAPS lines.")
    else:
        pdf = st.file_uploader("Upload screenplay PDF", type=["pdf"], key="story_pdf")
        if pdf:
            try:
                story_text, pages = extract_pdf_text(pdf)
                st.caption(f"Extracted selectable text from {pages} page(s). Scanned PDFs need OCR, which is not included.")
                with st.expander("Preview extracted text"):
                    st.text(story_text[:10000])
            except Exception as exc:
                st.error(f"Could not read PDF: {exc}")
    manual_names = st.text_input("Character names (optional; comma-separated)", placeholder="e.g. MAYA, ARJUN, INSPECTOR RAO")
    st.caption("Use this field if the story is prose, or if character names are not formatted as ALL-CAPS screenplay cues.")

    if st.button("Parse screenplay with rules", type="primary", disabled=len(story_text.strip()) < 20):
        st.session_state["rasa_story_report"] = parse_screenplay(story_text, manual_names)
        st.session_state["rasa_story_text"] = story_text

    story_report = st.session_state.get("rasa_story_report")

    # Keep the workflow numbering stable: sections 1–4 are always visible.
with workflow_tabs[1]:
    _rasa_section_heading("02", "DIRECTOR'S CHARACTER BREAKDOWN", "Character Performance Intelligence")
    if story_report:
        characters = story_report.get("story_characters", [])
        st.write(
            f"Analysed **{len(characters)} character profile(s)** across "
            f"**{story_report['screenplay_scene_heading_count']} scene heading(s)**."
        )
        st.caption(
            "Each observation below is tied to screenplay evidence. Shared actions are attributed "
            "to each clearly identified participant; unclear actions and ambiguous pronouns remain unassigned."
        )

        for i, character in enumerate(characters, 1):
            cues = character.get("performance_requirements", [])
            with st.expander(
                f"{i:02d}  ·  {character['name']}  ·  {len(cues)} supported performance cue(s)",
                expanded=(i == 1),
            ):
                st.markdown(f"### {character['name']}")
                st.write(character["character_description"])

                if character.get("potential_characteristics"):
                    st.markdown("**Potential performance characteristics**")
                    cols = st.columns(min(3, len(character["potential_characteristics"])))
                    for idx, characteristic in enumerate(character["potential_characteristics"]):
                        with cols[idx % len(cols)]:
                            st.markdown(
                                f"""
                                <div style="padding:.8rem .9rem;min-height:76px;border:1px solid rgba(135,164,220,.28);
                                border-radius:12px;background:linear-gradient(145deg,rgba(35,55,86,.72),rgba(19,31,49,.82));
                                color:#eaf1ff;font-weight:750;">{html.escape(characteristic)}</div>
                                """,
                                unsafe_allow_html=True,
                            )

                if cues:
                    st.markdown("**Screenplay evidence and director's watchpoints**")
                    for cue_index, req in enumerate(cues, 1):
                        st.markdown(f"**{cue_index}. {html.escape(req.get('characteristic', req['requirement']))}**")
                        for evidence in req.get("evidence_items", []):
                            excerpt = evidence.get("excerpt", "")
                            source_label = evidence.get("source", "Screenplay evidence")
                            st.markdown(
                                f"""
                                <div style="margin:.35rem 0 .55rem;padding:.75rem .9rem;border-left:3px solid #80adf5;
                                border-radius:0 10px 10px 0;background:rgba(26,42,65,.72);">
                                  <div style="color:#a9c8ff;font-size:.72rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;">
                                    {html.escape(source_label)}
                                  </div>
                                  <div style="color:#edf3ff;margin-top:.25rem;">“{html.escape(excerpt)}”</div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )
                        st.markdown(
                            '<div class="rasa-important-note">'
                            '<strong>Director\'s watchpoint:</strong> '
                            f'{html.escape(str(req.get("director_watchpoint", "Review the evidence in scene context.")))}'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(
                            '<div class="rasa-important-note">'
                            '<strong>Suggested audition exercise:</strong> '
                            f'{html.escape(str(req.get("audition_test", "Review the relevant scene.")))}'
                            '</div>',
                            unsafe_allow_html=True,
                        )
                        st.divider()
                else:
                    st.info(
                        "No clearly attributable performance evidence was found for this character. "
                        "This is preferable to inventing traits from nearby text. Review the screenplay "
                        "format or add director-defined requirements in the Casting Brief."
                    )

                if character.get("ambiguous_action_count"):
                    st.warning(
                        f"{character['ambiguous_action_count']} action sentence(s) also mention another "
                        "known character and were not automatically assigned. Review these in the original scene."
                    )
                    for excerpt in character.get("ambiguous_action_examples", []):
                        st.markdown(
                            '<div class="rasa-important-note">'
                            '<strong>Unassigned shared action:</strong> '
                            f'{html.escape(str(excerpt))}'
                            '</div>',
                            unsafe_allow_html=True,
                        )

                with st.expander("How this profile was built", expanded=False):
                    st.caption(character["limitations"])

        st.markdown("""
        <style>
        .rasa-analysis-method {
            margin: .35rem 0 .65rem;
            padding: 1rem 1.15rem;
            border: 1px solid rgba(135, 164, 220, .26);
            border-left: 4px solid #83adff;
            border-radius: 14px;
            background: linear-gradient(145deg, #192437, #121d2d);
        }
        .rasa-analysis-method h3 {
            margin: 0 0 .55rem 0;
            padding: 0;
            color: #f3f6ff;
            font-size: 1.22rem;
            font-weight: 850;
            line-height: 1.3;
        }
        .rasa-analysis-method ul {
            margin: 0;
            padding-left: 1.2rem;
        }
        .rasa-analysis-method li {
            margin: 0;
            padding: .18rem 0;
            color: #cbd7eb;
            font-size: .91rem;
            line-height: 1.45;
        }
        </style>
        """, unsafe_allow_html=True)

        notes_html = "".join(
            f"<li>{html.escape(str(note))}</li>"
            for note in story_report["notes"]
        )
        st.markdown(
            '<div class="rasa-analysis-method">'
            '<h3>Analysis method and limitations</h3>'
            f'<ul>{notes_html}</ul>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            "Download screenplay analysis (JSON)",
            json.dumps(story_report, indent=2, ensure_ascii=False),
            "rasaai_screenplay_analysis.json",
            "application/json",
        )
    else:
        st.info(
            "Add a screenplay in the Screenplay workspace and select **Parse screenplay**. "
            "Character profiles will then show evidence-backed performance characteristics and audition watchpoints."
        )

    # ---------- Explicit role requirements for transparent matching ----------
with workflow_tabs[2]:
    _rasa_section_heading("03", "CASTING BRIEF", "Define role requirements")
    if story_report and story_report.get("story_characters"):
        st.write("Choose observable requirements for the selected role. These are filmmaker-defined targets, not automatically inferred acting judgments.")
        requirement_options = [
            "More visible body movement",
            "Less visible body movement / controlled stillness",
            "Frequent hands above shoulder level",
            "More level shoulder alignment",
            "Frequent mouth opening / visible mouth movement",
            "Greater variation in eye openness",
            "Greater variation in eyebrow-to-eye spacing",
        ]
        cue_to_targets = {
            "high movement": ["More visible body movement"],
            "stillness / controlled posture": ["Less visible body movement / controlled stillness"],
            "hand gestures": ["Frequent hands above shoulder level"],
        }
        role_requirements = {}
        for idx, character in enumerate(story_report["story_characters"]):
            with st.expander(f"Requirements for {character['name']}", expanded=(len(story_report["story_characters"]) == 1)):
                detected_cues = character.get("performance_requirements", [])
                suggested = []
                for cue in detected_cues:
                    suggested.extend(cue_to_targets.get(cue.get("requirement"), []))
                suggested = list(dict.fromkeys(suggested))
                if detected_cues:
                    st.caption("Text cues found near this character (verify manually): " + ", ".join(cue.get("requirement", "") for cue in detected_cues))
                if suggested:
                    st.info("Suggested measurable targets are preselected from nearby screenplay cues. Review them before using.")
                selected_targets = st.multiselect(
                    "Select measurable audition targets",
                    requirement_options,
                    default=suggested,
                    key=f"role_requirements_{idx}_" + re.sub(r"[^a-zA-Z0-9_]", "_", character["name"]),
                    help="Targets map only to rough video measurements. They do not determine talent, emotion, personality, or casting suitability.",
                )
                custom_targets_text = st.text_area(
                    "Write your own requirement",
                    placeholder="Describe an additional role-specific requirement in your own words. Enter multiple requirements on separate lines.",
                    key=f"custom_role_requirements_{idx}_" + re.sub(r"[^a-zA-Z0-9_]", "_", character["name"]),
                    height=105,
                )
                custom_targets = [
                    item.strip() for item in custom_targets_text.splitlines()
                    if item.strip()
                ]
                role_requirements[character["name"]] = list(dict.fromkeys(selected_targets + custom_targets))
        st.session_state["rasa_role_requirements"] = role_requirements

        st.subheader("Character emotion-performance brief")
        st.caption("Choose the intended portrayal to create a human-review checklist. This is not an automatic emotion detector and does not diagnose the actor.")
        portrayal_options = [
            "Sadness / grief",
            "Anxiety / fear",
            "Anger / confrontation",
            "Joy / excitement",
            "Restrained / stoic performance",
            "Other / mixed emotional state",
        ]
        selected_portrayal = st.selectbox(
            "What emotional portrayal does the scene call for?",
            portrayal_options,
            key="rasa_character_portrayal_intent",
        )
        custom_portrayal = st.text_area(
            "Write your own emotional / performance brief",
            placeholder=(
                "Describe the exact portrayal you want the actor to explore, "
                "including emotional shifts, intensity, restraint, or scene-specific nuances."
            ),
            key="rasa_custom_portrayal_brief",
            height=110,
        )
        review_guides = {
            "Sadness / grief": [
                "Review whether facial changes, gaze and posture fit the scene context; do not treat lowered gaze or reduced movement as proof of sadness.",
                "Check the actor's choices at the relevant dialogue and action beats.",
                "Consider whether the performance changes appropriately across the scene rather than remaining uniformly still.",
            ],
            "Anxiety / fear": [
                "Review timing and context of visible facial and body changes.",
                "Check whether movement, gaze and pauses fit the character's stated objective and scene beats.",
                "Do not interpret eye openness or movement alone as proof of fear.",
            ],
            "Anger / confrontation": [
                "Review facial and body changes at confrontation beats.",
                "Check whether gesture intensity and timing fit the director's brief.",
                "Do not treat eyebrow spacing or mouth opening alone as proof of anger.",
            ],
            "Joy / excitement": [
                "Review visible facial changes and gesture timing in scene context.",
                "Check whether changes align with the character's reactions and dialogue.",
                "A smile or increased movement alone does not establish joy or convincing acting.",
            ],
            "Restrained / stoic performance": [
                "Review whether facial and body changes are controlled in the intended moments.",
                "Check for meaningful variation at scripted beats; low movement alone is not proof of restraint.",
                "Consider dialogue delivery and scene context during human review.",
            ],
            "Other / mixed emotional state": [
                "Write down the specific visible performance cues expected by the director.",
                "Review timestamped evidence against scene beats and dialogue.",
                "Do not infer an internal emotional state from facial geometry alone.",
            ],
        }
        brief_heading = selected_portrayal
        if custom_portrayal.strip():
            brief_heading += " + director's custom brief"
        st.markdown(f"**Human-review checklist for: {brief_heading}**")
        for guide in review_guides[selected_portrayal]:
            st.markdown(f"- {guide}")
        if custom_portrayal.strip():
            st.markdown("**Director's custom portrayal brief**")
            st.markdown(custom_portrayal.strip())
        custom_review_points = []
        st.session_state["rasa_character_emotion_brief"] = {
            "selected_portrayal": selected_portrayal,
            "custom_portrayal": custom_portrayal.strip(),
            "review_checklist": review_guides[selected_portrayal] + custom_review_points,
        }
        # The selectbox key already stores this value in session_state.
        # Do not assign to it after the widget has been instantiated.
    else:
        st.info("After screenplay parsing, this section will let you define measurable performance requirements for each detected character.")

    # ---------- Local computer vision ----------
with workflow_tabs[3]:
    _rasa_section_heading("04", "VISUAL REVIEW", "Upload an actor audition video")
    st.write("Upload an audition clip with the actor's consent. RasaAI measures body movement and facial geometry. Optional FER mode adds model-estimated facial-expression labels for human review; these are uncertain visual predictions, not proof of internal emotion or acting ability.")
    character_options = [c["name"] for c in story_report.get("story_characters", [])] if story_report else []
    selected_character = st.selectbox("Character being auditioned for", character_options, key="selected_character") if character_options else st.text_input("Character being auditioned for", placeholder="Enter character name")
    actor_label = st.text_input("Actor / audition label", placeholder="e.g., Audition A or actor name", key="rasa_actor_label")
    actor_video = st.file_uploader("Choose actor video", type=["mp4", "mov", "avi", "m4v"], key="actor_video")
    if actor_video:
        video_bytes = actor_video.getvalue()
        video_suffix = Path(actor_video.name).suffix.lower() or ".mp4"
        video_format = {
            ".mp4": "video/mp4", ".m4v": "video/mp4",
            ".mov": "video/quicktime", ".avi": "video/x-msvideo",
        }.get(video_suffix, "application/octet-stream")

        # Persist the original upload inside this authenticated user's private vault.
        # A content hash prevents repeated Streamlit reruns from writing duplicate files.
        media_dir = _USER_DATA_DIR / "media"
        media_dir.mkdir(parents=True, exist_ok=True)
        video_digest = hashlib.sha256(video_bytes).hexdigest()
        safe_video_name = Path(actor_video.name).name.replace("\\x00", "") or "audition_video"
        source_video_path = media_dir / f"{video_digest[:20]}_{safe_video_name}"
        if not source_video_path.is_file():
            source_video_path.write_bytes(video_bytes)

        # Prefer a persistent browser-friendly H.264 MP4 when FFmpeg is available.
        # Keep the original file as a fallback; neither file is deleted on reruns.
        playable_video_path = source_video_path
        # Never let an extracted audio track from a previous upload appear
        # as the vocal track for a newly selected video.
        if st.session_state.get("rasa_video_audio_digest") != video_digest:
            st.session_state["rasa_video_audio_bytes"] = None
            st.session_state["rasa_video_audio_name"] = None
            st.session_state["rasa_video_audio_digest"] = None

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            st.info(
                "FFmpeg is unavailable. The original saved video will be used. "
                "H.264 MP4 provides the widest browser playback compatibility."
            )
        else:
            converted_video_path = media_dir / f"{video_digest[:20]}_browser.mp4"
            if not converted_video_path.is_file() or converted_video_path.stat().st_size == 0:
                try:
                    result = subprocess.run(
                        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_video_path),
                         "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "ultrafast",
                         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                         str(converted_video_path)],
                        capture_output=True, text=True, timeout=180,
                    )
                    if (result.returncode != 0 or not converted_video_path.is_file()
                            or converted_video_path.stat().st_size <= 0):
                        detail = (result.stderr or "Unknown FFmpeg conversion error").strip()[-1200:]
                        st.warning(
                            "Browser-compatible conversion was unavailable; using the original saved video. "
                            f"Details: {detail}"
                        )
                        converted_video_path.unlink(missing_ok=True)
                    else:
                        playable_video_path = converted_video_path
                except Exception as convert_exc:
                    st.warning(
                        "Video conversion failed; using the original saved video. "
                        f"{type(convert_exc).__name__}: {convert_exc}"
                    )
                    converted_video_path.unlink(missing_ok=True)
            else:
                playable_video_path = converted_video_path

            # Extract audio from this same audition take once per uploaded video.
            # The extracted bytes remain available to the Vocal Analysis tab.
            if st.session_state.get("rasa_video_audio_digest") != video_digest:
                st.session_state["rasa_video_audio_bytes"] = None
                st.session_state["rasa_video_audio_name"] = None
                extracted_audio_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as audio_tmp:
                        extracted_audio_path = audio_tmp.name
                    audio_result = subprocess.run(
                        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source_video_path),
                         "-vn", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", extracted_audio_path],
                        capture_output=True, text=True, timeout=120,
                    )
                    if (audio_result.returncode == 0 and os.path.exists(extracted_audio_path)
                            and os.path.getsize(extracted_audio_path) > 44):
                        st.session_state["rasa_video_audio_bytes"] = Path(extracted_audio_path).read_bytes()
                        st.session_state["rasa_video_audio_name"] = f"{Path(actor_video.name).stem}_audio.wav"
                        st.session_state["rasa_video_audio_digest"] = video_digest
                    else:
                        detail = (audio_result.stderr or "No audio stream was found.").strip()[-500:]
                        st.caption(f"No extractable audio track was found in this video. {detail}")
                        st.session_state["rasa_video_audio_digest"] = video_digest
                except Exception as audio_exc:
                    st.warning(f"Could not extract the video's audio: {type(audio_exc).__name__}: {audio_exc}")
                finally:
                    if extracted_audio_path and os.path.exists(extracted_audio_path):
                        try:
                            os.unlink(extracted_audio_path)
                        except OSError:
                            pass

        if st.session_state.get("rasa_video_audio_bytes"):
            st.caption("Audio track extracted from this video is available in the Vocal Analysis tab.")

        st.caption(f"Selected: {actor_video.name} · {actor_video.size / (1024 * 1024):.1f} MB")
        st.caption(f"Saved in your private vault: {source_video_path.name}")
        st.warning("For comparisons, use similar framing, lighting, camera distance and audition instructions for every actor.")
        enable_fer = st.checkbox(
            "Also run experimental facial-expression model (requires the optional 'fer' package)",
            value=False,
            help="Runs a pretrained expression classifier on sampled frames. Outputs can be wrong, especially during speech, with poor lighting, or with occlusion. Use only as review evidence.",
        )
        if st.button("Analyze video locally", type="primary"):
            cap = None
            try:
                import cv2
                import mediapipe as mp
                import numpy as np
                emotion_detector = None
                fer_enabled = False
                if enable_fer:
                    try:
                        from fer import FER
                        emotion_detector = FER(mtcnn=False)
                        fer_enabled = True
                    except Exception as fer_exc:
                        st.warning(
                            "FER facial-expression analysis could not be loaded in this deployment "
                            f"({type(fer_exc).__name__}: {fer_exc}). Continuing with body-movement "
                            "and facial-geometry analysis only. Check the pinned FER/TensorFlow "
                            "dependencies in requirements.txt and redeploy."
                        )
                # Analyze the exact persistent file used by the player and preview.
                cap = cv2.VideoCapture(str(playable_video_path))
                fps = cap.get(cv2.CAP_PROP_FPS) or 0
                total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
                duration = total_frames / fps if fps > 0 else 0
                sample_every = max(1, int(fps)) if fps > 0 else 24
                frame_index = checked = detected = 0
                face_detected = 0
                previous_points = None
                movements, shoulder_tilts, torso_offsets, wrist_above = [], [], [], []
                mouth_open_ratios, eye_openness_values, brow_eye_distances = [], [], []
                emotion_scores_by_label = {}
                emotion_predictions = []
                observations = []
                pose_api = mp.solutions.pose
                face_api = mp.solutions.face_mesh
                def point_distance(a, b):
                    return float(np.hypot(a.x - b.x, a.y - b.y))
                with pose_api.Pose(static_image_mode=False, model_complexity=1, enable_segmentation=False, min_detection_confidence=0.5, min_tracking_confidence=0.5) as pose, face_api.FaceMesh(static_image_mode=False, max_num_faces=1, refine_landmarks=True, min_detection_confidence=0.5, min_tracking_confidence=0.5) as face_mesh:
                    while cap.isOpened():
                        ok, frame = cap.read()
                        if not ok:
                            break
                        current = frame_index
                        frame_index += 1
                        if current % sample_every:
                            continue
                        checked += 1
                        timestamp = current / fps if fps > 0 else float(current)
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        model_emotion = None
                        model_emotion_scores = None
                        if emotion_detector is not None:
                            try:
                                face_predictions = emotion_detector.detect_emotions(frame)
                                if face_predictions:
                                    raw_scores = face_predictions[0].get("emotions", {})
                                    if raw_scores:
                                        model_emotion_scores = {str(k): round(float(v), 4) for k, v in raw_scores.items()}
                                        model_emotion = max(model_emotion_scores, key=model_emotion_scores.get)
                                        emotion_predictions.append({"timestamp_seconds": round(timestamp, 1), "label": model_emotion, "scores": model_emotion_scores})
                                        for label, score in model_emotion_scores.items():
                                            emotion_scores_by_label.setdefault(label, []).append(score)
                            except Exception:
                                # A single frame's model failure should not stop pose/facial-geometry analysis.
                                pass
                        result = pose.process(rgb_frame)
                        face_result = face_mesh.process(rgb_frame)
                        face_metrics = {"face_detected": False, "mouth_opening_ratio": None, "eye_openness_proxy": None, "brow_eye_spacing_proxy": None, "model_expression_label": model_emotion, "model_expression_scores": model_emotion_scores}
                        if face_result.multi_face_landmarks:
                            face_detected += 1
                            flm = face_result.multi_face_landmarks[0].landmark
                            # Ratios are normalized to facial dimensions, reducing—but not removing—scale effects.
                            mouth_width = point_distance(flm[61], flm[291])
                            if mouth_width > 1e-6:
                                mouth_ratio = point_distance(flm[13], flm[14]) / mouth_width
                                mouth_open_ratios.append(mouth_ratio)
                                face_metrics["mouth_opening_ratio"] = round(mouth_ratio, 4)
                            def ear(indices):
                                p1,p2,p3,p4,p5,p6 = [flm[i] for i in indices]
                                horizontal = point_distance(p1,p4)
                                return ((point_distance(p2,p6) + point_distance(p3,p5)) / (2 * horizontal)) if horizontal > 1e-6 else None
                            ears = [v for v in (ear([33,160,158,133,153,144]), ear([362,385,387,263,373,380])) if v is not None]
                            if ears:
                                eye_value = float(np.mean(ears))
                                eye_openness_values.append(eye_value)
                                face_metrics["eye_openness_proxy"] = round(eye_value, 4)
                            # Average vertical brow-to-upper-eye spacing, normalized by face width.
                            face_width = point_distance(flm[234], flm[454])
                            if face_width > 1e-6:
                                spacing = float(np.mean([abs(flm[105].y-flm[159].y), abs(flm[334].y-flm[386].y)]) / face_width)
                                brow_eye_distances.append(spacing)
                                face_metrics["brow_eye_spacing_proxy"] = round(spacing, 4)
                        if not result.pose_landmarks:
                            observations.append({"timestamp_seconds": round(timestamp, 1), "pose_detected": False, **face_metrics})
                            continue
                        detected += 1
                        lm = result.pose_landmarks.landmark
                        get = lambda key: lm[getattr(pose_api.PoseLandmark, key).value]
                        ls, rs, lh, rh = get("LEFT_SHOULDER"), get("RIGHT_SHOULDER"), get("LEFT_HIP"), get("RIGHT_HIP")
                        lw, rw = get("LEFT_WRIST"), get("RIGHT_WRIST")
                        shoulder_tilt = abs(ls.y - rs.y)
                        shoulder_tilts.append(shoulder_tilt)
                        shoulder_mid_x = (ls.x + rs.x) / 2
                        hip_mid_x = (lh.x + rh.x) / 2
                        torso_offset = abs(shoulder_mid_x - hip_mid_x)
                        torso_offsets.append(torso_offset)
                        above = bool(lw.y < ls.y or rw.y < rs.y)
                        wrist_above.append(above)
                        points = np.array([[p.x, p.y] for p in lm if p.visibility > 0.5], dtype=float)
                        # Normalize coordinates around the shoulder midpoint and by shoulder width.
                        # This reduces (but does not eliminate) sensitivity to camera distance.
                        shoulder_width = float(np.hypot(ls.x - rs.x, ls.y - rs.y))
                        shoulder_midpoint = np.array([(ls.x + rs.x) / 2, (ls.y + rs.y) / 2], dtype=float)
                        normalized_points = None
                        if points.size and shoulder_width > 1e-4:
                            normalized_points = (points - shoulder_midpoint) / shoulder_width
                        sample_movement = None
                        if normalized_points is not None and previous_points is not None and normalized_points.shape == previous_points.shape and normalized_points.size:
                            sample_movement = float(np.mean(np.linalg.norm(normalized_points - previous_points, axis=1)))
                            movements.append(sample_movement)
                        previous_points = normalized_points
                        observations.append({
                            "timestamp_seconds": round(timestamp, 1),
                            "pose_detected": True,
                            "movement_since_previous_sample_index": round(sample_movement, 4) if sample_movement is not None else None,
                            "wrist_above_shoulder": above,
                            "shoulder_tilt_index": round(shoulder_tilt, 4),
                            "torso_lateral_offset": round(torso_offset, 4),
                            **face_metrics
                        })
                if cap:
                    cap.release()
                    cap = None
                if checked == 0:
                    st.error("Could not read video frames. Try a short MP4 using a common H.264 encoding.")
                else:
                    report = {
                        "video_file": actor_video.name,
                        "actor_label": actor_label.strip() or Path(actor_video.name).stem,
                        "selected_character": selected_character,
                        "duration_seconds_estimate": round(duration, 1),
                        "sample_interval_seconds_approx": 1,
                        "per_sample_movement_definition": "Mean Euclidean change between sampled visible landmarks after centering coordinates on the shoulder midpoint and dividing by shoulder width. Samples are compared only when landmark arrays have matching shapes. This reduces sensitivity to camera distance but remains sensitive to camera angle, framing, occlusion, tracking and body orientation.",
                        "sampled_frames": checked,
                        "frames_with_detected_pose": detected,
                        "pose_detection_rate": round(detected / checked, 3) if checked else None,
                        "frames_with_detected_face": face_detected,
                        "face_detection_rate": round(face_detected / checked, 3) if checked else None,
                        "mean_mouth_opening_ratio": round(float(np.mean(mouth_open_ratios)), 4) if mouth_open_ratios else None,
                        "mouth_opening_variability": round(float(np.std(mouth_open_ratios)), 4) if len(mouth_open_ratios) > 1 else None,
                        "mean_eye_openness_proxy": round(float(np.mean(eye_openness_values)), 4) if eye_openness_values else None,
                        "eye_openness_variability": round(float(np.std(eye_openness_values)), 4) if len(eye_openness_values) > 1 else None,
                        "mean_brow_eye_spacing_proxy": round(float(np.mean(brow_eye_distances)), 4) if brow_eye_distances else None,
                        "brow_eye_spacing_variability": round(float(np.std(brow_eye_distances)), 4) if len(brow_eye_distances) > 1 else None,
                        "mean_normalized_landmark_movement_index": round(float(np.mean(movements)), 4) if movements else None,
                        "mean_shoulder_tilt_index": round(float(np.mean(shoulder_tilts)), 4) if shoulder_tilts else None,
                        "mean_torso_lateral_offset": round(float(np.mean(torso_offsets)), 4) if torso_offsets else None,
                        "fraction_samples_with_wrist_above_shoulder": round(sum(wrist_above) / len(wrist_above), 3) if wrist_above else None,
                        "sample_observations": observations,
                        "facial_expression_model_enabled": bool(fer_enabled),
                        "facial_expression_model_mean_scores": {label: round(float(np.mean(scores)), 4) for label, scores in emotion_scores_by_label.items()},
                        "facial_expression_predictions": emotion_predictions,
                        "interpretation_limit": "Facial geometry metrics are not emotion labels. Optional FER model labels are probabilistic visual classifications and can be wrong due to lighting, camera angle, speech, occlusion, culture, individual differences and model bias. They do not diagnose depression or establish internal emotion, acting ability, personality, or role suitability. Use timestamped predictions as prompts for human review only."
                    }
                    st.session_state["rasa_video_report"] = report
                    st.success("Local video analysis complete.")
            except ImportError as exc:
                st.error(f"A required video dependency is missing: {exc}. Run pip install -r requirements.txt and restart the app.")
            except Exception as exc:
                st.error(f"Video analysis failed: {exc}")
                st.caption("Try a 10–30 second MP4 clip with the actor's upper body and hands visible.")
            finally:
                if cap is not None:
                    cap.release()

    video_report = st.session_state.get("rasa_video_report")
    if video_report:
        st.subheader("Observable movement and facial-feature report")
        c1, c2, c3 = st.columns(3)
        c1.metric("Clip duration", f"{video_report['duration_seconds_estimate']} s")
        c2.metric("Sampled frames", video_report["sampled_frames"])
        c3.metric("Pose detection", f"{video_report['pose_detection_rate'] * 100:.0f}%" if video_report.get("pose_detection_rate") is not None else "N/A")
        f1, f2, f3 = st.columns(3)
        f1.metric("Face detection", f"{video_report['face_detection_rate'] * 100:.0f}%" if video_report.get("face_detection_rate") is not None else "N/A")
        f2.metric("Mouth opening variability", str(video_report.get("mouth_opening_variability", "N/A")))
        f3.metric("Eye openness variability", str(video_report.get("eye_openness_variability", "N/A")))
        st.caption("Facial geometry is not an emotion label. Optional FER predictions are uncertain visual classifications and must be reviewed in context.")

        # Translate technical measurements into plain language for directors and casting reviewers.
        # This is descriptive evidence only: it must not infer internal emotion, acting quality,
        # personality, or role suitability from facial/body measurements.
        with st.container(border=True):
            st.subheader("What this analysis means — director's view")
            st.caption(
                "A plain-language guide to what the camera-based measurements noticed in this clip. "
                "Use it to decide what to rewatch, not to score or rank the actor."
            )
            director_notes = []

            pose_rate = video_report.get("pose_detection_rate")
            if isinstance(pose_rate, (int, float)):
                director_notes.append(
                    f"**Body visibility:** The actor's body pose could be followed in about {pose_rate * 100:.0f}% "
                    "of the sampled moments. This tells you how consistently the body was visible to the camera, "
                    "not how well the actor performed."
                )

            face_rate = video_report.get("face_detection_rate")
            if isinstance(face_rate, (int, float)):
                director_notes.append(
                    f"**Face visibility:** The face was detected in about {face_rate * 100:.0f}% of sampled moments. "
                    "A lower figure can happen when the face turns away, is obscured, is too small, or lighting is poor."
                )

            movement_value = video_report.get("mean_normalized_landmark_movement_index")
            if isinstance(movement_value, (int, float)):
                if movement_value < 0.025:
                    movement_text = (
                        "The sampled body landmarks changed relatively little from one sampled moment to the next. "
                        "On screen, this clip may read as physically contained or still."
                    )
                else:
                    movement_text = (
                        "The sampled body landmarks changed more noticeably from one sampled moment to the next. "
                        "There is visible body movement across the sampled moments."
                    )
                director_notes.append(
                    f"**Body movement:** {movement_text} This is only a rough movement indicator; "
                    "it cannot tell whether the movement is intentional, expressive, or appropriate for the scene."
                )

            wrist_fraction = video_report.get("fraction_samples_with_wrist_above_shoulder")
            if isinstance(wrist_fraction, (int, float)):
                director_notes.append(
                    f"**Hand gestures:** In about {wrist_fraction * 100:.0f}% of pose-detected samples, "
                    "at least one wrist was above shoulder level. This can help you locate moments with raised-hand "
                    "gestures; it does not explain what the gesture means."
                )

            shoulder_tilt = video_report.get("mean_shoulder_tilt_index")
            if isinstance(shoulder_tilt, (int, float)):
                director_notes.append(
                    "**Shoulder line:** The app measured how level or tilted the shoulders appeared in the sampled "
                    "frames. This describes visible alignment only; it is not a judgement about confidence, mood, "
                    "or posture quality."
                )

            mouth_variability = video_report.get("mouth_opening_variability")
            eye_variability = video_report.get("eye_openness_variability")
            if isinstance(mouth_variability, (int, float)) or isinstance(eye_variability, (int, float)):
                director_notes.append(
                    "**Facial movement:** The app tracked changes in mouth opening and eye openness. These are "
                    "small geometry measurements that may help you find moments to review, but they cannot establish "
                    "whether the actor is happy, sad, angry, afraid, sincere, or convincing."
                )

            if video_report.get("facial_expression_model_enabled"):
                predictions = video_report.get("facial_expression_predictions") or []
                if predictions:
                    director_notes.append(
                        f"**Experimental expression labels:** The optional model produced {len(predictions)} "
                        "timestamped visual labels. Treat each as a fallible prompt to rewatch that moment—not as "
                        "proof of what the actor felt or successfully portrayed."
                    )
                else:
                    director_notes.append(
                        "**Experimental expression labels:** The optional facial-expression model did not return "
                        "usable labels for this clip. No conclusion about the actor's expression should be drawn "
                        "from that part of the analysis."
                    )
            else:
                director_notes.append(
                    "**Experimental expression labels:** This optional model was not enabled, so this report does "
                    "not contain model-generated expression labels."
                )

            intended_portrayal_for_notes = st.session_state.get(
                "rasa_character_portrayal_intent", "Not specified"
            )
            if intended_portrayal_for_notes != "Not specified":
                director_notes.append(
                    f"**Director's intended portrayal:** You selected “{intended_portrayal_for_notes}”. "
                    "The measurements above describe visible movement and facial features; they do not confirm "
                    "whether the actor communicated that intended portrayal. Rewatch the relevant dialogue and scene beats."
                )

            for note in director_notes:
                st.markdown(f"- {note}")

            with st.expander("What this analysis cannot tell you"):
                st.markdown(
                    "- It cannot determine an actor's real feelings, thoughts, personality, honesty, or mental health.\n"
                    "- It cannot decide whether an actor is talented, convincing, suitable for a role, or should be cast.\n"
                    "- A low movement value is not automatically good or bad; stillness may be right for one scene and wrong for another.\n"
                    "- Camera angle, framing, lighting, occlusion, clip length, and the action in the scene can change the measurements.\n"
                    "- Use the timestamps and the original audition video for human review. Do not use these measurements as an automated casting decision."
                )

            st.markdown("### Does the observed expression align with the intended portrayal?")
            target_label_map = {
                "Sadness / grief": {"sad"},
                "Anxiety / fear": {"fear"},
                "Anger / confrontation": {"angry"},
                "Joy / excitement": {"happy"},
                "Restrained / stoic performance": {"neutral"},
            }
            target_portrayal = st.session_state.get(
                "rasa_character_portrayal_intent", "Other / mixed emotional state"
            )
            target_labels = target_label_map.get(target_portrayal, set())
            fer_predictions = video_report.get("facial_expression_predictions") or []
            review_threshold = float(st.session_state.get("rasa_fer_confidence_threshold", 0.60))
            usable_predictions = []
            aligned_predictions = 0

            for item in fer_predictions:
                predicted_label = str(item.get("label", "")).casefold()
                score_values = item.get("scores") or {}
                try:
                    top_score = max((float(value) for value in score_values.values()), default=None)
                except (TypeError, ValueError):
                    top_score = None
                if predicted_label and top_score is not None and top_score >= review_threshold:
                    usable_predictions.append(item)
                    if predicted_label in target_labels:
                        aligned_predictions += 1

            if not video_report.get("facial_expression_model_enabled"):
                st.info(
                    "No match conclusion is available because the optional facial-expression model was not enabled. "
                    "The movement and facial-geometry measurements cannot identify an emotion on their own."
                )
            elif not target_labels:
                st.info(
                    "Your selected brief is mixed or scene-specific, so there is no single emotion category to compare. "
                    "Review the timestamps against the character's emotional changes and dialogue."
                )
            elif not usable_predictions:
                st.warning(
                    f"The intended portrayal is **{target_portrayal}**, but the model returned no usable "
                    f"expression labels above the {review_threshold:.0%} review threshold. "
                    "The result is **inconclusive**, not a mismatch."
                )
            else:
                alignment = aligned_predictions / len(usable_predictions)
                if alignment >= 0.70:
                    alignment_text = "The model's labels show frequent category-level alignment"
                elif alignment >= 0.40:
                    alignment_text = "The model's labels show partial category-level alignment"
                else:
                    alignment_text = "The model's labels show limited category-level alignment"

                st.markdown(
                    f"**Intended portrayal:** {target_portrayal}  \n"
                    f"**Observed label alignment:** {aligned_predictions} of {len(usable_predictions)} "
                    f"usable samples ({alignment:.0%}).  \n"
                    f"**Plain-language takeaway:** {alignment_text} with the selected category."
                )
                st.caption(
                    "This compares experimental facial-expression labels with the selected category only. "
                    "It does not establish what the actor felt, whether the emotion was convincingly acted, "
                    "or whether the performance fulfilled the scene. A different expression may be correct "
                    "at a particular story beat. Check the timestamps and video yourself."
                )

            st.markdown("### Why this is useful in a real casting process")
            st.markdown(
                "**For a small audition:** If you are reviewing one or two actors, watching the clips carefully "
                "may be all you need. The value of this tool becomes clearer when the volume grows.\n\n"
                "**For a large audition:** When dozens or hundreds of actors apply, it becomes difficult to "
                "remember every clip and compare everyone consistently. RASA AI organizes observations, "
                "timestamps and review notes so a director can revisit comparable evidence and manage a "
                "human-led shortlist—for example, narrowing a large pool to 10 or 5 actors for closer review.\n\n"
                "**For actors:** Auditions can be affected by subjective impressions, inconsistent attention "
                "or personal bias. A structured record gives each audition additional observable evidence to "
                "review and helps make the process more consistent and explainable. It supports an actor's "
                "opportunity to be properly considered; it cannot guarantee a bias-free decision.\n\n"
                "**Important:** The current version helps organize audition evidence and reduce manual review "
                "effort; it does not yet automatically select or rank the top 10 or top 5 actors. This is a planned "
                "future capability: as RASA AI develops, it can be extended to compare auditions against role-specific "
                "requirements and help directors create a data-supported shortlist from a large pool. Any such "
                "shortlist should remain explainable and subject to human review, with the director and casting team "
                "making the final decision."
            )

        # Experimental portrayal evidence summary: reports observed model labels only;
        # it does not assign a suitability score or infer the actor's internal state.
        portrayal_label_map = {
            "Sadness / grief": {"sad"},
            "Anxiety / fear": {"fear"},
            "Anger / confrontation": {"angry"},
            "Joy / excitement": {"happy"},
            "Restrained / stoic performance": {"neutral"},
            "Other / mixed emotional state": set(),
        }
        intended_portrayal = st.session_state.get("rasa_character_portrayal_intent", "Other / mixed emotional state")
        expected_labels = portrayal_label_map.get(intended_portrayal, set())
        predictions = video_report.get("facial_expression_predictions", [])
        if video_report.get("facial_expression_model_enabled"):
            st.subheader("Experimental portrayal evidence")
            st.write(f"**Director's intended portrayal:** {intended_portrayal}")
            if expected_labels and predictions:
                confidence_threshold = st.slider(
                    "Minimum model score to count a prediction as review evidence",
                    min_value=0.0, max_value=1.0, value=0.60, step=0.05,
                    help="This is a review filter, not a calibrated probability that the actor feels an emotion or performs it convincingly.",
                    key="rasa_fer_confidence_threshold",
                )
                evidence_rows = []
                matched_confident = 0
                confident_count = 0
                label_counts = {}
                for prediction in predictions:
                    label = str(prediction.get("label", "")).casefold()
                    scores = prediction.get("scores") or {}
                    top_score = max(scores.values(), default=None)
                    is_confident = top_score is not None and float(top_score) >= confidence_threshold
                    if is_confident:
                        confident_count += 1
                        if label in expected_labels:
                            matched_confident += 1
                    if label:
                        label_counts[label] = label_counts.get(label, 0) + 1
                    evidence_rows.append({
                        "Timestamp (s)": prediction.get("timestamp_seconds"),
                        "Predicted label": prediction.get("label"),
                        "Top-label score": round(float(top_score), 3) if top_score is not None else None,
                        "Meets review threshold": "Yes" if is_confident else "Low confidence / unavailable",
                        "Matches selected category": "Yes" if label in expected_labels else "No",
                    })
                coverage = matched_confident / confident_count if confident_count else None
                m1, m2, m3 = st.columns(3)
                m1.metric(
                    "Matching labels among threshold-passing samples",
                    f"{coverage * 100:.1f}%" if coverage is not None else "N/A",
                )
                m2.metric("Threshold-passing samples", f"{confident_count}/{len(predictions)}")
                m3.metric("Samples needing closer review", len(predictions) - confident_count)
                st.caption(
                    "Descriptive model output only. The percentage is calculated only among samples whose top score meets your chosen threshold. "
                    "Scores are not necessarily calibrated probabilities; this is not a role-fit score or a measure of acting quality. "
                    "A different expression at a particular story beat may be entirely appropriate."
                )
                st.write("**Predicted-label distribution**")
                if label_counts:
                    st.dataframe(
                        [{"Predicted label": label, "Sample count": count}
                         for label, count in sorted(label_counts.items(), key=lambda item: (-item[1], item[0]))],
                        use_container_width=True,
                    )
                st.write("**Timestamped evidence**")
                st.dataframe(evidence_rows, use_container_width=True)
                st.write("**Human review:** inspect the listed timestamps alongside the dialogue, scene beat, and director's brief before making a casting decision.")
            elif not expected_labels:
                st.info("For mixed portrayals, review the timestamped predictions against the director's scene-specific notes; this version does not calculate a single target category.")
            else:
                st.warning("No facial-expression predictions were recorded. Check face visibility, lighting, and whether the optional FER model ran successfully.")
        else:
            st.info("Enable the optional facial-expression model during video analysis to show experimental timestamped expression labels for human review.")
        st.json({k: v for k, v in video_report.items() if k != "sample_observations"})
        st.markdown("**Sample observations**")
        sample_observations = video_report["sample_observations"]
        st.dataframe(sample_observations, use_container_width=True)

        with st.expander("What each video sample tells the director", expanded=False):
            st.caption(
                "Each row represents one sampled moment in the clip. These notes translate visible measurements "
                "into plain language so you can decide which moments to replay. They describe what the camera "
                "could measure—not the actor's feelings, intention, talent, or role suitability."
            )
            st.markdown(
                "**How to read the columns**\n"
                "- **Timestamp:** Approximate moment in the clip to replay.\n"
                "- **Pose detected:** Whether the body-pose model could identify the actor's body landmarks in that frame.\n"
                "- **Movement since previous sample:** How much the tracked body landmarks changed since the previous sampled moment. A larger value means more visible landmark movement, not better or worse acting.\n"
                "- **Wrist above shoulder:** Whether at least one detected wrist was higher than shoulder level in that frame.\n"
                "- **Shoulder tilt / torso offset:** Measurements of visible shoulder alignment and the torso's position in the frame. They do not measure confidence, mood, or posture quality.\n"
                "- **Face detected:** Whether the face could be located in that frame.\n"
                "- **Mouth opening / eye openness / brow-eye spacing:** Measurements of visible facial geometry. They are not emotion labels."
            )

            st.markdown("**Plain-language notes for the sampled moments**")
            for sample in sample_observations:
                timestamp = sample.get("timestamp_seconds", "unknown")
                try:
                    timestamp_label = f"{float(timestamp):.1f} sec"
                except (TypeError, ValueError):
                    timestamp_label = str(timestamp)

                observations = []
                pose_value = sample.get("pose_detected")
                face_value = sample.get("face_detected")
                if pose_value is not None:
                    observations.append(
                        "body pose was detected" if bool(pose_value) else "body pose was not reliably detected"
                    )
                if face_value is not None:
                    observations.append(
                        "face was detected" if bool(face_value) else "face was not reliably detected"
                    )

                movement = sample.get("movement_since_previous_sample_index")
                try:
                    if movement is not None:
                        movement = float(movement)
                        if movement != movement:  # Ignore NaN values without requiring pandas here.
                            movement = None
                        if movement is None:
                            raise ValueError("Movement sample is not a number")
                        if movement < 0.005:
                            observations.append("tracked body landmarks changed very little since the previous sample")
                        elif movement < 0.015:
                            observations.append("tracked body landmarks showed some change since the previous sample")
                        else:
                            observations.append("tracked body landmarks changed more noticeably since the previous sample")
                except (TypeError, ValueError):
                    pass

                wrist_value = sample.get("wrist_above_shoulder")
                if wrist_value is not None:
                    observations.append(
                        "at least one wrist was above shoulder level" if bool(wrist_value)
                        else "no wrist was detected above shoulder level"
                    )

                if observations:
                    st.markdown(f"- **{timestamp_label}:** " + "; ".join(observations) + ".")

            st.caption(
                "These are frame-by-frame observations, not conclusions about the performance. A hand raised "
                "may be part of a gesture, movement may be required by the scene, and a face or body not detected "
                "may simply be outside the frame or obscured. Replay the original clip and interpret each moment "
                "using the dialogue, blocking and director's brief."
            )

        st.download_button("Download movement report (JSON)", json.dumps(video_report, indent=2, ensure_ascii=False), "rasaai_actor_movement_report.json", "application/json")

        st.subheader("Multi-audition comparison")
        st.caption(f"Saved locally in {AUDITION_LIBRARY_PATH.name}. Add each analyzed audition to keep it available after restarting RasaAI. Compare similar clips; these are descriptive measurements, not a talent ranking.")

        # Browse, filter, and selectively remove saved auditions.
        library_items = list(st.session_state.get("rasa_audition_comparisons", []))
        if library_items:
            st.divider()
            library_characters = sorted({
                str(item.get("selected_character") or "Unassigned")
                for item in library_items
            })
            filter_col1, filter_col2 = st.columns(2)
            with filter_col1:
                library_filter = st.selectbox(
                    "Filter by character",
                    ["All characters"] + library_characters,
                    key="rasa_library_character_filter",
                )
                search_text = st.text_input(
                    "Search actor, video, character, or reviewer notes",
                    key="rasa_library_search",
                    placeholder="Type to search...",
                )
            with filter_col2:
                status_filter = st.selectbox(
                    "Filter by review status",
                    ["All statuses", "Not reviewed", "Consider", "Callback", "Hold", "Not selected"],
                    key="rasa_library_status_filter",
                )
                shortlist_only = st.checkbox(
                    "Show shortlisted auditions only",
                    key="rasa_library_shortlist_only",
                )

            normalized_search = search_text.strip().casefold()
            filtered_items = []
            for idx, item in enumerate(library_items):
                character = str(item.get("selected_character") or "Unassigned")
                actor = str(item.get("actor_label") or "")
                video = str(item.get("video_file") or "")
                notes = str(item.get("reviewer_notes") or "")
                status = str(item.get("reviewer_decision") or "Not reviewed")
                matches_character = library_filter == "All characters" or character == library_filter
                matches_status = status_filter == "All statuses" or status == status_filter
                matches_shortlist = not shortlist_only or bool(item.get("shortlisted", False))
                searchable_text = " ".join([actor, video, character, notes]).casefold()
                matches_search = not normalized_search or normalized_search in searchable_text
                if matches_character and matches_status and matches_shortlist and matches_search:
                    filtered_items.append((idx, item))

            st.caption(f"{len(filtered_items)} saved audition(s) shown · {len(library_items)} total")
            for original_index, item in filtered_items:
                label = item.get("actor_label") or item.get("video_file") or f"Audition {original_index + 1}"
                character = item.get("selected_character") or "Unassigned"
                with st.expander(f"{label} — {character}", expanded=False):
                    st.write(f"**Video:** {item.get('video_file', 'Unknown')}")
                    st.write(f"**Duration:** {item.get('duration_seconds_estimate', 'N/A')} seconds")
                    pose_rate = item.get("pose_detection_rate")
                    st.write(f"**Pose detection:** {round(pose_rate * 100, 1)}%" if isinstance(pose_rate, (int, float)) else "**Pose detection:** N/A")
                    st.json({
                        "mean_normalized_landmark_movement_index": item.get("mean_normalized_landmark_movement_index"),
                        "mean_shoulder_tilt_index": item.get("mean_shoulder_tilt_index"),
                        "fraction_samples_with_wrist_above_shoulder": item.get("fraction_samples_with_wrist_above_shoulder"),
                        "evidence_quality_notes": item.get("evidence_quality_notes", []),
                    })
                    report_name = re.sub(r"[^A-Za-z0-9_-]+", "_", str(label)).strip("_") or "audition"
                    st.download_button(
                        "Download audition review report (HTML)",
                        data=build_audition_html_report(item).encode("utf-8"),
                        file_name=f"rasaai_audition_review_{report_name}.html",
                        mime="text/html",
                        key=f"rasa_audition_html_report_{original_index}",
                        help="Open the downloaded report in a browser and use Print → Save as PDF if a PDF copy is needed.",
                    )

                    st.markdown("**Human reviewer feedback**")
                    decision_options = ["Not reviewed", "Consider", "Callback", "Hold", "Not selected"]
                    current_decision = item.get("reviewer_decision", "Not reviewed")
                    if current_decision not in decision_options:
                        current_decision = "Not reviewed"
                    reviewer_decision = st.selectbox(
                        "Review status",
                        decision_options,
                        index=decision_options.index(current_decision),
                        key=f"rasa_review_decision_{original_index}",
                        help="This is a human-entered workflow status, not an automated recommendation.",
                    )
                    shortlisted = st.checkbox(
                        "Add to casting shortlist",
                        value=bool(item.get("shortlisted", False)),
                        key=f"rasa_shortlist_{original_index}",
                        help="A human-managed shortlist marker; it is not an automated recommendation.",
                    )
                    reviewer_notes = st.text_area(
                        "Reviewer notes",
                        value=item.get("reviewer_notes", ""),
                        key=f"rasa_review_notes_{original_index}",
                        placeholder="Record observable strengths, questions, callbacks, or follow-up items.",
                        help="Notes are stored in the local JSON library. Avoid entering unnecessary sensitive personal information.",
                    )
                    if st.button("Save reviewer feedback", key=f"rasa_save_review_{original_index}"):
                        updated_items = [dict(saved_item) for saved_item in library_items]
                        updated_items[original_index]["reviewer_decision"] = reviewer_decision
                        updated_items[original_index]["shortlisted"] = bool(shortlisted)
                        updated_items[original_index]["reviewer_notes"] = reviewer_notes.strip()
                        if save_audition_library(updated_items):
                            record_audition_activity(
                                "Reviewer feedback saved",
                                updated_items[original_index],
                                "Review status, shortlist marker, and reviewer notes saved.",
                            )
                            st.session_state["rasa_audition_comparisons"] = updated_items
                            st.success("Reviewer feedback saved locally.")
                            st.rerun()

                    if st.button("Remove this audition", key=f"rasa_remove_saved_{original_index}"):
                        updated_items = [
                            saved_item for idx, saved_item in enumerate(library_items)
                            if idx != original_index
                        ]
                        if save_audition_library(updated_items):
                            record_audition_activity(
                                "Audition removed",
                                item,
                                "Removed from the saved audition library.",
                            )
                            st.session_state["rasa_audition_comparisons"] = updated_items
                            st.rerun()

        if st.button("Add this audition to comparison", key="rasa_add_audition"):
            saved = list(st.session_state.get("rasa_audition_comparisons", []))
            actor_label_value = video_report.get("actor_label") or video_report.get("video_file", "Audition")
            duplicate = any(
                item.get("actor_label") == actor_label_value
                and item.get("video_file") == video_report.get("video_file")
                and item.get("selected_character") == video_report.get("selected_character")
                for item in saved
            )
            if duplicate:
                st.info("This actor/video is already in the comparison list.")
            else:
                saved.append(video_report)
                if save_audition_library(saved):
                    record_audition_activity(
                        "Audition added",
                        saved[-1],
                        "New audition added to the local comparison library.",
                    )
                    st.session_state["rasa_audition_comparisons"] = saved
                    st.success("Audition added to the local library and saved for future sessions.")

        comparison_items = [
            item for item in st.session_state.get("rasa_audition_comparisons", [])
            if item.get("selected_character") == video_report.get("selected_character")
        ]
        if comparison_items:
            comparison_rows = []
            for item in comparison_items:
                comparison_rows.append({
                    "Actor / label": item.get("actor_label") or item.get("video_file"),
                    "Character": item.get("selected_character"),
                    "Video": item.get("video_file"),
                    "Duration (s)": item.get("duration_seconds_estimate"),
                    "Pose detection (%)": round(item["pose_detection_rate"] * 100, 1) if isinstance(item.get("pose_detection_rate"), (int, float)) else None,
                    "Mean movement index": item.get("mean_normalized_landmark_movement_index"),
                    "Mean shoulder tilt": item.get("mean_shoulder_tilt_index"),
                    "Wrist-above-shoulder fraction": item.get("fraction_samples_with_wrist_above_shoulder"),
                    "Reviewer decision": item.get("reviewer_decision", "Not reviewed"),
                    "Shortlisted": bool(item.get("shortlisted", False)),
                    "Reviewer notes": item.get("reviewer_notes", ""),
                    "Evidence quality": (
                        "Low pose coverage"
                        if isinstance(item.get("pose_detection_rate"), (int, float)) and item.get("pose_detection_rate") < 0.5
                        else "Short clip"
                        if isinstance(item.get("duration_seconds_estimate"), (int, float)) and item.get("duration_seconds_estimate") < 10
                        else "Review framing"
                        if isinstance(item.get("pose_detection_rate"), (int, float)) and item.get("pose_detection_rate") < 0.8
                        else "Review manually"
                    ),
                })
            st.dataframe(comparison_rows, use_container_width=True, hide_index=True)
            st.caption("Evidence-quality flags are simple review prompts, not validated confidence scores. Low pose coverage may reflect occlusion, framing, lighting, or pose-detector limitations; short clips provide less evidence.")
            st.download_button(
                "Download multi-audition comparison (JSON)",
                json.dumps(comparison_rows, indent=2, ensure_ascii=False),
                "rasaai_multi_audition_comparison.json",
                "application/json",
                key="rasa_comparison_download"
            )
            if st.button("Clear comparison list", key="rasa_clear_comparisons"):
                if save_audition_library([]):
                    st.session_state["rasa_audition_comparisons"] = []
                    st.rerun()
        else:
            st.info("No auditions have been added for this character yet. Analyze a clip and click **Add this audition to comparison**.")

        st.subheader("Role requirement evidence comparison")
        st.caption("Exploratory rule-based indicators only; thresholds are not trained or validated and should not be interpreted as an actor score.")
        targets = st.session_state.get("rasa_role_requirements", {}).get(video_report.get("selected_character", ""), [])
        if not targets:
            st.info("No measurable targets were selected for this character. Select requirements above to compare them with the video measurements.")
        else:
            evidence_rows = build_requirement_evidence(targets, video_report)
            st.dataframe(evidence_rows, use_container_width=True, hide_index=True)
            timestamp_rows = build_timestamped_evidence(targets, video_report)
            st.markdown("**Timestamped observable evidence**")
            st.caption("Movement timestamps use changes in visible landmark positions, centered on the shoulder midpoint and scaled by shoulder width, between adjacent sampled frames (about one second apart). This partially reduces camera-distance effects; it is still an experimental proxy, not a validated performance measure.")
            st.dataframe(timestamp_rows, use_container_width=True, hide_index=True)
            st.warning("These comparisons are sensitive to camera framing, pose visibility, action context and clip differences. Review the timestamped observations yourself; do not use this as an automated casting decision.")
            combined_report = {
                "project": "RasaAI",
                "analysis_method": "Local rule-based NLP and observable computer-vision measurements; no LLM or cloud API",
                "character": video_report.get("selected_character"),
                "role_requirements_selected_by_filmmaker": targets,
                "intended_character_portrayal": st.session_state.get("rasa_character_portrayal_intent", "Not specified"),
                "portrayal_analysis_note": "The selected portrayal is a filmmaker-provided brief, not a detected emotion label. Facial measurements are geometric proxies and must be interpreted by a human reviewer in scene context.",
                "role_requirement_evidence": evidence_rows,
                "timestamped_observable_evidence": timestamp_rows,
                "screenplay_analysis": story_report,
                "actor_video_analysis": video_report,
                "matching_limitations": "Exploratory indicators only. No trained actor-ranking model is used. Measurements do not establish talent, emotion, personality, or casting suitability. Human review is required."
            }
            st.download_button("Download combined role review (JSON)", json.dumps(combined_report, indent=2, ensure_ascii=False), "rasaai_combined_role_review.json", "application/json")


    # ---------- Vocal performance analysis (audio-only, experimental) ----------
with workflow_tabs[4]:
    _rasa_section_heading("05", "AUDIO REVIEW", "Vocal performance analysis")
    st.write(
        "Upload an audition audio track to inspect pitch, loudness, pauses and vocal variation. "
        "This measures acoustic patterns; it does not determine whether an actor is truly sad, happy, angry, "
        "or suitable for a role. For best comparisons, use clean dialogue with minimal music and similar recording conditions."
    )
    st.caption("Audio processing is local. Supported formats depend on the installed librosa/audio backend; WAV is the safest option.")
    audio_actor_label = st.text_input(
        "Actor / audition label for vocal analysis",
        placeholder="e.g., Audition A or actor name",
        key="rasa_vocal_actor_label",
    )
    audio_character_options = [c["name"] for c in story_report.get("story_characters", [])] if story_report else []
    if audio_character_options:
        audio_character = st.selectbox(
            "Character for this vocal audition", ["Unassigned"] + audio_character_options,
            key="rasa_vocal_character",
        )
    else:
        audio_character = st.text_input(
            "Character for this vocal audition (optional)",
            placeholder="e.g., Arjun", key="rasa_vocal_character_text",
        ) or "Unassigned"
    extracted_video_audio = st.session_state.get("rasa_video_audio_bytes")
    audio_source_options = ["Upload a separate audio file"]
    if extracted_video_audio:
        audio_source_options.insert(0, "Use audio from the audition video")
    selected_audio_source = st.radio(
        "Audio source for vocal analysis",
        audio_source_options,
        horizontal=True,
        key="rasa_vocal_audio_source",
    )
    audio_file = None
    if selected_audio_source == "Upload a separate audio file":
        audio_file = st.file_uploader(
            "Upload audition audio", type=["wav", "mp3", "m4a", "flac", "ogg"], key="rasa_vocal_audio"
        )
        selected_audio_bytes = audio_file.getvalue() if audio_file else None
        selected_audio_name = audio_file.name if audio_file else None
    else:
        selected_audio_bytes = extracted_video_audio
        selected_audio_name = st.session_state.get("rasa_video_audio_name", "audition_video_audio.wav")

    if selected_audio_bytes:
        audio_bytes = selected_audio_bytes
        audio_suffix = Path(selected_audio_name or "audition.wav").suffix.lower() or ".wav"
        playable_audio_bytes = audio_bytes
        audio_format = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".flac": "audio/flac", ".ogg": "audio/ogg"}.get(audio_suffix, "application/octet-stream")
        ffmpeg = shutil.which("ffmpeg")
        source_audio_path = None
        converted_audio_path = None
        if ffmpeg:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=audio_suffix) as source_tmp:
                    source_tmp.write(audio_bytes)
                    source_audio_path = source_tmp.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as converted_tmp:
                    converted_audio_path = converted_tmp.name
                result = subprocess.run(
                    [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", source_audio_path,
                     "-vn", "-ac", "1", "-ar", "22050", "-c:a", "pcm_s16le", converted_audio_path],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0 and os.path.exists(converted_audio_path) and os.path.getsize(converted_audio_path) > 44:
                    playable_audio_bytes = Path(converted_audio_path).read_bytes()
                    audio_format = "audio/wav"
                else:
                    detail = (result.stderr or "Unknown FFmpeg conversion error").strip()[-800:]
                    st.warning(f"Audio conversion was unavailable; trying the original audio file. Details: {detail}")
            except Exception as convert_exc:
                st.error(f"Audio conversion failed: {type(convert_exc).__name__}: {convert_exc}")
            finally:
                for temp_name in (source_audio_path, converted_audio_path):
                    if temp_name:
                        try:
                            os.unlink(temp_name)
                        except OSError:
                            pass
        else:
            st.info("FFmpeg is unavailable. The original audio will be played directly; WAV is the most compatible format.")
        if st.button("Analyze vocal acoustics", type="primary", key="rasa_analyze_vocal"):
            try:
                import librosa
                import numpy as np
                import pandas as pd
                audio, sr = librosa.load(io.BytesIO(playable_audio_bytes), sr=22050, mono=True)
                if audio.size == 0:
                    st.error("The uploaded audio contains no readable samples.")
                else:
                    duration_s = float(len(audio) / sr)
                    frame_length = 2048
                    hop_length = 512
                    rms = librosa.feature.rms(y=audio, frame_length=frame_length, hop_length=hop_length)[0]
                    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
                    # pyin is relatively expensive, so cap the analysis duration to keep local use practical.
                    max_duration = 180.0
                    analyzed_audio = audio[: int(max_duration * sr)]
                    f0, voiced_flag, voiced_prob = librosa.pyin(
                        analyzed_audio, fmin=librosa.note_to_hz("C2"), fmax=librosa.note_to_hz("C7"),
                        sr=sr, frame_length=2048, hop_length=512
                    )
                    pitch_times = librosa.times_like(f0, sr=sr, hop_length=512)
                    valid_pitch = f0[np.isfinite(f0)]
                    voiced_fraction = float(np.isfinite(f0).mean()) if len(f0) else 0.0
                    # Relative energy threshold provides a rough pause proxy, not speech recognition.
                    energy_floor = max(float(np.max(rms)) * 0.12, 1e-5)
                    active = rms > energy_floor
                    frame_seconds = hop_length / sr
                    pause_seconds = float((~active).sum() * frame_seconds)
                    changes = np.diff(np.r_[False, active, False].astype(int))
                    starts = np.where(changes == 1)[0]
                    ends = np.where(changes == -1)[0]
                    pauses = []
                    for a, b in zip(ends[:-1], starts[1:]):
                        gap = (starts[np.where(starts > a)[0][0]] - a) * frame_seconds if np.any(starts > a) else 0
                        if gap >= 0.35:
                            pauses.append({"start_seconds": round(float(a * frame_seconds), 2), "duration_seconds": round(float(gap), 2)})
                    features = {
                        "audio_file": selected_audio_name or "audition_video_audio.wav",
                        "duration_seconds": round(duration_s, 2),
                        "analyzed_duration_seconds": round(min(duration_s, max_duration), 2),
                        "median_pitch_hz": round(float(np.median(valid_pitch)), 1) if len(valid_pitch) else None,
                        "pitch_10th_percentile_hz": round(float(np.percentile(valid_pitch, 10)), 1) if len(valid_pitch) else None,
                        "pitch_90th_percentile_hz": round(float(np.percentile(valid_pitch, 90)), 1) if len(valid_pitch) else None,
                        "pitch_standard_deviation_hz": round(float(np.std(valid_pitch)), 1) if len(valid_pitch) else None,
                        "voiced_frame_fraction": round(voiced_fraction, 3),
                        "mean_rms_energy": round(float(np.mean(rms)), 5),
                        "energy_variation_std": round(float(np.std(rms)), 5),
                        "estimated_low_energy_seconds": round(pause_seconds, 2),
                        "detected_energy_gaps_over_0_35s": len(pauses),
                        "energy_gap_examples": pauses[:100],
                        "note": "Acoustic descriptors only; low energy is not necessarily silence, and pitch/energy do not establish emotion or acting quality."
                    }
                    st.session_state["rasa_vocal_analysis"] = {
                        "features": features,
                        "pitch_times": pitch_times.tolist(),
                        "pitch_hz": [float(x) if np.isfinite(x) else None for x in f0],
                        "rms_times": rms_times.tolist(),
                        "rms": rms.tolist(),
                        "actor_label": audio_actor_label.strip() or Path(selected_audio_name or "audition_audio.wav").stem,
                        "selected_character": audio_character or "Unassigned",
                    }
            except ImportError:
                st.error("Vocal analysis needs librosa. In the active Python 3.12 environment, run: python -m pip install librosa")
            except Exception as exc:
                st.error(f"Audio analysis failed: {type(exc).__name__}: {exc}")

    vocal_result = st.session_state.get("rasa_vocal_analysis")
    if vocal_result:
        # Streamlit reruns the script after a button click. Re-import these here so
        # the results-rendering pass does not depend on imports from the click branch.
        try:
            import numpy as np
            import pandas as pd
        except ImportError as exc:
            st.error(f"Cannot display saved vocal results because a required package is missing: {exc}")
            st.stop()
        vf = vocal_result["features"]
        st.subheader("Vocal acoustics summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Median pitch", f"{vf['median_pitch_hz']} Hz" if vf["median_pitch_hz"] is not None else "Unavailable")
        c2.metric("Pitch range (P10–P90)", f"{vf['pitch_10th_percentile_hz']}–{vf['pitch_90th_percentile_hz']} Hz" if vf["pitch_10th_percentile_hz"] is not None else "Unavailable")
        c3.metric("Pitch variability", f"{vf['pitch_standard_deviation_hz']} Hz" if vf["pitch_standard_deviation_hz"] is not None else "Unavailable")
        c4.metric("Energy gaps ≥ 0.35 s", str(vf["detected_energy_gaps_over_0_35s"]))
        pitch_df = pd.DataFrame({"Time (s)": vocal_result["pitch_times"], "Pitch (Hz)": vocal_result["pitch_hz"]}).set_index("Time (s)")
        st.markdown("**Pitch contour**")
        st.caption(
            "Director's guide: Read this from left to right as the clip plays. The horizontal line is time; "
            "the vertical value is the detected pitch of the voice. A rising line means the voice became higher; "
            "a falling line means it became lower. Changes can help you locate shifts in vocal delivery, but "
            "they do not tell you which emotion the actor was expressing. Gaps mean pitch could not be detected. "
            "Sudden isolated spikes can be tracking errors, background sounds or pitch-detection mistakes—"
            "replay those moments before drawing conclusions."
        )
        st.line_chart(pitch_df, height=220)
        rms_df = pd.DataFrame({"Time (s)": vocal_result["rms_times"], "RMS energy": vocal_result["rms"]}).set_index("Time (s)")
        st.markdown("**Relative loudness / energy**")
        st.caption(
            "Director's guide: This line shows how strong the recorded sound is over time. Higher sections are "
            "louder in the recording; lower sections are quieter. Use it to find changes in vocal intensity or "
            "possible pauses. It is not a calibrated loudness score: music, background noise, microphone distance "
            "and recording volume can also raise or lower the line."
        )
        st.line_chart(rms_df, height=180)

        with st.container(border=True):
            st.subheader("What this vocal analysis means — director's view")
            st.caption(
                "A plain-language guide to the voice measurements in this clip. "
                "Use these observations to decide what to listen to again, not to score or rank the actor."
            )

            median_pitch = vf.get("median_pitch_hz")
            low_pitch = vf.get("pitch_10th_percentile_hz")
            high_pitch = vf.get("pitch_90th_percentile_hz")
            pitch_variability = vf.get("pitch_standard_deviation_hz")
            mean_energy = vf.get("mean_rms_energy")
            energy_variability = vf.get("energy_variation_std")
            voiced_fraction = vf.get("voiced_frame_fraction")
            low_energy_seconds = vf.get("estimated_low_energy_seconds")
            gap_count = vf.get("detected_energy_gaps_over_0_35s")
            clip_duration = vf.get("duration_seconds")

            if median_pitch is not None:
                st.markdown(
                    f"- **Voice pitch:** The typical detected pitch in this clip was about "
                    f"**{median_pitch} Hz**. The measured middle range was **{low_pitch}–{high_pitch} Hz**. "
                    "This describes how high or low the voice sounded acoustically; it is not a judgement "
                    "about whether the voice is attractive, suitable, masculine, feminine, or emotionally correct."
                )
            else:
                st.markdown(
                    "- **Voice pitch:** The system could not reliably detect pitch in this recording. "
                    "This can happen with noise, music, overlapping voices, or very quiet audio."
                )

            if pitch_variability is not None:
                st.markdown(
                    f"- **Pitch variation:** The measured variation was **{pitch_variability} Hz**. "
                    "This shows how much the detected pitch moved around during the clip. "
                    "A steadier pitch may sound more even; greater variation may make delivery sound more varied. "
                    "Neither is automatically better—the scene and character direction matter."
                )

            if energy_variability is not None:
                st.markdown(
                    f"- **Loudness changes:** The recording's energy variation was **{energy_variability}**. "
                    "The chart shows where the voice or overall audio became louder or softer. "
                    "This can help locate changes in vocal intensity, but background music, microphone distance "
                    "and recording volume also affect it."
                )

            if voiced_fraction is not None:
                st.markdown(
                    f"- **Detectable voiced sound:** About **{voiced_fraction * 100:.0f}%** of the analysed "
                    "frames contained a pitch the system could detect. This is not the percentage of words "
                    "spoken or a speech-clarity score."
                )

            if low_energy_seconds is not None and gap_count is not None:
                st.markdown(
                    f"- **Quieter moments:** The system found about **{low_energy_seconds} seconds** of "
                    f"low-energy audio and **{gap_count} energy gaps longer than 0.35 seconds**. "
                    "These may point to pauses or quieter moments worth replaying, but they are not confirmed "
                    "speech pauses—silence, soft speech, music and room noise can affect the estimate."
                )

            st.markdown("### Does the voice match the intended emotion?")
            intended_vocal_portrayal = st.session_state.get(
                "rasa_character_portrayal_intent", "Not specified"
            )
            st.info(
                f"The selected intended portrayal is **{intended_vocal_portrayal}**. "
                "This version measures pitch, loudness and low-energy gaps; it does not recognise emotion "
                "from speech or understand the dialogue. Therefore it cannot reliably say whether the actor's "
                "voice matched the intended emotion. The vocal result is **not an emotion-match verdict**. "
                "Listen to the relevant lines in context and compare them with the character brief."
            )

            with st.expander("What this vocal analysis cannot tell you"):
                st.markdown(
                    "- It cannot identify the actor's real feelings or prove that an emotion was convincingly portrayed.\n"
                    "- It does not transcribe dialogue, measure pronunciation, understand language or determine what the words mean.\n"
                    "- It does not currently provide a validated speaking-speed, vocal-clarity, accent, or acting-quality score.\n"
                    "- Pitch and loudness are affected by the actor's natural voice, language, dialogue, microphone, music, room and recording conditions.\n"
                    "- A pause or a quiet moment is not automatically a mistake; it may be an intentional part of the performance."
                )

            st.markdown("### Why this is useful in a real casting process")
            st.markdown(
                "**For directors:** When reviewing many auditions, the pitch and energy timelines and the detected "
                "quieter moments help you return to specific parts of a recording instead of relying only on memory. "
                "They add structured listening notes alongside your own judgement.\n\n"
                "**For actors:** A saved, structured record can make vocal review more consistent and give the actor "
                "specific moments to discuss or revisit, rather than relying entirely on a general impression. "
                "It can support fairer consideration, but it cannot guarantee that human bias is removed.\n\n"
                "**For large audition rounds:** With dozens or hundreds of submissions, RASA AI can help organise "
                "and compare review evidence so the casting team can manage a human-led shortlist. The current vocal "
                "analysis does not rank actors or select a top 10 or top 5."
            )

        st.dataframe(pd.DataFrame([vf]), use_container_width=True, hide_index=True)
        st.download_button("Download vocal analysis (JSON)", json.dumps(vf, indent=2, ensure_ascii=False), "rasaai_vocal_analysis.json", "application/json", key="rasa_vocal_json")
        if st.button("Save vocal analysis to audition library / Haystack", type="primary", key="rasa_save_vocal_analysis"):
            saved_items = [dict(item) for item in st.session_state.get("rasa_audition_comparisons", [])]
            actor_value = vocal_result.get("actor_label") or Path(vf.get("audio_file", "audition_audio")).stem
            character_value = vocal_result.get("selected_character") or "Unassigned"
            duplicate_index = next((i for i, item in enumerate(saved_items)
                if item.get("analysis_type") == "vocal"
                and item.get("audio_file") == vf.get("audio_file")
                and item.get("actor_label") == actor_value
                and item.get("selected_character") == character_value), None)
            vocal_record = {
                "analysis_type": "vocal",
                "actor_label": actor_value,
                "selected_character": character_value,
                "audio_file": vf.get("audio_file"),
                "video_file": "",
                "vocal_analysis": vf,
                "median_pitch_hz": vf.get("median_pitch_hz"),
                "pitch_10th_percentile_hz": vf.get("pitch_10th_percentile_hz"),
                "pitch_90th_percentile_hz": vf.get("pitch_90th_percentile_hz"),
                "pitch_standard_deviation_hz": vf.get("pitch_standard_deviation_hz"),
                "voiced_frame_fraction": vf.get("voiced_frame_fraction"),
                "mean_rms_energy": vf.get("mean_rms_energy"),
                "energy_variation_std": vf.get("energy_variation_std"),
                "estimated_low_energy_seconds": vf.get("estimated_low_energy_seconds"),
                "detected_energy_gaps_over_0_35s": vf.get("detected_energy_gaps_over_0_35s"),
                "reviewer_decision": "Not reviewed",
                "shortlisted": False,
                "reviewer_notes": "",
                "analysis_method": "Local librosa acoustic analysis; no speech transcription or emotion inference",
                "saved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            }
            if duplicate_index is not None:
                saved_items[duplicate_index] = {**saved_items[duplicate_index], **vocal_record}
            else:
                saved_items.append(vocal_record)
            if save_audition_library(saved_items):
                st.session_state["rasa_audition_comparisons"] = saved_items
                record_audition_activity("Vocal analysis saved", vocal_record, "Saved vocal acoustics for Haystack keyword retrieval.")
                st.success("Vocal analysis saved to the local library. It is now available in Haystack Retrieval.")

        # Export a compact, timestamped evidence table so reviewers can inspect
        # acoustic measurements alongside the actual recording. This is not speech
        # transcription or emotion recognition.
        st.subheader("Timestamped vocal evidence")
        st.caption(
            "Director's guide: Each row is a moment in the recording. The timestamp tells you where to replay; "
            "pitch_hz is the estimated voice pitch at that moment; rms_energy is the relative strength of the "
            "recorded sound. 'None' in the pitch column means the system could not find a reliable pitched voice "
            "at that instant—it does not automatically mean the actor was silent. Use the rows to locate moments "
            "for listening, not as a line-by-line performance score."
        )
        try:
            evidence_df = pd.DataFrame({
                "time_seconds": vocal_result["pitch_times"],
                "pitch_hz": vocal_result["pitch_hz"],
            })
            rms_df_export = pd.DataFrame({
                "time_seconds": vocal_result["rms_times"],
                "rms_energy": vocal_result["rms"],
            })
            evidence_df = evidence_df.dropna(subset=["time_seconds"])
            evidence_df["time_seconds"] = pd.to_numeric(evidence_df["time_seconds"], errors="coerce")
            rms_df_export["time_seconds"] = pd.to_numeric(rms_df_export["time_seconds"], errors="coerce")
            evidence_df = evidence_df.dropna(subset=["time_seconds"])
            rms_df_export = rms_df_export.dropna(subset=["time_seconds"])
            if not evidence_df.empty and not rms_df_export.empty:
                evidence_df["rms_energy"] = np.interp(
                    evidence_df["time_seconds"].to_numpy(),
                    rms_df_export["time_seconds"].to_numpy(),
                    rms_df_export["rms_energy"].to_numpy(),
                )
                evidence_df["time_seconds"] = evidence_df["time_seconds"].round(2)
                evidence_df["pitch_hz"] = pd.to_numeric(evidence_df["pitch_hz"], errors="coerce").round(1)
                evidence_df["rms_energy"] = evidence_df["rms_energy"].round(6)
                st.dataframe(evidence_df, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download timestamped vocal evidence (CSV)",
                    evidence_df.to_csv(index=False).encode("utf-8"),
                    "rasaai_vocal_evidence.csv",
                    "text/csv",
                    key="rasa_vocal_evidence_csv",
                )
            else:
                st.info("No timestamped samples were available to export.")
        except Exception as exc:
            st.warning(f"Could not prepare the timestamped evidence table: {type(exc).__name__}: {exc}")

        st.subheader("Dialogue delivery by time segment")
        st.caption(
            "Director's guide: This divides the recording into short time windows (for example, 0–5 seconds, "
            "5–10 seconds) so you can compare how the voice changes across the audition. It describes sound "
            "patterns only; it does not identify emotions or judge acting quality."
        )
        with st.expander("How to read the columns"):
            st.markdown(
                "- **Start / end seconds:** The part of the recording covered by that row.\n"
                "- **Median pitch:** The typical detected pitch in that section. A higher number means a higher-sounding voice in that section.\n"
                "- **Pitch variability:** How much the detected pitch moved around within that section. Higher variation means more pitch movement, not necessarily better delivery.\n"
                "- **Mean energy:** The average strength of the recorded sound in that section. Higher values mean louder recorded audio, not necessarily stronger acting.\n"
                "- **Energy variability:** How much the recorded loudness changed within that section.\n"
                "- **Pitch / energy frames:** How many small audio samples contributed to each measurement. These are technical sample counts, not words or lines."
            )
        segment_seconds = st.select_slider(
            "Segment length (seconds)",
            options=[3, 5, 10, 15],
            value=5,
            key="rasa_vocal_segment_length",
        )
        pitch_frame = pd.DataFrame({
            "time_seconds": vocal_result["pitch_times"],
            "pitch_hz": vocal_result["pitch_hz"],
        })
        energy_frame = pd.DataFrame({
            "time_seconds": vocal_result["rms_times"],
            "rms_energy": vocal_result["rms"],
        })
        pitch_frame["time_seconds"] = pd.to_numeric(pitch_frame["time_seconds"], errors="coerce")
        pitch_frame["pitch_hz"] = pd.to_numeric(pitch_frame["pitch_hz"], errors="coerce")
        energy_frame["time_seconds"] = pd.to_numeric(energy_frame["time_seconds"], errors="coerce")
        energy_frame["rms_energy"] = pd.to_numeric(energy_frame["rms_energy"], errors="coerce")
        pitch_frame = pitch_frame.dropna(subset=["time_seconds"])
        energy_frame = energy_frame.dropna(subset=["time_seconds", "rms_energy"])
        if not pitch_frame.empty and not energy_frame.empty:
            max_time = min(
                float(pitch_frame["time_seconds"].max()),
                float(energy_frame["time_seconds"].max()),
            )
            boundaries = np.arange(0, max_time + segment_seconds, segment_seconds)
            segment_rows = []
            for start in boundaries[:-1]:
                end = min(float(start + segment_seconds), max_time + 1e-6)
                pseg = pitch_frame[
                    (pitch_frame["time_seconds"] >= start) &
                    (pitch_frame["time_seconds"] < end)
                ]["pitch_hz"].dropna()
                eseg = energy_frame[
                    (energy_frame["time_seconds"] >= start) &
                    (energy_frame["time_seconds"] < end)
                ]["rms_energy"].dropna()
                if pseg.empty and eseg.empty:
                    continue
                segment_rows.append({
                    "start_seconds": round(float(start), 2),
                    "end_seconds": round(float(end), 2),
                    "median_pitch_hz": round(float(pseg.median()), 1) if not pseg.empty else None,
                    "pitch_variability_std_hz": round(float(pseg.std(ddof=0)), 1) if not pseg.empty else None,
                    "mean_rms_energy": round(float(eseg.mean()), 6) if not eseg.empty else None,
                    "energy_variability_std": round(float(eseg.std(ddof=0)), 6) if not eseg.empty else None,
                    "pitch_frames": int(len(pseg)),
                    "energy_frames": int(len(eseg)),
                })
            if segment_rows:
                segment_df = pd.DataFrame(segment_rows)
                st.dataframe(segment_df, use_container_width=True, hide_index=True)

                with st.expander("What each time segment tells the director", expanded=False):
                    st.markdown("**What each time segment tells the director**")
                    clip_pitch_reference = float(pitch_frame["pitch_hz"].dropna().median()) if not pitch_frame["pitch_hz"].dropna().empty else None
                    clip_energy_reference = float(energy_frame["rms_energy"].median()) if not energy_frame.empty else None
                    for row in segment_rows:
                        start_label = int(row["start_seconds"]) if float(row["start_seconds"]).is_integer() else row["start_seconds"]
                        end_label = int(row["end_seconds"]) if float(row["end_seconds"]).is_integer() else row["end_seconds"]
                        observations = []
                        row_pitch = row.get("median_pitch_hz")
                        row_energy = row.get("mean_rms_energy")
                        row_pitch_var = row.get("pitch_variability_std_hz")
                        row_energy_var = row.get("energy_variability_std")

                        if row_pitch is None:
                            observations.append("no reliable pitch was detected")
                        elif clip_pitch_reference is not None:
                            pitch_ratio = row_pitch / max(clip_pitch_reference, 1e-6)
                            if pitch_ratio >= 1.12:
                                observations.append("the voice sat higher than this clip's typical pitch")
                            elif pitch_ratio <= 0.88:
                                observations.append("the voice sat lower than this clip's typical pitch")
                            else:
                                observations.append("the voice pitch was close to this clip's typical level")

                        if row_energy is not None and clip_energy_reference is not None:
                            energy_ratio = row_energy / max(clip_energy_reference, 1e-9)
                            if energy_ratio >= 1.20:
                                observations.append("the recording was louder than the clip's typical level")
                            elif energy_ratio <= 0.80:
                                observations.append("the recording was quieter than the clip's typical level")
                            else:
                                observations.append("the recording level was near the clip's typical level")

                        if row_pitch_var is not None:
                            observations.append(
                                "pitch moved around more in this section" if row_pitch_var > (vf.get("pitch_standard_deviation_hz") or 0)
                                else "pitch was relatively steadier in this section"
                            )
                        if row_energy_var is not None:
                            observations.append(
                                "recorded loudness changed noticeably within this section"
                                if row_energy_var > (vf.get("energy_variation_std") or 0)
                                else "recorded loudness was relatively even within this section"
                            )

                        if observations:
                            st.markdown(f"- **{start_label}–{end_label} sec:** " + "; ".join(observations) + ".")
                    st.caption(
                        "These comparisons are relative to this recording, not to other actors or a universal ideal. "
                        "A higher, lower, louder or steadier section is not automatically good or bad. Listen to the "
                        "actual dialogue and scene context before interpreting it."
                    )
                st.download_button(
                    "Download segment delivery summary (CSV)",
                    segment_df.to_csv(index=False).encode("utf-8"),
                    "rasaai_vocal_segment_summary.csv",
                    "text/csv",
                    key="rasa_vocal_segment_summary_csv",
                )
            else:
                st.info("No usable samples were available for segment summaries.")
        else:
            st.info("No timestamped pitch or energy samples are available for segment summaries.")

        st.warning("These acoustic features are not an emotion classifier. Pitch and loudness vary with the actor, language, dialogue, microphone, music and recording conditions. Review the audio in context; do not use these measurements alone to rank or reject actors.")


    st.divider()
    st.caption("Privacy: processing is designed to run locally. Use only actor media you have permission to analyze. This is an experimental casting-support tool; final decisions remain with the filmmaker and casting team.")


    # ---------- Combined vocal + visual evidence timeline (experimental) ----------
    st.divider()
with workflow_tabs[5]:
    _rasa_section_heading("06", "EVIDENCE REVIEW", "Combined vocal + visual evidence timeline")
    st.write(
        "Align timestamped video observations with nearby vocal measurements for reviewer inspection. "
        "This does not infer a person's true emotion or calculate a validated acting score."
    )
    video_report = st.session_state.get("rasa_video_report")
    vocal_result = st.session_state.get("rasa_vocal_analysis")
    if not video_report or not vocal_result:
        st.info("Run both video analysis and vocal analysis in this session to build a combined timeline.")
    else:
        import pandas as pd
        import numpy as np

        sync_offset = st.number_input(
            "Audio offset relative to video (seconds)",
            min_value=-3600.0,
            max_value=3600.0,
            value=0.0,
            step=0.1,
            help="Positive values mean the audio starts later than the video. Adjust only if you know the recordings are offset."
        )
        tolerance = st.slider(
            "Maximum time difference for matching samples (seconds)",
            min_value=0.25,
            max_value=5.0,
            value=1.0,
            step=0.25,
        )
        observations = video_report.get("sample_observations", [])
        if not observations:
            st.warning("The video report has no timestamped observations to align.")
        else:
            pitch_times = np.asarray(vocal_result.get("pitch_times", []), dtype=float)
            pitch_values = vocal_result.get("pitch_hz", [])
            rms_times = np.asarray(vocal_result.get("rms_times", []), dtype=float)
            rms_values = vocal_result.get("rms", [])
            vocal_rows = []
            for i, t in enumerate(pitch_times):
                value = pitch_values[i] if i < len(pitch_values) else None
                if value is not None and np.isfinite(value):
                    vocal_rows.append({"time": float(t) + float(sync_offset), "pitch_hz": float(value)})
            for i, t in enumerate(rms_times):
                value = rms_values[i] if i < len(rms_values) else None
                if value is not None and np.isfinite(value):
                    vocal_rows.append({"time": float(t) + float(sync_offset), "rms_energy": float(value)})
            pitch_df = pd.DataFrame(vocal_rows)
            if not pitch_df.empty:
                if "pitch_hz" not in pitch_df:
                    pitch_df["pitch_hz"] = np.nan
                if "rms_energy" not in pitch_df:
                    pitch_df["rms_energy"] = np.nan
                pitch_df = pitch_df.groupby("time", as_index=False).agg(
                    pitch_hz=("pitch_hz", "mean"), rms_energy=("rms_energy", "mean")
                )
            prediction_rows = video_report.get("facial_expression_predictions", [])
            aligned = []
            for obs in observations:
                video_time = float(obs.get("timestamp_seconds", 0.0))
                row = {
                    "video_time_seconds": round(video_time, 2),
                    "pose_detected": obs.get("pose_detected"),
                    "mouth_opening_ratio": obs.get("mouth_opening_ratio"),
                    "eye_openness_proxy": obs.get("eye_openness_proxy"),
                    "movement_index": obs.get("movement_since_previous_sample_index"),
                    "shoulder_tilt_index": obs.get("shoulder_tilt_index"),
                    "facial_expression_prediction": None,
                    "expression_model_score": None,
                    "matched_audio_time_seconds": None,
                    "pitch_hz_nearby": None,
                    "rms_energy_nearby": None,
                    "audio_match_difference_seconds": None,
                }
                if prediction_rows:
                    candidates = [
                        p for p in prediction_rows
                        if p.get("timestamp_seconds") is not None and p.get("label")
                    ]
                    if candidates:
                        nearest_prediction = min(
                            candidates, key=lambda p: abs(float(p["timestamp_seconds"]) - video_time)
                        )
                        if abs(float(nearest_prediction["timestamp_seconds"]) - video_time) <= tolerance:
                            row["facial_expression_prediction"] = nearest_prediction.get("label")
                            scores = nearest_prediction.get("scores", {})
                            if isinstance(scores, dict) and scores:
                                row["expression_model_score"] = round(max(float(v) for v in scores.values()), 4)
                if not pitch_df.empty:
                    nearest_idx = (pitch_df["time"] - video_time).abs().idxmin()
                    nearest = pitch_df.loc[nearest_idx]
                    difference = abs(float(nearest["time"]) - video_time)
                    if difference <= tolerance:
                        row["matched_audio_time_seconds"] = round(float(nearest["time"]), 2)
                        row["audio_match_difference_seconds"] = round(difference, 2)
                        if pd.notna(nearest["pitch_hz"]):
                            row["pitch_hz_nearby"] = round(float(nearest["pitch_hz"]), 1)
                        if pd.notna(nearest["rms_energy"]):
                            row["rms_energy_nearby"] = round(float(nearest["rms_energy"]), 6)
                aligned.append(row)
            combined_df = pd.DataFrame(aligned)
            st.caption(
                f"Video: {video_report.get('video_file', 'current video')} · "
                f"Audio: aligned using offset {sync_offset:.2f}s · "
                f"Matching tolerance: {tolerance:.2f}s"
            )
            st.dataframe(combined_df, use_container_width=True, hide_index=True)
            st.download_button(
                "Download combined evidence timeline (CSV)",
                combined_df.to_csv(index=False).encode("utf-8"),
                "rasaai_combined_evidence_timeline.csv",
                "text/csv",
                key="rasa_combined_evidence_csv",
            )
            st.download_button(
                "Download combined evidence timeline (JSON)",
                json.dumps({
                    "video_file": video_report.get("video_file"),
                    "audio_offset_seconds": float(sync_offset),
                    "matching_tolerance_seconds": float(tolerance),
                    "observations": combined_df.where(pd.notna(combined_df), None).to_dict(orient="records"),
                    "interpretation_limit": "Time-aligned measurements and model predictions are evidence for human review only. They do not establish internal emotion, mental health, acting ability, or casting suitability."
                }, indent=2, ensure_ascii=False, default=str),
                "rasaai_combined_evidence_timeline.json",
                "application/json",
                key="rasa_combined_evidence_json",
            )
            st.warning(
                "Audio/video timestamps must refer to the same recording timeline. This tool aligns measurements by time; "
                "it does not verify lip-sync or infer emotional meaning. Review the original footage and audio."
            )


# ---------- Standalone Haystack Retrieval tab ----------
with workflow_tabs[6]:
    _rasa_section_heading("07", "AUDITION LIBRARY", "Haystack Retrieval")
    st.caption(
        "Search saved audition reports using Haystack BM25 keyword retrieval. "
        "Results are relevant recorded evidence for human review, not casting recommendations."
    )

    saved_auditions = list(st.session_state.get("rasa_audition_comparisons", []))
    if not saved_auditions:
        st.info(
            "No saved auditions are available yet. Go to Video Analysis, analyze a clip, "
            "and click **Add this audition to comparison**. Then return here to search it."
        )
    else:
        st.write(f"Saved audition records available: **{len(saved_auditions)}**")
        if haystack_search_auditions is None:
            st.error(
                "Haystack is not available in this deployment. Check that `haystack-ai>=2.0,<3` "
                "is in requirements.txt and review the deployment logs."
            )
            with st.expander("Import error details"):
                st.code(HAYSTACK_SEARCH_IMPORT_ERROR or "Haystack import unavailable")
        else:
            # Filters are applied before BM25 retrieval so the result limit is
            # filled from the selected subset rather than filtering a small top-k afterward.
            character_options = sorted({
                str(item.get("selected_character") or "Unassigned")
                for item in saved_auditions
            }, key=str.casefold)
            status_options = sorted({
                str(item.get("reviewer_decision") or "Not reviewed")
                for item in saved_auditions
            }, key=str.casefold)

            filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])
            with filter_col1:
                retrieval_character = st.selectbox(
                    "Character", ["All characters"] + character_options,
                    key="rasa_haystack_character_filter",
                )
            with filter_col2:
                retrieval_status = st.selectbox(
                    "Review status", ["All statuses"] + status_options,
                    key="rasa_haystack_status_filter",
                )
            with filter_col3:
                retrieval_shortlisted_only = st.checkbox(
                    "Shortlisted only", key="rasa_haystack_shortlisted_filter"
                )

            query_col, limit_col = st.columns([5, 1])
            with query_col:
                retrieval_query = st.text_input(
                    "Search saved audition evidence",
                    placeholder="e.g. callback with reviewer notes about hand gestures",
                    key="rasa_haystack_standalone_query",
                )
            with limit_col:
                retrieval_limit = st.selectbox(
                    "Max results", [5, 10, 20], index=1,
                    key="rasa_haystack_standalone_limit",
                )

            search_clicked = st.button(
                "Retrieve auditions", type="primary",
                key="rasa_haystack_standalone_button",
                disabled=not bool(retrieval_query.strip()),
            )
            if search_clicked:
                try:
                    candidate_records = []
                    original_indices = []
                    for original_index, item in enumerate(saved_auditions):
                        character = str(item.get("selected_character") or "Unassigned")
                        status = str(item.get("reviewer_decision") or "Not reviewed")
                        if retrieval_character != "All characters" and character != retrieval_character:
                            continue
                        if retrieval_status != "All statuses" and status != retrieval_status:
                            continue
                        if retrieval_shortlisted_only and not bool(item.get("shortlisted", False)):
                            continue
                        candidate_records.append(item)
                        original_indices.append(original_index)

                    retrieval_results = haystack_search_auditions(
                        candidate_records, retrieval_query.strip(), top_k=retrieval_limit
                    ) if candidate_records else []

                    # The helper returns indices relative to candidate_records.
                    # Convert them back to indices in the full saved audition library.
                    mapped_results = []
                    for result in retrieval_results:
                        candidate_index = int(result.get("library_index", -1))
                        if 0 <= candidate_index < len(original_indices):
                            mapped = dict(result)
                            mapped["library_index"] = original_indices[candidate_index]
                            mapped_results.append(mapped)

                    st.session_state["rasa_haystack_standalone_results"] = {
                        "query": retrieval_query.strip(),
                        "character": retrieval_character,
                        "status": retrieval_status,
                        "shortlisted_only": retrieval_shortlisted_only,
                        "candidate_count": len(candidate_records),
                        "results": mapped_results,
                    }

                    # Keep a short session-only history so users can track recent searches.
                    history = st.session_state.get("rasa_haystack_search_history", [])
                    history.insert(0, {
                        "query": retrieval_query.strip(),
                        "character": retrieval_character,
                        "status": retrieval_status,
                        "shortlisted_only": retrieval_shortlisted_only,
                        "candidate_count": len(candidate_records),
                        "result_count": len(mapped_results),
                        "searched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    })
                    st.session_state["rasa_haystack_search_history"] = history[:10]
                except Exception as exc:
                    st.session_state.pop("rasa_haystack_standalone_results", None)
                    st.error(f"Haystack retrieval failed: {type(exc).__name__}: {exc}")

            search_history = st.session_state.get("rasa_haystack_search_history", [])
            if search_history:
                with st.expander("Recent search history (this session)", expanded=False):
                    st.caption("The latest 10 searches are kept in this browser session only; history is not saved to disk.")
                    for history_index, history_item in enumerate(search_history, start=1):
                        history_filters = []
                        if history_item.get("character") != "All characters":
                            history_filters.append(f"Character: {history_item['character']}")
                        if history_item.get("status") != "All statuses":
                            history_filters.append(f"Status: {history_item['status']}")
                        if history_item.get("shortlisted_only"):
                            history_filters.append("Shortlisted only")
                        st.write(
                            f"**{history_index}. {history_item.get('query', '')}** — "
                            f"{history_item.get('result_count', 0)} result(s) · "
                            f"{history_item.get('searched_at', '')}"
                        )
                        st.caption("Filters: " + (" · ".join(history_filters) if history_filters else "None"))

            retrieval_state = st.session_state.get("rasa_haystack_standalone_results", {})
            if retrieval_state.get("query"):
                st.subheader("Retrieved results")
                st.caption(f"Query: {retrieval_state['query']}")
                filter_summary = []
                if retrieval_state.get("character", "All characters") != "All characters":
                    filter_summary.append(f"Character: {retrieval_state['character']}")
                if retrieval_state.get("status", "All statuses") != "All statuses":
                    filter_summary.append(f"Status: {retrieval_state['status']}")
                if retrieval_state.get("shortlisted_only"):
                    filter_summary.append("Shortlisted only")
                st.caption("Filters: " + (" · ".join(filter_summary) if filter_summary else "None"))
                st.caption(f"Searched {retrieval_state.get('candidate_count', 0)} audition(s) matching the filters.")
                results = retrieval_state.get("results", [])
                if not results:
                    st.info("No matching records were returned. Try different keywords or broaden the filters.")
                else:
                    st.write(f"Found **{len(results)}** matching audition(s).")
                    for rank, result in enumerate(results, start=1):
                        try:
                            index = int(result.get("library_index", -1))
                        except (TypeError, ValueError):
                            continue
                        if not 0 <= index < len(saved_auditions):
                            continue
                        item = saved_auditions[index]
                        label = item.get("actor_label") or item.get("video_file") or f"Audition {index + 1}"
                        character = item.get("selected_character") or "Unassigned"
                        score = result.get("score")
                        score_label = f" · BM25 score {score:.3f}" if isinstance(score, (int, float)) else ""
                        with st.expander(f"{rank}. {label} — {character}{score_label}", expanded=(rank == 1)):
                            if item.get("analysis_type") == "vocal":
                                st.write(f"**Audio:** {item.get('audio_file') or 'Not available'}")
                                st.write(f"**Median pitch:** {item.get('median_pitch_hz', 'N/A')} Hz")
                                st.write(f"**Energy gaps:** {item.get('detected_energy_gaps_over_0_35s', 'N/A')}")
                            else:
                                st.write(f"**Video:** {item.get('video_file') or 'Not available'}")
                            st.write(f"**Analysis type:** {item.get('analysis_type') or 'video'}")
                            st.write(f"**Review status:** {item.get('reviewer_decision') or 'Not reviewed'}")
                            st.write(f"**Shortlisted:** {'Yes' if item.get('shortlisted', False) else 'No'}")
                            st.write(f"**Reviewer notes:** {item.get('reviewer_notes') or 'No reviewer notes'}")
                            st.caption("Matching indexed evidence")
                            st.text(str(result.get("content", ""))[:2500])

                    # Export only the currently displayed retrieval results.
                    export_rows = []
                    for rank, result in enumerate(results, start=1):
                        try:
                            index = int(result.get("library_index", -1))
                        except (TypeError, ValueError):
                            continue
                        if not 0 <= index < len(saved_auditions):
                            continue
                        item = saved_auditions[index]
                        export_rows.append({
                            "Rank": rank,
                            "Actor": item.get("actor_label") or "",
                            "Video file": item.get("video_file") or "",
                            "Character": item.get("selected_character") or "Unassigned",
                            "Review status": item.get("reviewer_decision") or "Not reviewed",
                            "Shortlisted": bool(item.get("shortlisted", False)),
                            "Reviewer notes": item.get("reviewer_notes") or "",
                            "BM25 score": result.get("score", ""),
                        })
                    if export_rows:
                        csv_buffer = io.StringIO(newline="")
                        writer = csv.DictWriter(csv_buffer, fieldnames=list(export_rows[0].keys()))
                        writer.writeheader()
                        writer.writerows(export_rows)
                        st.download_button(
                            "Download results as CSV",
                            data="\ufeff" + csv_buffer.getvalue(),
                            file_name="rasa_haystack_retrieval_results.csv",
                            mime="text/csv",
                            key="rasa_haystack_download_results",
                        )
                st.caption(
                    "BM25 is keyword-based retrieval. It does not reliably understand every paraphrase, "
                    "and its score is not a measure of acting quality or role suitability."
                )
            if st.button("Clear retrieval results", key="rasa_haystack_standalone_clear"):
                st.session_state.pop("rasa_haystack_standalone_results", None)
                st.rerun()


# ---------- Optional Db2 integration ----------
with workflow_tabs[7]:
    _rasa_section_heading("08", "OPTIONAL DATA CONNECTOR", "Db2 Database")
    st.caption(
        "Optional, locally configured Db2 persistence. RASA AI works without Db2; each user who wants this integration must provide access to their own Db2 instance. "
        "The account-specific local JSON library remains the source; sync is manual."
    )

    try:
        from src.db2_store import connection_status, ensure_schema, sync_auditions, fetch_auditions
        DB2_MODULE_ERROR = None
    except Exception as exc:
        connection_status = ensure_schema = sync_auditions = fetch_auditions = None
        DB2_MODULE_ERROR = f"{type(exc).__name__}: {exc}"

    with st.expander("Connection configuration", expanded=True):
        st.write("Set these environment variables before starting Streamlit:")
        st.code(
            '$env:DB2_HOST = "127.0.0.1"\n'
            '$env:DB2_PORT = "50000"\n'
            '$env:DB2_DATABASE = "your-database"\n'
            '$env:DB2_USER = "your-username"\n'
            '$env:DB2_PASSWORD = "your-password"\n'
            '$env:DB2_SSL = "false"  # set true only if your Db2 service requires TLS',
            language="powershell",
        )
        st.warning("Do not paste database passwords into chat or commit them to Git. Db2 LUW catalog SQL is used by this initial connector.")

    if DB2_MODULE_ERROR:
        st.error(f"Could not load the Db2 integration: {DB2_MODULE_ERROR}")
    else:
        db2_col1, db2_col2 = st.columns(2)
        with db2_col1:
            if st.button("Check Db2 connection", key="rasa_db2_check"):
                try:
                    st.success(connection_status())
                except Exception as exc:
                    st.error(f"Db2 connection failed: {type(exc).__name__}: {exc}")
        with db2_col2:
            if st.button("Initialize audition table", key="rasa_db2_init"):
                try:
                    ensure_schema()
                    st.success("RASA_AUDITIONS table is ready in the current Db2 schema.")
                except Exception as exc:
                    st.error(f"Could not initialize Db2 table: {type(exc).__name__}: {exc}")

        db2_auditions = list(st.session_state.get("rasa_audition_comparisons", []))
        st.write(f"Local audition records available to sync: **{len(db2_auditions)}**")
        if st.button(
            "Sync local audition library to Db2",
            type="primary",
            key="rasa_db2_sync",
            disabled=not bool(db2_auditions),
        ):
            try:
                synced_count = sync_auditions(db2_auditions)
                st.success(f"Synced {synced_count} audition record(s) to Db2. The JSON library was not changed.")
            except Exception as exc:
                st.error(f"Db2 sync failed: {type(exc).__name__}: {exc}")

        if st.button("Load recent Db2 records", key="rasa_db2_load"):
            try:
                st.session_state["rasa_db2_records"] = fetch_auditions(100)
            except Exception as exc:
                st.error(f"Could not load Db2 records: {type(exc).__name__}: {exc}")

        db2_records = st.session_state.get("rasa_db2_records", [])
        if db2_records:
            st.write(f"Records currently loaded from Db2: **{len(db2_records)}**")
            st.dataframe(
                [{
                    "Actor": row.get("actor_label"),
                    "Character": row.get("selected_character"),
                    "Review status": row.get("reviewer_decision"),
                    "Shortlisted": row.get("shortlisted"),
                    "Updated at": row.get("updated_at"),
                } for row in db2_records],
                use_container_width=True,
                hide_index=True,
            )
            with st.expander("Inspect full record payload"):
                st.json(db2_records[0].get("payload", {}))
        else:
            st.info("After configuring Db2, check the connection, initialize the table, then sync the local library.")
