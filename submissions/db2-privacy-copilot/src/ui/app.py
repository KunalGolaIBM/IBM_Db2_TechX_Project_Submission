"""Db2 Privacy Copilot landing page."""
import streamlit as st

st.set_page_config(
    page_title="Db2 Privacy Copilot",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {display:none;}
    .block-container {max-width: 1180px; padding-top: 1.4rem; padding-bottom: 3rem;}
    .topbar {display:flex; align-items:center; justify-content:space-between;
        border-bottom:1px solid #e7ebf0; padding:0 0 1rem; margin-bottom:2.8rem;}
    .brand {font-size:1.05rem; font-weight:700; color:#14263d; letter-spacing:-.02em;}
    .brand-mark {display:inline-flex; width:30px; height:30px; align-items:center;
        justify-content:center; border-radius:8px; background:#e8f1fb; color:#1769aa;
        margin-right:9px; font-size:1rem;}
    .topnav {font-size:.83rem; color:#5c6b7d; letter-spacing:.01em;}
    .eyebrow {color:#1769aa; font-size:.75rem; font-weight:700; letter-spacing:.14em;
        text-transform:uppercase; margin-bottom:1rem;}
    .hero-title {font-size:clamp(2.7rem, 5vw, 4.4rem); line-height:1.04;
        letter-spacing:-.055em; font-weight:700; color:#11243a; margin:0 0 1.25rem;}
    .hero-copy {max-width:640px; font-size:1.12rem; line-height:1.7; color:#536477;}
    .hero-note {font-size:.82rem; color:#7a8796; margin-top:1rem;}
    .hero-panel {background:linear-gradient(145deg,#f1f6fb,#e5eef7); border:1px solid #e0e9f1;
        border-radius:18px; min-height:315px; padding:28px; position:relative; overflow:hidden;}
    .panel-label {font-size:.72rem; font-weight:700; text-transform:uppercase;
        letter-spacing:.11em; color:#63768b;}
    .panel-title {font-size:1.18rem; font-weight:650; color:#1a3048; margin:12px 0 20px;}
    .signal {display:flex; align-items:center; gap:12px; background:rgba(255,255,255,.82);
        padding:13px 15px; border:1px solid #e4ebf1; border-radius:10px; margin:10px 0;
        box-shadow:0 4px 16px rgba(27,55,84,.04);}
    .signal-dot {width:9px; height:9px; border-radius:50%; background:#2e8b76; flex:none;}
    .signal-text {font-size:.85rem; color:#33485f; font-weight:550;}
    .signal-meta {font-size:.72rem; color:#7c8b9b; margin-left:auto;}
    .section-kicker {font-size:.73rem; text-transform:uppercase; letter-spacing:.13em;
        color:#1769aa; font-weight:700;}
    .section-title {font-size:2rem; letter-spacing:-.035em; color:#152941; font-weight:680;
        margin:.5rem 0 .65rem;}
    .section-copy {color:#647386; line-height:1.65; max-width:720px;}
    .capability {height:100%; min-height:210px; border:1px solid #e4e9ef; border-radius:13px;
        background:#fff; padding:23px; transition:border-color .15s, box-shadow .15s;}
    .capability:hover {border-color:#b8ccdf; box-shadow:0 10px 28px rgba(28,57,86,.07);}
    .cap-icon {width:38px; height:38px; border-radius:10px; background:#edf4fa;
        display:flex; align-items:center; justify-content:center; color:#1769aa; font-size:1.1rem;}
    .cap-title {font-size:1.05rem; font-weight:650; color:#1d334c; margin:17px 0 8px;}
    .cap-copy {font-size:.88rem; color:#68788a; line-height:1.65;}
    .workflow {border-top:1px solid #e5eaf0; padding:23px 8px 0; min-height:165px;}
    .step-no {font-size:.73rem; color:#1769aa; font-weight:700; letter-spacing:.1em;}
    .step-title {font-size:1rem; font-weight:650; color:#1d334c; margin:10px 0 7px;}
    .step-copy {font-size:.85rem; line-height:1.6; color:#6b7a8c;}
    .trust-band {background:#f4f7fa; border:1px solid #e8edf2; border-radius:14px; padding:22px 25px;}
    .trust-head {font-size:.8rem; font-weight:700; color:#2c435c; margin-bottom:6px;}
    .trust-copy {font-size:.83rem; line-height:1.55; color:#68788a;}
    .footer {border-top:1px solid #e7ebf0; margin-top:3rem; padding-top:1.2rem;
        font-size:.78rem; color:#7d8997;}
    div.stButton > button[kind="primary"] {background:#1769aa; border:1px solid #1769aa;
        border-radius:7px; min-height:46px; padding:0 24px; font-weight:650;}
    div.stButton > button[kind="primary"]:hover {background:#125789; border-color:#125789;}
    @media (max-width:700px) {
        .topnav {display:none;} .hero-panel {min-height:270px;}
        .block-container {padding-left:1rem; padding-right:1rem;}
    }
    </style>
    <div class="topbar">
      <div class="brand"><span class="brand-mark">✦</span>Db2 Privacy Copilot</div>
      <div class="topnav">DATA DISCOVERY&nbsp;&nbsp; · &nbsp;&nbsp;PRIVACY OPERATIONS&nbsp;&nbsp; · &nbsp;&nbsp;AUDITABILITY</div>
    </div>
    """,
    unsafe_allow_html=True,
)

left, right = st.columns([1.15, 0.85], gap="large", vertical_alignment="center")
with left:
    st.markdown(
        """
        <div class="eyebrow">Privacy operations for IBM Db2</div>
        <h1 class="hero-title">Know your data.<br>Act with confidence.</h1>
        <div class="hero-copy">A decision-support workspace for discovering personal data,
        reviewing privacy signals, and preparing accountable data-rights workflows.</div>
        <div class="hero-note">Human review stays in control of sensitive decisions.</div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    if st.button("Open the workspace  →", type="primary"):
        st.switch_page("pages/1_🔐_Login.py")
    st.caption("Choose an access profile on the sign-in page to open the workspace.")
with right:
    st.markdown(
        """
        <div class="hero-panel">
          <div class="panel-label">A clearer view of privacy data</div>
          <div class="panel-title">From database metadata to reviewable action</div>
          <div class="signal"><span class="signal-dot"></span><span class="signal-text">Schema relationships mapped</span><span class="signal-meta">DISCOVERY</span></div>
          <div class="signal"><span class="signal-dot" style="background:#5681b5"></span><span class="signal-text">Personal-data candidates surfaced</span><span class="signal-meta">CLASSIFICATION</span></div>
          <div class="signal"><span class="signal-dot" style="background:#c38b37"></span><span class="signal-text">Actions prepared for human review</span><span class="signal-meta">GOVERNANCE</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")
st.write("")
st.markdown(
    "<div class='section-kicker'>Capabilities</div><div class='section-title'>A practical privacy workflow</div><div class='section-copy'>Bring schema context, classification, consent records, and review steps into one Db2-focused workspace.</div>",
    unsafe_allow_html=True,
)
st.write("")

capabilities = [
    ("⌕", "Discover data", "Map tables, columns, and relationships to understand where personal data may reside."),
    ("◈", "Classify signals", "Combine value patterns and column context to surface candidates with confidence and review status."),
    ("✓", "Manage consent", "Record and inspect consent across business time and system history."),
    ("↗", "Prepare rights plans", "Generate reviewable erasure plans that account for relationships and retention rules."),
    ("⊘", "Apply guardrails", "Validate proposed SQL against deterministic checks before sensitive operations."),
    ("≋", "Verify the audit trail", "Maintain a hash-linked record of actions and check the integrity of the chain."),
]
for row in (capabilities[:3], capabilities[3:]):
    cols = st.columns(3, gap="medium")
    for col, (icon, title, description) in zip(cols, row):
        with col:
            st.markdown(
                f"<div class='capability'><div class='cap-icon'>{icon}</div><div class='cap-title'>{title}</div><div class='cap-copy'>{description}</div></div>",
                unsafe_allow_html=True,
            )

st.write("")
st.write("")
st.markdown(
    "<div class='section-kicker'>How it works</div><div class='section-title'>A human-led path from discovery to action</div>",
    unsafe_allow_html=True,
)
steps = [
    ("01", "Discover", "Map the schema and its relationships."),
    ("02", "Classify", "Review personal-data candidates and confidence."),
    ("03", "Plan", "Prepare a rights workflow with retention context."),
    ("04", "Approve", "Keep review and approval with authorized people."),
]
cols = st.columns(4, gap="medium")
for col, (number, title, copy) in zip(cols, steps):
    with col:
        st.markdown(
            f"<div class='workflow'><div class='step-no'>{number}</div><div class='step-title'>{title}</div><div class='step-copy'>{copy}</div></div>",
            unsafe_allow_html=True,
        )

st.write("")
st.markdown(
    """
    <div class="trust-band">
      <div class="trust-head">Designed for review, not automatic legal decisions</div>
      <div class="trust-copy">The workspace supports selected DPDP-related privacy operations. It does not replace legal advice or a complete compliance program. Retention rules and classifications require review by qualified owners. The included clinic records are synthetic.</div>
    </div>
    <div class="footer">Db2 Privacy Copilot&nbsp;&nbsp; · &nbsp;&nbsp;Privacy operations workspace&nbsp;&nbsp; · &nbsp;&nbsp;<a href="https://github.com/dreameterftw/db2-privacy-copilot" target="_blank">View source on GitHub</a></div>
    """,
    unsafe_allow_html=True,
)
