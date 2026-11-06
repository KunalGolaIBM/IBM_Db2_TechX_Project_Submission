"""
Reusable Streamlit UI Components, Styling, and Metric Cards.
High-contrast, professional, and razor-sharp visibility.
"""

import streamlit as st

def inject_custom_css():
    st.markdown("""
    <style>
    /* Global Typography */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"], .stMarkdown, .stText {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Metric Cards - High Contrast & Sharp Visibility */
    .metric-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%) !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        padding: 20px 22px !important;
        color: #f8fafc !important;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.35) !important;
    }
    .metric-title {
        font-size: 0.82rem !important;
        font-weight: 700 !important;
        color: #94a3b8 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        margin-bottom: 8px !important;
    }
    .metric-value {
        font-size: 1.95rem !important;
        font-weight: 800 !important;
        color: #ffffff !important;
        margin-bottom: 6px !important;
        line-height: 1.2 !important;
    }
    .metric-subtitle {
        font-size: 0.82rem !important;
        font-weight: 600 !important;
    }

    /* Status Badges */
    .badge-critical {
        background-color: rgba(239, 68, 68, 0.2) !important;
        color: #f87171 !important;
        border: 1px solid rgba(239, 68, 68, 0.5) !important;
        padding: 4px 10px !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        font-size: 0.78rem !important;
    }
    .badge-warning {
        background-color: rgba(245, 158, 11, 0.2) !important;
        color: #fbbf24 !important;
        border: 1px solid rgba(245, 158, 11, 0.5) !important;
        padding: 4px 10px !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        font-size: 0.78rem !important;
    }
    .badge-good {
        background-color: rgba(16, 185, 129, 0.2) !important;
        color: #34d399 !important;
        border: 1px solid rgba(16, 185, 129, 0.5) !important;
        padding: 4px 10px !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        font-size: 0.78rem !important;
    }
    .badge-upcoming {
        background-color: rgba(59, 130, 246, 0.2) !important;
        color: #60a5fa !important;
        border: 1px solid rgba(59, 130, 246, 0.5) !important;
        padding: 4px 10px !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        font-size: 0.78rem !important;
    }

    /* AI Insight Box */
    .ai-insight-box {
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.4) 0%, rgba(15, 23, 42, 0.8) 100%) !important;
        border: 1px solid rgba(59, 130, 246, 0.4) !important;
        border-left: 4px solid #38bdf8 !important;
        border-radius: 12px !important;
        padding: 18px 22px !important;
        margin-bottom: 20px !important;
        color: #f8fafc !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2) !important;
    }

    /* Recipe Card */
    .recipe-card {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        padding: 20px 22px !important;
        margin-bottom: 16px !important;
        color: #f8fafc !important;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15) !important;
    }

    /* Section Cards */
    .glass-card {
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        padding: 22px !important;
        margin-bottom: 16px !important;
        color: #f8fafc !important;
    }

    /* High contrast headers */
    h1, h2, h3, h4, h5, h6 {
        color: #f8fafc !important;
    }
    </style>
    """, unsafe_allow_html=True)

def render_metric_card(title: str, value: str, subtitle: str = "", delta_color: str = "#38bdf8"):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-subtitle" style="color: {delta_color}">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)
