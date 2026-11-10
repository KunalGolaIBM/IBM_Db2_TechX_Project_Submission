"""
Reusable UI Report Cards and Metrics Blocks.
"""
from typing import Any, Optional
import streamlit as st


def render_kpi_card(title: str, value: Any, delta: Optional[str] = None, help_text: Optional[str] = None):
    """Renders a polished KPI metric card."""
    st.metric(label=title, value=value, delta=delta, help=help_text)


def render_severity_badge(level: str) -> str:
    """Returns HTML for an impact severity pill."""
    lvl = level.upper()
    colors = {
        "CRITICAL": "#DA1E28",
        "HIGH": "#FA4D56",
        "MEDIUM": "#F1C21B",
        "LOW": "#42BE65",
    }
    bg = colors.get(lvl, "#6F6F6F")
    text_color = "black" if lvl == "MEDIUM" else "white"
    return f"<span style='background-color:{bg}; color:{text_color}; padding:4px 10px; border-radius:12px; font-weight:700; font-size:12px;'>{lvl}</span>"
