"""Navigation and visual theme."""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
.stApp { background: radial-gradient(ellipse at 80% 0%, #13283d 0%, #0b1220 42%, #090e18 100%); color:#e8eef8; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
h1,h2,h3 {font-family:'Space Grotesk',sans-serif; letter-spacing:-.03em;}
.block-container {max-width:1440px;padding-top:2rem;padding-bottom:3rem;}
[data-testid="stSidebar"] {background:#0a111d;border-right:1px solid #1e2c3d;}
[data-testid="stMetric"] {background:linear-gradient(145deg,#101e2d,#101723);border:1px solid #263749;padding:18px 20px;border-radius:16px;}
[data-testid="stMetricValue"] {color:#f2f7ff;}
div[data-testid="stAlert"] {border-radius:12px;}
button[kind="primary"] {background:#16a6c9;border:0;}
.hero {background:linear-gradient(120deg,rgba(26,119,160,.2),rgba(55,87,168,.12));border:1px solid #24465c;border-radius:20px;padding:26px 30px;margin:6px 0 22px;}
.eyebrow {color:#59d0e5;font-size:.76rem;font-weight:700;letter-spacing:.15em;text-transform:uppercase;}
.muted {color:#92a5ba;}
</style>
"""
PAGES = ["Dashboard", "AI SQL Assistant", "Data Explorer", "Analytics", "Query History", "Database Connection", "About"]

def render_sidebar():
    st.sidebar.markdown("<div style='font:700 22px Space Grotesk;color:#eaf5ff'>◈ Db2Ops <span style='color:#55cee3'>AI</span></div><div style='color:#90a8bf;font-size:12px;margin:4px 0 24px'>INTELLIGENT DATABASE COPILOT</div>", unsafe_allow_html=True)
    return st.sidebar.radio("Workspace", PAGES, label_visibility="collapsed", key="nav_page")
