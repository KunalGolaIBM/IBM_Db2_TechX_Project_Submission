"""Dashboard theme: palette, global CSS, floating motion, and UI fragments."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

COLORS = {
    "bg_deep": "#060912",
    "bg_panel": "rgba(14, 22, 42, 0.82)",
    "border": "rgba(99, 179, 237, 0.18)",
    "border_strong": "rgba(99, 179, 237, 0.35)",
    "accent": "#63b3ed",
    "accent_soft": "rgba(99, 179, 237, 0.12)",
    "violet": "#a78bfa",
    "magenta": "#f472b6",
    "text": "#f1f5f9",
    "muted": "#94a3b8",
    "danger": "#fb7185",
    "warning": "#fbbf24",
    "success": "#34d399",
}

PLOTLY_TEMPLATE = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(10, 16, 30, 0.65)",
    "font": {"family": "IBM Plex Sans, system-ui, sans-serif", "color": COLORS["text"], "size": 12},
    "xaxis": {
        "gridcolor": "rgba(148, 163, 184, 0.08)",
        "linecolor": "rgba(148, 163, 184, 0.25)",
        "zerolinecolor": "rgba(148, 163, 184, 0.15)",
    },
    "yaxis": {
        "gridcolor": "rgba(148, 163, 184, 0.08)",
        "linecolor": "rgba(148, 163, 184, 0.25)",
        "zerolinecolor": "rgba(148, 163, 184, 0.15)",
    },
    "legend": {"bgcolor": "rgba(0,0,0,0)", "bordercolor": "rgba(0,0,0,0)"},
    "margin": {"l": 8, "r": 8, "t": 40, "b": 8},
}

HORIZON_LABELS = {
    "5m": "5 min",
    "15m": "15 min",
    "60m": "1 hour",
    "1d": "1 day",
}


def horizon_label(horizon: str) -> str:
    return HORIZON_LABELS.get(horizon, horizon)


_FLOATING_CSS = """
            @keyframes aegis-float-y {
                0%, 100% { transform: translateY(0) translateX(0); }
                50% { transform: translateY(-12px) translateX(5px); }
            }
            @keyframes aegis-float-y-slow {
                0%, 100% { transform: translateY(0) rotate(0deg); }
                50% { transform: translateY(-18px) rotate(1.5deg); }
            }
            @keyframes aegis-float-orb {
                0%, 100% {
                    transform: translate(0, 0) scale(1);
                    opacity: 0.35;
                }
                33% {
                    transform: translate(28px, -36px) scale(1.06);
                    opacity: 0.5;
                }
                66% {
                    transform: translate(-18px, -22px) scale(0.94);
                    opacity: 0.3;
                }
            }
            @keyframes aegis-float-glow {
                0%, 100% { box-shadow: 0 0 20px rgba(99, 179, 237, 0.08); }
                50% { box-shadow: 0 0 32px rgba(99, 179, 237, 0.18); }
            }
            @keyframes aegis-badge-float {
                0%, 100% { transform: translateY(0); }
                50% { transform: translateY(-4px); }
            }
            @keyframes aegis-panel-reveal {
                0% { opacity: 0; transform: translateY(8px) scale(0.985); }
                100% { opacity: 1; transform: translateY(0) scale(1); }
            }
            @keyframes aegis-toggle-pop {
                0% { transform: scale(0.96); }
                60% { transform: scale(1.02); }
                100% { transform: scale(1); }
            }
            .aegis-float-layer {
                position: fixed;
                inset: 0;
                pointer-events: none;
                z-index: 0;
                overflow: hidden;
            }
            [data-testid="stAppViewContainer"],
            [data-testid="stMain"],
            [data-testid="stSidebar"],
            [data-testid="stHeader"],
            [data-testid="stBottom"],
            [data-testid="stBottomBlockContainer"],
            .block-container {
                position: relative;
                z-index: 1;
            }
            [data-testid="stMarkdownContainer"] h1,
            [data-testid="stMarkdownContainer"] h2,
            [data-testid="stMarkdownContainer"] h3,
            [data-testid="stMarkdownContainer"] p,
            [data-testid="stWidgetLabel"],
            [data-testid="stCaptionContainer"],
            label[data-testid="stWidgetLabel"],
            .stTextInput label,
            .stSelectbox label,
            .stMultiSelect label,
            .stSlider label,
            .stToggle label {
                color: var(--aegis-text) !important;
            }
            [data-testid="stMarkdownContainer"] .aegis-login-brand p,
            [data-testid="stMarkdownContainer"] .aegis-topbar-sub,
            [data-testid="stMarkdownContainer"] .aegis-pred-label,
            [data-testid="stMarkdownContainer"] .aegis-empty {
                color: var(--aegis-muted) !important;
            }
            [data-baseweb="tab-list"] button,
            [data-baseweb="tab"] {
                color: var(--aegis-muted) !important;
            }
            [data-baseweb="tab"][aria-selected="true"] {
                color: var(--aegis-accent) !important;
            }
            .aegis-orb {
                position: absolute;
                border-radius: 50%;
                filter: blur(40px);
                animation: aegis-float-orb ease-in-out infinite;
            }
            .aegis-orb-1 {
                width: 280px; height: 280px;
                top: 8%; left: -4%;
                background: rgba(99, 179, 237, 0.22);
                animation-duration: 14s;
            }
            .aegis-orb-2 {
                width: 220px; height: 220px;
                top: 55%; right: -2%;
                background: rgba(167, 139, 250, 0.2);
                animation-duration: 18s;
                animation-delay: -4s;
            }
            .aegis-orb-3 {
                width: 160px; height: 160px;
                bottom: 12%; left: 35%;
                background: rgba(244, 114, 182, 0.14);
                animation-duration: 16s;
                animation-delay: -7s;
            }
            .aegis-orb-4 {
                width: 120px; height: 120px;
                top: 22%; right: 28%;
                background: rgba(52, 211, 153, 0.12);
                animation-duration: 12s;
                animation-delay: -2s;
            }
            .aegis-float,
            .aegis-pred-card,
            .aegis-panel,
            .aegis-empty {
                animation: aegis-float-y 5.5s ease-in-out infinite,
                           aegis-float-glow 5.5s ease-in-out infinite;
            }
            .aegis-pred-grid .aegis-pred-card:nth-child(1) { animation-delay: 0s, 0s; }
            .aegis-pred-grid .aegis-pred-card:nth-child(2) { animation-delay: 0.4s, 0.4s; }
            .aegis-pred-grid .aegis-pred-card:nth-child(3) { animation-delay: 0.8s, 0.8s; }
            .aegis-pred-grid .aegis-pred-card:nth-child(4) { animation-delay: 1.2s, 1.2s; }
            .aegis-login-brand {
                animation: aegis-float-y-slow 7s ease-in-out infinite;
            }
            .aegis-topbar-meta .aegis-badge {
                animation: aegis-badge-float 4s ease-in-out infinite;
            }
            .aegis-topbar-meta .aegis-badge:nth-child(2) { animation-delay: 0.35s; }
            .aegis-topbar-meta .aegis-badge:nth-child(3) { animation-delay: 0.7s; }
            .aegis-chip {
                animation: aegis-badge-float 5s ease-in-out infinite;
            }
            .aegis-assistant-panel {
                animation: aegis-panel-reveal 0.45s ease-out;
            }
            .aegis-assistant-toggle {
                animation: aegis-toggle-pop 0.28s ease-out;
            }
            @media (prefers-reduced-motion: reduce) {
                .aegis-orb, .aegis-float, .aegis-pred-card, .aegis-panel,
                .aegis-empty, .aegis-login-brand,
                .aegis-topbar-meta .aegis-badge, .aegis-chip {
                    animation: none !important;
                }
            }
"""


def inject_futuristic_theme() -> None:
    st.markdown(
        f"""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap" rel="stylesheet">
        <style>
            :root {{
                --aegis-accent: {COLORS["accent"]};
                --aegis-text: {COLORS["text"]};
                --aegis-muted: {COLORS["muted"]};
                --aegis-border: {COLORS["border"]};
            }}
            {_FLOATING_CSS}
            .stApp {{
                position: relative;
                overflow-x: hidden;
                background:
                    radial-gradient(ellipse 70% 45% at 0% 0%, rgba(99, 179, 237, 0.08), transparent 55%),
                    radial-gradient(ellipse 50% 35% at 100% 0%, rgba(167, 139, 250, 0.07), transparent 50%),
                    linear-gradient(180deg, #060912 0%, #0a1020 50%, #060912 100%);
                color: var(--aegis-text);
                font-family: 'IBM Plex Sans', system-ui, sans-serif;
            }}
            #MainMenu, footer, header[data-testid="stHeader"] {{
                background: transparent !important;
            }}
            .block-container {{
                padding-top: 1.25rem;
                padding-bottom: 2rem;
                max-width: 1600px;
                padding-left: 2rem;
                padding-right: 2rem;
            }}
            [data-testid="stSidebar"] > div {{
                position: relative;
                z-index: 1;
            }}
            h1, h2, h3 {{
                font-family: 'IBM Plex Sans', sans-serif !important;
                letter-spacing: -0.02em;
            }}
            h1 {{
                font-size: 1.75rem !important;
                font-weight: 700 !important;
                color: {COLORS["text"]} !important;
            }}
            h2 {{
                font-size: 1.05rem !important;
                font-weight: 600 !important;
                color: {COLORS["text"]} !important;
                margin-bottom: 0.75rem !important;
            }}
            h3 {{
                font-size: 0.95rem !important;
                color: {COLORS["muted"]} !important;
            }}
            p, label, .stMarkdown, span {{
                font-family: 'IBM Plex Sans', sans-serif !important;
            }}
            [data-testid="stSidebar"] {{
                background: linear-gradient(180deg, #0a1020 0%, #060912 100%) !important;
                border-right: 1px solid {COLORS["border"]};
            }}
            [data-testid="stSidebar"] .block-container {{ padding-top: 1rem; }}
            [data-testid="stSidebar"] h1,
            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3 {{
                font-size: 0.7rem !important;
                font-weight: 600 !important;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                color: {COLORS["muted"]} !important;
            }}
            [data-testid="stMetric"] {{
                background: {COLORS["bg_panel"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 12px;
                padding: 0.85rem 1rem;
                animation: aegis-float-y 6s ease-in-out infinite;
            }}
            [data-testid="stMetricLabel"] {{
                color: var(--aegis-muted) !important;
                font-size: 0.7rem !important;
                letter-spacing: 0.06em;
                text-transform: uppercase;
            }}
            [data-testid="stMetricValue"] {{
                color: var(--aegis-text) !important;
                font-family: 'IBM Plex Mono', monospace !important;
                font-size: 1.2rem !important;
            }}
            .aegis-mono, .aegis-pred-value, .aegis-pred-cell {{
                font-family: 'IBM Plex Mono', monospace !important;
            }}
            .aegis-pred-label {{
                font-size: 0.68rem !important;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                color: var(--aegis-muted);
                font-weight: 500;
            }}
            .aegis-pred-value {{
                font-size: 1.35rem;
                font-weight: 500;
                line-height: 1.25;
            }}
            .aegis-pred-value-lg {{
                font-size: 1.65rem;
                font-family: 'IBM Plex Mono', monospace !important;
            }}
            .aegis-pred-card {{
                background: {COLORS["bg_panel"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 12px;
                padding: 0.9rem 1rem;
                min-height: 76px;
            }}
            .aegis-pred-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 0.65rem;
                margin-bottom: 1rem;
            }}
            @media (max-width: 1100px) {{
                .aegis-pred-grid {{ grid-template-columns: repeat(2, 1fr); }}
            }}
            @media (max-width: 520px) {{
                .aegis-pred-grid {{ grid-template-columns: 1fr; }}
            }}
            .aegis-pred-table {{
                width: 100%;
                border-collapse: separate;
                border-spacing: 0 4px;
                font-family: 'IBM Plex Mono', monospace !important;
                font-size: 0.8rem;
            }}
            .aegis-pred-table th {{
                font-size: 0.65rem;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                color: {COLORS["muted"]};
                text-align: left;
                padding: 0.45rem 0.7rem;
                border-bottom: 1px solid {COLORS["border"]};
                font-weight: 600;
            }}
            .aegis-pred-table td {{
                padding: 0.5rem 0.7rem;
                color: {COLORS["text"]};
                background: rgba(10, 16, 30, 0.5);
            }}
            .aegis-pred-table tr td:first-child {{ border-radius: 8px 0 0 8px; }}
            .aegis-pred-table tr td:last-child {{ border-radius: 0 8px 8px 0; }}
            .aegis-telemetry-strip {{
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 0.85rem;
                margin-bottom: 0.85rem;
            }}
            @media (max-width: 900px) {{
                .aegis-telemetry-strip {{ grid-template-columns: 1fr; }}
            }}
            .aegis-forecast-compact .aegis-compact-row {{
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                gap: 0.75rem;
                padding: 0.4rem 0;
                border-bottom: 1px solid rgba(148, 163, 184, 0.1);
            }}
            .aegis-forecast-compact .aegis-compact-row:last-child {{ border-bottom: none; }}
            .aegis-forecast-compact .aegis-compact-value {{
                font-family: 'IBM Plex Mono', monospace !important;
                font-size: 0.95rem;
                text-align: right;
            }}
            .stTabs [data-baseweb="tab-list"] {{
                gap: 4px;
                background: rgba(10, 16, 30, 0.7);
                border-radius: 10px;
                padding: 4px;
                border: 1px solid {COLORS["border"]};
            }}
            .stTabs [data-baseweb="tab"] {{
                font-size: 0.8rem !important;
                font-weight: 500 !important;
                color: var(--aegis-muted) !important;
                border-radius: 8px;
                padding: 0.45rem 0.9rem;
            }}
            .stTabs [aria-selected="true"] {{
                background: {COLORS["accent_soft"]} !important;
                color: {COLORS["accent"]} !important;
                border: 1px solid {COLORS["border_strong"]} !important;
            }}
            .stButton > button {{
                font-weight: 500 !important;
                font-size: 0.8rem !important;
                border-radius: 8px !important;
                border: 1px solid {COLORS["border_strong"]} !important;
                background: {COLORS["accent_soft"]} !important;
                color: {COLORS["accent"]} !important;
                transition: background 0.15s ease, border-color 0.15s ease, transform 0.2s ease;
            }}
            .stButton > button:hover {{
                background: rgba(99, 179, 237, 0.2) !important;
                border-color: {COLORS["accent"]} !important;
                color: {COLORS["text"]} !important;
                transform: translateY(-2px);
            }}
            [data-testid="stFormSubmitButton"] > button {{
                background: {COLORS["accent"]} !important;
                color: #060912 !important;
                font-weight: 600 !important;
                border: none !important;
            }}
            .stTextInput input,
            .stSelectbox div[data-baseweb="select"] > div,
            .stMultiSelect div[data-baseweb="select"] > div {{
                background: rgba(10, 16, 30, 0.85) !important;
                border-color: {COLORS["border"]} !important;
                color: var(--aegis-text) !important;
                border-radius: 8px !important;
            }}
            [data-testid="stDataFrame"] {{
                border: 1px solid {COLORS["border"]};
                border-radius: 10px;
                overflow: hidden;
            }}
            .aegis-topbar {{
                display: flex;
                flex-wrap: wrap;
                align-items: flex-end;
                justify-content: space-between;
                gap: 1rem;
                margin-bottom: 1.25rem;
                padding-bottom: 1rem;
                border-bottom: 1px solid {COLORS["border"]};
            }}
            .aegis-topbar-title {{
                margin: 0;
                font-size: 1.5rem !important;
                font-weight: 700 !important;
                color: {COLORS["text"]} !important;
            }}
            .aegis-topbar-sub {{
                margin: 0.25rem 0 0;
                color: {COLORS["muted"]};
                font-size: 0.9rem;
            }}
            .aegis-topbar-meta {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
                align-items: center;
            }}
            .aegis-badge {{
                display: inline-flex;
                align-items: center;
                gap: 0.35rem;
                padding: 0.2rem 0.65rem;
                border-radius: 999px;
                font-size: 0.72rem;
                font-weight: 500;
                border: 1px solid {COLORS["border"]};
                background: rgba(10, 16, 30, 0.6);
                color: {COLORS["muted"]};
            }}
            .aegis-badge-live {{
                border-color: rgba(52, 211, 153, 0.35);
                color: {COLORS["success"]};
                background: rgba(52, 211, 153, 0.08);
            }}
            .aegis-badge-live::before {{
                content: "";
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: {COLORS["success"]};
                box-shadow: 0 0 8px {COLORS["success"]};
                animation: aegis-badge-float 2.5s ease-in-out infinite;
            }}
            .aegis-badge-offline {{
                border-color: rgba(251, 113, 133, 0.35);
                color: {COLORS["danger"]};
                background: rgba(251, 113, 133, 0.08);
            }}
            .aegis-panel {{
                background: {COLORS["bg_panel"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 12px;
                padding: 1rem 1.15rem;
                margin-bottom: 0.85rem;
            }}
            .aegis-advice-buy {{
                border-left: 3px solid {COLORS["success"]};
                background: rgba(52, 211, 153, 0.06);
            }}
            .aegis-advice-sell {{
                border-left: 3px solid {COLORS["danger"]};
                background: rgba(251, 113, 133, 0.06);
            }}
            .aegis-advice-hold {{
                border-left: 3px solid {COLORS["warning"]};
                background: rgba(251, 191, 36, 0.06);
            }}
            .aegis-advice-title {{
                font-size: 1rem;
                font-weight: 600;
                margin-bottom: 0.3rem;
            }}
            .aegis-login-brand {{
                text-align: center;
                margin-bottom: 1.75rem;
                pointer-events: none;
            }}
            .aegis-login-brand h1 {{
                font-size: 1.65rem !important;
                margin: 0.5rem 0 0.35rem !important;
            }}
            .aegis-login-brand p {{
                color: {COLORS["muted"]};
                font-size: 0.9rem;
                margin: 0;
            }}
            .aegis-chip {{
                display: inline-block;
                margin: 0.2rem 0.3rem 0.2rem 0;
                padding: 0.15rem 0.55rem;
                border: 1px solid {COLORS["border"]};
                border-radius: 6px;
                font-family: 'IBM Plex Mono', monospace !important;
                font-size: 0.72rem;
                color: {COLORS["accent"]};
            }}
            .aegis-assistant-overlay {{
                position: fixed;
                inset: 0;
                z-index: 9999;
                display: none;
                align-items: center;
                justify-content: center;
                padding: 1rem;
                background: rgba(2, 6, 23, 0.82);
                backdrop-filter: blur(16px);
            }}
            .aegis-assistant-overlay.aegis-open {{
                display: flex;
            }}
            .aegis-assistant-shell {{
                width: min(1120px, 100%);
                max-height: 92vh;
                overflow: auto;
                border-radius: 24px;
                padding: 1rem;
                border: 1px solid rgba(99, 179, 237, 0.24);
                background: linear-gradient(180deg, rgba(9, 15, 28, 0.98), rgba(5, 9, 18, 0.98));
                box-shadow: 0 30px 80px rgba(0, 0, 0, 0.38);
            }}
            .aegis-assistant-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                gap: 1rem;
                margin-bottom: 0.8rem;
            }}
            .aegis-assistant-title {{
                margin: 0;
                font-size: 1.1rem !important;
                font-weight: 700 !important;
                color: {COLORS["text"]} !important;
            }}
            .aegis-assistant-subtitle {{
                margin: 0.2rem 0 0;
                color: {COLORS["muted"]};
                font-size: 0.86rem;
            }}
            .aegis-assistant-close {{
                display: flex;
                justify-content: flex-end;
            }}
            .aegis-assistant-close > div {{
                display: inline-block;
            }}
            .aegis-assistant-grid {{
                display: grid;
                grid-template-columns: 1.05fr 0.95fr;
                gap: 1rem;
                margin-top: 0.75rem;
            }}
            .aegis-assistant-card {{
                background: rgba(10, 16, 30, 0.72);
                border: 1px solid {COLORS["border"]};
                border-radius: 16px;
                padding: 0.95rem;
            }}
            .aegis-assistant-card h4 {{
                margin: 0 0 0.45rem;
                color: {COLORS["text"]};
                font-size: 0.95rem;
            }}
            .aegis-assistant-card p {{
                margin: 0 0 0.6rem;
                color: {COLORS["muted"]};
                font-size: 0.84rem;
            }}
            .aegis-chat-history {{
                display: flex;
                flex-direction: column;
                gap: 0.55rem;
                margin-top: 0.75rem;
            }}
            .aegis-chat-bubble {{
                padding: 0.7rem 0.8rem;
                border-radius: 12px;
                border: 1px solid {COLORS["border"]};
                font-size: 0.85rem;
                line-height: 1.45;
            }}
            .aegis-chat-bubble-user {{
                background: rgba(99, 179, 237, 0.12);
                border-color: rgba(99, 179, 237, 0.24);
            }}
            .aegis-chat-bubble-assistant {{
                background: rgba(167, 139, 250, 0.09);
                border-color: rgba(167, 139, 250, 0.24);
            }}
            .aegis-assistant-list {{
                display: flex;
                flex-direction: column;
                gap: 0.45rem;
                margin-top: 0.6rem;
            }}
            .aegis-assistant-list-item {{
                padding: 0.55rem 0.65rem;
                border-radius: 10px;
                background: rgba(10, 16, 30, 0.55);
                border: 1px solid rgba(148, 163, 184, 0.15);
                font-size: 0.8rem;
                color: {COLORS["text"]};
            }}
            @media (max-width: 900px) {{
                .aegis-assistant-grid {{ grid-template-columns: 1fr; }}
            }}
            .aegis-empty {{
                text-align: center;
                padding: 2rem 1rem;
                color: {COLORS["muted"]};
                border: 1px dashed {COLORS["border"]};
                border-radius: 12px;
                background: rgba(10, 16, 30, 0.4);
            }}
            .aegis-empty-title {{
                font-weight: 600;
                color: {COLORS["text"]};
                margin-bottom: 0.35rem;
            }}
            .stAlert {{ border-radius: 10px !important; }}
            div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 12px; }}
            /* Material Symbols Font & Icon Fallback Fix (e.g., keyboard_double_arrow_left) */
            [data-testid="stIconMaterial"],
            [class*="material-symbols"],
            .material-symbols-outlined,
            .material-icons,
            .material-icons-outlined,
            [data-testid="stSidebarCollapseButton"] span,
            [data-testid="stSidebarCollapseButton"] i,
            button[data-testid="baseButton-headerNoPadding"] span {{
                font-family: 'Material Symbols Outlined', 'Material Icons' !important;
                font-weight: normal !important;
                font-style: normal !important;
                font-size: 1.25rem !important;
                line-height: 1 !important;
                letter-spacing: normal !important;
                text-transform: none !important;
                display: inline-block !important;
                white-space: nowrap !important;
                word-wrap: normal !important;
                direction: ltr !important;
                -webkit-font-smoothing: antialiased !important;
            }}
            button[kind="icon"] svg {{
                font-size: 1rem !important;
                line-height: 1rem !important;
            }}
            .material-icons svg,
            .material-icons-outlined svg {{
                font-size: 1.25rem;
                width: 100%;
                height: 100%;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    render_floating_background()


def render_floating_background() -> None:
    st.markdown(
        """
        <div class="aegis-float-layer" aria-hidden="true">
            <span class="aegis-orb aegis-orb-1"></span>
            <span class="aegis-orb aegis-orb-2"></span>
            <span class="aegis-orb aegis-orb-3"></span>
            <span class="aegis-orb aegis-orb-4"></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_assistant_overlay(*, symbol: str, horizon: str, timeframe: str) -> None:
    if not st.session_state.get("assistant_open", True):
        return

    st.session_state.setdefault("assistant_chat_history", [
        {"role": "assistant", "text": "Hello! I can help you review strategy ideas, plan future trades, and log buy/sell/hold records."}
    ])
    st.session_state.setdefault("strategy_ideas", [])
    st.session_state.setdefault("trade_plans", [])
    st.session_state.setdefault("trade_records", [])
    st.session_state.setdefault("assistant_view", "home")

    st.markdown(
        """
        <div class="aegis-assistant-panel" style="
            border: 1px solid rgba(99, 179, 237, 0.22);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            margin: 1rem 0 1.25rem;
            background: linear-gradient(180deg, rgba(10, 16, 30, 0.96) 0%, rgba(6, 10, 20, 0.96) 100%);
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.22);
        ">
        """,
        unsafe_allow_html=True,
    )

    st.markdown(f"### Aegis Assistant · {symbol}")
    st.caption("Choose a workflow to plan, record, or chat about the current setup.")

    option_keys = [
        ("Strategy planning", "strategy"),
        ("Record trade", "trade"),
        ("Personalized chat", "chat"),
    ]
    cols = st.columns(3)
    current_view = st.session_state.get("assistant_view", "home")
    for col, (label, key) in zip(cols, option_keys, strict=False):
        button_type = "primary" if current_view == key else "secondary"
        if col.button(label, use_container_width=True, type=button_type):
            st.session_state["assistant_view"] = key
            st.rerun()

    st.divider()

    if current_view == "strategy":
        st.markdown("#### Strategy planning")
        st.caption("Capture a plan for this symbol, horizon, and market context.")
        with st.form("assistant_strategy_form"):
            strategy = st.text_area(
                "Strategy note",
                key="assistant_strategy_note",
                height=90,
                placeholder="Example: Focus on pullbacks with confirmation from the moving averages.",
            )
            if st.form_submit_button("Save strategy", use_container_width=True):
                if strategy.strip():
                    st.session_state.strategy_ideas.append({"text": strategy.strip(), "symbol": symbol, "horizon": horizon})
                    st.success("Strategy saved.")
                    st.rerun()
        if st.session_state.strategy_ideas:
            st.markdown("**Recent strategies**")
            for idea in reversed(st.session_state.strategy_ideas[-3:]):
                st.caption(f"• {idea['text']}")

    elif current_view == "trade":
        st.markdown("#### Record trade")
        st.caption("Log a buy, sell, or hold decision for later review.")
        with st.form("assistant_trade_form"):
            side = st.selectbox("Action", ["Buy", "Sell", "Hold"], key="assistant_trade_side")
            price = st.text_input("Price", key="assistant_trade_price", placeholder="1345.00")
            quantity = st.text_input("Quantity", key="assistant_trade_quantity", placeholder="100")
            note = st.text_input("Note", key="assistant_trade_note", placeholder="Reason or target")
            if st.form_submit_button("Save record", use_container_width=True):
                if price.strip() and note.strip():
                    st.session_state.trade_records.append(
                        {
                            "type": side,
                            "price": price.strip(),
                            "quantity": quantity.strip() or "—",
                            "note": note.strip(),
                            "symbol": symbol,
                        }
                    )
                    st.success("Trade record saved.")
                    st.rerun()
        if st.session_state.trade_records:
            st.markdown("**Recent records**")
            for rec in reversed(st.session_state.trade_records[-4:]):
                st.caption(f"• {rec['type']} {rec['symbol']} @ {rec['price']} · {rec['quantity']} — {rec['note']}")

    elif current_view == "chat":
        st.markdown("#### Personalized chat")
        st.caption("Ask for guidance tailored to the current symbol and horizon.")
        with st.form("assistant_chat_form"):
            msg_input = st.text_input(
                "Your message",
                key="assistant_chat_msg",
                placeholder="Try: Should I be more cautious on this setup?",
            )
            if st.form_submit_button("Send", use_container_width=True):
                if msg_input.strip():
                    st.session_state.assistant_chat_history.append({"role": "user", "text": msg_input.strip()})
                    lower = msg_input.strip().lower()
                    if any(word in lower for word in ("buy", "sell", "hold", "trade")):
                        reply = (
                            f"For {symbol} on {horizon_label(horizon)}, I’d frame the decision around the current forecast, "
                            "your risk limit, and the latest price structure before taking action."
                        )
                    elif any(word in lower for word in ("strategy", "plan", "goal")):
                        reply = f"Your strategy should stay aligned with {symbol} and the {horizon_label(horizon)} horizon while keeping downside risk controlled."
                    else:
                        reply = (
                            f"I’m tailoring this to {symbol} · {horizon_label(horizon)} · {timeframe}. "
                            "I can help you review the signal, plan next steps, or record the trade decision."
                        )
                    st.session_state.assistant_chat_history.append({"role": "assistant", "text": reply})
                    st.rerun()
        if st.session_state.get("assistant_chat_history"):
            st.markdown("**Recent chat**")
            for item in st.session_state.assistant_chat_history[-6:]:
                role = item.get("role", "assistant")
                label = "You" if role == "user" else "Assistant"
                st.markdown(f"**{label}:** {item.get('text', '')}")

    else:
        st.markdown("#### Quick launch")
        st.caption("Pick one path to get started.")
        st.info("Use Strategy planning to frame your setup, Record trade to log a buy/sell/hold decision, or Personal chat for fast guidance.")

    st.markdown("</div>", unsafe_allow_html=True)


def render_topbar(
    *,
    title: str,
    subtitle: str,
    symbol: str,
    horizon: str,
    api_online: bool,
) -> None:
    status_class = "aegis-badge-live" if api_online else "aegis-badge-offline"
    status_text = "API connected" if api_online else "API offline"
    st.markdown(
        f"""
        <div class="aegis-topbar">
            <div>
                <h1 class="aegis-topbar-title">{title}</h1>
                <p class="aegis-topbar-sub">{subtitle}</p>
            </div>
            <div class="aegis-topbar-meta">
                <span class="aegis-badge">{symbol}</span>
                <span class="aegis-badge">{horizon_label(horizon)}</span>
                <span class="aegis-badge {status_class}">{status_text}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login_brand() -> None:
    st.markdown(
        f"""
        <div class="aegis-login-brand aegis-float">
            <span class="aegis-badge aegis-badge-live">Analytics platform</span>
            <h1>Aegis Analytics</h1>
            <p>ML forecasts, risk bands, and market dashboards</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(title: str, detail: str) -> None:
    st.markdown(
        f"""
        <div class="aegis-empty">
            <div class="aegis-empty-title">{title}</div>
            <p style="margin:0;font-size:0.88rem;">{detail}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_advice_panel(label: str, reason: str) -> None:
    css_class = "aegis-advice-hold"
    color = COLORS["warning"]
    if label == "Buy":
        css_class = "aegis-advice-buy"
        color = COLORS["success"]
    elif label == "Sell / Reduce":
        css_class = "aegis-advice-sell"
        color = COLORS["danger"]

    st.markdown(
        f"""
        <div class="aegis-panel {css_class}">
            <div class="aegis-advice-title" style="color:{color}">{label}</div>
            <p style="margin:0;color:{COLORS['muted']};font-size:0.9rem;line-height:1.5;">{reason}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _value_color(value: float, *, positive_good: bool = True) -> str:
    if value > 0:
        return COLORS["success"] if positive_good else COLORS["danger"]
    if value < 0:
        return COLORS["danger"] if positive_good else COLORS["success"]
    return COLORS["muted"]


def render_prediction_metrics(
    *,
    expected_return: float,
    expected_price: float,
    p_up: float | None,
    downside_risk: float,
) -> None:
    ret_color = _value_color(expected_return)
    conf_text = "N/A" if p_up is None else f"{p_up * 100:.1f}%"
    conf_color = COLORS["muted"] if p_up is None else _value_color(float(p_up) - 0.5)
    risk_color = (
        COLORS["danger"]
        if downside_risk >= 0.35
        else COLORS["warning"]
        if downside_risk >= 0.2
        else COLORS["success"]
    )

    st.markdown(
        f"""
        <div class="aegis-pred-grid">
            <div class="aegis-pred-card">
                <div class="aegis-pred-label">Expected return</div>
                <div class="aegis-pred-value aegis-mono" style="color:{ret_color}">{expected_return * 100:+.3f}%</div>
            </div>
            <div class="aegis-pred-card">
                <div class="aegis-pred-label">Expected price</div>
                <div class="aegis-pred-value aegis-mono" style="color:{COLORS['accent']}">${expected_price:,.2f}</div>
            </div>
            <div class="aegis-pred-card">
                <div class="aegis-pred-label">P(up)</div>
                <div class="aegis-pred-value aegis-mono" style="color:{conf_color}">{conf_text}</div>
            </div>
            <div class="aegis-pred-card">
                <div class="aegis-pred-label">Downside (&lt; −2%)</div>
                <div class="aegis-pred-value aegis-mono" style="color:{risk_color}">{downside_risk * 100:.1f}%</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_forecast_summary_compact(
    *,
    symbol: str,
    horizon: str,
    timeframe: str,
    last_close: float,
    expected_return: float,
    expected_price: float,
    interval_low: float,
    interval_high: float,
    p_up: float | None,
    model_version: str | None,
    model_trained_at: str | None = None,
) -> None:
    low_price = last_close * (1.0 + interval_low)
    high_price = last_close * (1.0 + interval_high)
    conf = "—" if p_up is None else f"{p_up * 100:.1f}%"
    conf_color = COLORS["muted"] if p_up is None else _value_color(float(p_up) - 0.5)
    ret_color = _value_color(expected_return)
    trained = str(model_trained_at)[:19].replace("T", " ") if model_trained_at else "—"

    def row(label: str, value: str, color: str) -> str:
        return (
            f'<div class="aegis-compact-row">'
            f'<span class="aegis-pred-label">{label}</span>'
            f'<span class="aegis-compact-value" style="color:{color}">{value}</span>'
            f"</div>"
        )

    rows = [
        row("Last close", f"${last_close:,.2f}", COLORS["text"]),
        row("Target price", f"${expected_price:,.2f}", COLORS["magenta"]),
        row("Expected return", f"{expected_return * 100:+.3f}%", ret_color),
        row("P(up)", conf, conf_color),
        row("Return band", f"{interval_low * 100:+.2f}% to {interval_high * 100:+.2f}%", COLORS["violet"]),
        row("Price band", f"${low_price:,.2f} – ${high_price:,.2f}", COLORS["violet"]),
    ]

    st.markdown(
        f"""
        <div class="aegis-panel aegis-forecast-compact">
            <div class="aegis-pred-label" style="margin-bottom:0.5rem;">
                {symbol} · {horizon_label(horizon)} · {timeframe}
            </div>
            {"".join(rows)}
            <p style="margin:0.6rem 0 0;font-family:'IBM Plex Mono',monospace;font-size:0.68rem;color:{COLORS['muted']};">
                Model {model_version or '—'} · trained {trained}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_forecast_telemetry(
    *,
    symbol: str,
    horizon: str,
    timeframe: str,
    last_close: float,
    expected_return: float,
    expected_price: float,
    interval_low: float,
    interval_high: float,
    p_up: float | None,
    model_version: str | None,
) -> None:
    low_price = last_close * (1.0 + interval_low)
    high_price = last_close * (1.0 + interval_high)
    conf = "—" if p_up is None else f"{p_up * 100:.1f}%"

    st.markdown(
        f"""
        <div class="aegis-panel">
            <div class="aegis-pred-label" style="margin-bottom:0.65rem;">
                Forecast · {symbol} · {horizon_label(horizon)}
            </div>
            <div class="aegis-telemetry-strip">
                <div>
                    <div class="aegis-pred-label">Last close</div>
                    <div class="aegis-pred-value-lg aegis-mono" style="color:{COLORS['text']}">${last_close:,.2f}</div>
                </div>
                <div>
                    <div class="aegis-pred-label">Target price</div>
                    <div class="aegis-pred-value-lg aegis-mono" style="color:{COLORS['magenta']}">${expected_price:,.2f}</div>
                </div>
                <div>
                    <div class="aegis-pred-label">P(up)</div>
                    <div class="aegis-pred-value-lg aegis-mono" style="color:{COLORS['accent']}">{conf}</div>
                </div>
            </div>
            <div class="aegis-telemetry-strip">
                <div>
                    <div class="aegis-pred-label">Return forecast</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{_value_color(expected_return)}">{expected_return * 100:+.4f}%</div>
                </div>
                <div>
                    <div class="aegis-pred-label">Return interval</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['violet']}">
                        {interval_low * 100:+.3f}% to {interval_high * 100:+.3f}%
                    </div>
                </div>
                <div>
                    <div class="aegis-pred-label">Price band</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['violet']};font-size:1rem;">
                        ${low_price:,.2f} – ${high_price:,.2f}
                    </div>
                </div>
            </div>
            <p style="margin:0.4rem 0 0;font-family:'IBM Plex Mono',monospace;font-size:0.72rem;color:{COLORS['muted']};">
                {model_version or '—'} · {timeframe} · {horizon_label(horizon)}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_raw_data_summary(df: pd.DataFrame, *, symbol: str, timeframe: str) -> None:
    if df.empty:
        render_empty_state("No market data", f"No bars loaded for {symbol} ({timeframe}).")
        return

    last = df.iloc[-1]
    last_close = float(last.get("close", 0))
    period_high = float(df["high"].max()) if "high" in df.columns else last_close
    period_low = float(df["low"].min()) if "low" in df.columns else last_close
    bar_count = len(df)
    vol = last.get("volume")
    vol_txt = "—" if vol is None or (isinstance(vol, float) and pd.isna(vol)) else f"{int(vol):,}"

    st.markdown(
        f"""
        <div class="aegis-panel">
            <div class="aegis-pred-label" style="margin-bottom:0.65rem;">Market feed · {symbol} · {timeframe}</div>
            <div class="aegis-pred-grid">
                <div class="aegis-pred-card">
                    <div class="aegis-pred-label">Bars</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['accent']}">{bar_count:,}</div>
                </div>
                <div class="aegis-pred-card">
                    <div class="aegis-pred-label">Last close</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['text']}">${last_close:,.2f}</div>
                </div>
                <div class="aegis-pred-card">
                    <div class="aegis-pred-label">Period high</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['success']}">${period_high:,.2f}</div>
                </div>
                <div class="aegis-pred-card">
                    <div class="aegis-pred-label">Period low</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['danger']}">${period_low:,.2f}</div>
                </div>
            </div>
            <p style="margin:0;font-family:'IBM Plex Mono',monospace;font-size:0.72rem;color:{COLORS['muted']};">
                Last volume {vol_txt} · range ${period_low:,.2f} – ${period_high:,.2f}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_raw_data_table(df: pd.DataFrame, *, limit: int = 100) -> None:
    if df.empty:
        render_empty_state("No rows", "Load price data from the API to populate this table.")
        return

    view = df.tail(limit).copy()
    if "ts_utc" in view.columns:
        view["ts_utc"] = pd.to_datetime(view["ts_utc"]).dt.strftime("%Y-%m-%d %H:%M")

    col_defs: list[tuple[str, str, str | None]] = [
        ("ts_utc", "Time", COLORS["muted"]),
        ("open", "Open", COLORS["text"]),
        ("high", "High", COLORS["success"]),
        ("low", "Low", COLORS["danger"]),
        ("close", "Close", COLORS["accent"]),
        ("volume", "Volume", COLORS["violet"]),
    ]
    optional = [
        ("ma_fast", "MA fast", COLORS["magenta"]),
        ("ma_slow", "MA slow", COLORS["violet"]),
        ("ret_1", "Ret 1", None),
        ("ret_5", "Ret 5", None),
    ]
    for col, label, _ in optional:
        if col in view.columns:
            col_defs.append((col, label, _))

    headers = "".join(f"<th>{label}</th>" for _, label, _ in col_defs)
    body: list[str] = []
    for _, row in view.iterrows():
        cells = []
        for col, _, default_color in col_defs:
            val = row.get(col)
            if val is None or (isinstance(val, float) and pd.isna(val)):
                txt, color = "—", COLORS["muted"]
            elif col == "ts_utc":
                txt, color = str(val), COLORS["muted"]
            elif col in {"ret_1", "ret_5"}:
                fval = float(val)
                txt, color = f"{fval * 100:+.3f}%", _value_color(fval)
            elif col == "volume":
                txt, color = f"{int(val):,}", default_color or COLORS["violet"]
            elif col in {"open", "high", "low", "close", "ma_fast", "ma_slow"}:
                txt, color = f"{float(val):,.4f}", default_color or COLORS["text"]
            else:
                txt, color = str(val), default_color or COLORS["text"]
            cells.append(f"<td style='color:{color}'>{txt}</td>")
        body.append(f"<tr>{''.join(cells)}</tr>")

    st.markdown(
        f"""
        <div class="aegis-panel" style="padding:0.75rem 1rem;overflow-x:auto;">
            <div class="aegis-pred-label" style="margin-bottom:0.55rem;">
                OHLCV · {len(view)} of {len(df)} rows
            </div>
            <table class="aegis-pred-table">
                <thead><tr>{headers}</tr></thead>
                <tbody>{"".join(body)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_prediction_history_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        render_empty_state("No history yet", "Predictions are logged when you load a symbol and horizon.")
        return

    body = []
    for row in rows:
        exp_ret = float(row.get("expected_return", 0))
        exp_price = float(row.get("expected_price", 0))
        p_up = row.get("p_up")
        p_up_txt = "—" if p_up is None else f"{float(p_up) * 100:.1f}%"
        ret_color = _value_color(exp_ret)
        created = str(row.get("created_at", ""))[:19].replace("T", " ")
        body.append(
            f"<tr>"
            f"<td>{row.get('symbol', '')}</td>"
            f"<td>{horizon_label(str(row.get('horizon', '')))}</td>"
            f"<td style='color:{ret_color}'>{exp_ret * 100:+.3f}%</td>"
            f"<td style='color:{COLORS['accent']}'>${exp_price:,.2f}</td>"
            f"<td style='color:{COLORS['violet']}'>{p_up_txt}</td>"
            f"<td style='color:{COLORS['muted']};font-size:0.75rem;'>{created}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""
        <table class="aegis-pred-table">
            <thead>
                <tr>
                    <th>Symbol</th>
                    <th>Horizon</th>
                    <th>Return</th>
                    <th>Price</th>
                    <th>P(up)</th>
                    <th>When</th>
                </tr>
            </thead>
            <tbody>{"".join(body)}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def render_profile_panel(
    *,
    username: str,
    favorite_symbol: str | None,
    favorite_horizon: str | None,
    watchlist: list[str],
    current_symbol: str,
    current_horizon: str,
) -> None:
    if watchlist:
        watchlist_html = "".join(
            f'<span class="aegis-chip" style="margin:0.2rem 0.3rem 0.2rem 0;">{s}</span>' for s in watchlist
        )
    else:
        watchlist_html = f'<span style="color:{COLORS["muted"]};font-size:0.85rem;">Add symbols in the sidebar</span>'

    st.markdown(
        f"""
        <div class="aegis-panel">
            <div class="aegis-pred-label">Account</div>
            <p style="margin:0.35rem 0 0.85rem;font-size:1rem;font-weight:600;color:{COLORS['text']};">{username}</p>
            <div class="aegis-pred-label">Saved defaults</div>
            <p style="margin:0.25rem 0 0.65rem;color:{COLORS['muted']};font-size:0.88rem;">
                {favorite_symbol or current_symbol} · {horizon_label(favorite_horizon or current_horizon)}
            </p>
            <div class="aegis-pred-label">Watchlist</div>
            <div style="margin-top:0.4rem;display:flex;flex-wrap:wrap;gap:0.35rem;">{watchlist_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_market_stats_strip(
    *,
    period_return: float,
    volatility: float,
    avg_volume: float | None,
    bar_count: int,
) -> None:
    ret_color = _value_color(period_return)
    vol_color = COLORS["warning"] if volatility >= 0.015 else COLORS["success"] if volatility <= 0.008 else COLORS["muted"]
    vol_txt = f"{volatility * 100:.2f}%" if volatility == volatility else "—"
    avg_vol_txt = "—" if avg_volume is None else f"{int(avg_volume):,}"

    st.markdown(
        f"""
        <div class="aegis-pred-grid">
            <div class="aegis-pred-card">
                <div class="aegis-pred-label">Period return</div>
                <div class="aegis-pred-value aegis-mono" style="color:{ret_color}">{period_return * 100:+.2f}%</div>
            </div>
            <div class="aegis-pred-card">
                <div class="aegis-pred-label">Volatility (1-bar)</div>
                <div class="aegis-pred-value aegis-mono" style="color:{vol_color}">{vol_txt}</div>
            </div>
            <div class="aegis-pred-card">
                <div class="aegis-pred-label">Avg volume</div>
                <div class="aegis-pred-value aegis-mono" style="color:{COLORS['violet']}">{avg_vol_txt}</div>
            </div>
            <div class="aegis-pred-card">
                <div class="aegis-pred-label">Bars loaded</div>
                <div class="aegis-pred-value aegis-mono" style="color:{COLORS['accent']}">{bar_count:,}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_horizon_comparison_table(rows: list[dict[str, Any]], *, current_horizon: str) -> None:
    if not rows:
        render_empty_state("No horizon data", "Predictions across horizons will appear once the API responds.")
        return

    body = []
    for row in rows:
        horizon = str(row.get("horizon", ""))
        exp_ret = float(row.get("expected_return", 0))
        p_up = row.get("p_up")
        p_up_txt = "—" if p_up is None else f"{float(p_up) * 100:.1f}%"
        active = " · active" if horizon == current_horizon else ""
        body.append(
            f"<tr>"
            f"<td>{horizon_label(horizon)}{active}</td>"
            f"<td style='color:{_value_color(exp_ret)}'>{exp_ret * 100:+.3f}%</td>"
            f"<td style='color:{COLORS['accent']}'>${float(row.get('expected_price', 0)):,.2f}</td>"
            f"<td style='color:{COLORS['violet']}'>{p_up_txt}</td>"
            f"<td style='color:{COLORS['muted']}'>{float(row.get('interval_low', 0)) * 100:+.2f}% to {float(row.get('interval_high', 0)) * 100:+.2f}%</td>"
            f"</tr>"
        )

    st.markdown(
        f"""
        <div class="aegis-panel" style="padding:0.75rem 1rem;overflow-x:auto;">
            <div class="aegis-pred-label" style="margin-bottom:0.55rem;">Horizon comparison</div>
            <table class="aegis-pred-table">
                <thead>
                    <tr>
                        <th>Horizon</th>
                        <th>Return</th>
                        <th>Target</th>
                        <th>P(up)</th>
                        <th>Band</th>
                    </tr>
                </thead>
                <tbody>{"".join(body)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_watchlist_snapshot(rows: list[dict[str, Any]], *, current_symbol: str, horizon: str) -> None:
    if not rows:
        render_empty_state("Watchlist empty", "Add symbols in the sidebar to compare forecasts here.")
        return

    body = []
    for row in rows:
        sym = str(row.get("symbol", ""))
        exp_ret = float(row.get("expected_return", 0))
        p_up = row.get("p_up")
        advice = str(row.get("advice", "Hold"))
        advice_color = COLORS["success"] if advice == "Buy" else COLORS["danger"] if "Sell" in advice else COLORS["warning"]
        active = " · selected" if sym == current_symbol else ""
        body.append(
            f"<tr>"
            f"<td><strong>{sym}</strong>{active}</td>"
            f"<td style='color:{_value_color(exp_ret)};font-weight:600;'>{exp_ret * 100:+.3f}%</td>"
            f"<td style='color:{COLORS['accent']};font-weight:600;'>${float(row.get('expected_price', 0)):,.2f}</td>"
            f"<td style='color:{COLORS['violet']};font-weight:600;'>{'—' if p_up is None else f'{float(p_up) * 100:.1f}%'}</td>"
            f"<td style='color:{advice_color};font-weight:600;'>{advice}</td>"
            f"</tr>"
        )

    st.markdown(
        f"""
        <div class="aegis-panel" style="padding:0.75rem 1rem;overflow-x:auto;">
            <div class="aegis-pred-label" style="margin-bottom:0.55rem;">Watchlist · {horizon_label(horizon)}</div>
            <table class="aegis-pred-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Return</th>
                        <th>Target</th>
                        <th>P(up)</th>
                        <th>Signal</th>
                    </tr>
                </thead>
                <tbody>{"".join(body)}</tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_risk_summary_panel(
    *,
    last_close: float,
    expected_return: float,
    expected_price: float,
    interval_low: float,
    interval_high: float,
    p_down_1: float,
    p_down_2: float,
    p_up: float | None,
) -> None:
    band_width = interval_high - interval_low
    low_price = last_close * (1.0 + interval_low)
    high_price = last_close * (1.0 + interval_high)
    conf = "—" if p_up is None else f"{float(p_up) * 100:.1f}%"

    st.markdown(
        f"""
        <div class="aegis-panel">
            <div class="aegis-pred-label" style="margin-bottom:0.65rem;">Risk summary</div>
            <div class="aegis-telemetry-strip">
                <div>
                    <div class="aegis-pred-label">Expected move</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{_value_color(expected_return)}">{expected_return * 100:+.3f}%</div>
                </div>
                <div>
                    <div class="aegis-pred-label">Band width</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['violet']}">{band_width * 100:.2f}%</div>
                </div>
                <div>
                    <div class="aegis-pred-label">Direction confidence</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['accent']}">{conf}</div>
                </div>
            </div>
            <div class="aegis-telemetry-strip">
                <div>
                    <div class="aegis-pred-label">Price band</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['violet']};font-size:1rem;">
                        ${low_price:,.2f} – ${high_price:,.2f}
                    </div>
                </div>
                <div>
                    <div class="aegis-pred-label">Target price</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['magenta']}">${expected_price:,.2f}</div>
                </div>
                <div>
                    <div class="aegis-pred-label">Tail risk</div>
                    <div class="aegis-pred-value aegis-mono" style="color:{COLORS['danger']}">
                        {p_down_1 * 100:.1f}% / {p_down_2 * 100:.1f}%
                    </div>
                </div>
            </div>
            <p style="margin:0.35rem 0 0;font-size:0.82rem;color:{COLORS['muted']};">
                Tail risk shows P(return &lt; −1%) / P(return &lt; −2%) from the conformal interval.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_footer(*, symbol_count: int, api_base: str) -> None:
    st.markdown(
        f"""
        <div class="aegis-panel" style="padding:0.75rem 0.9rem;margin-top:0.5rem;">
            <div class="aegis-pred-label">System</div>
            <p style="margin:0.35rem 0 0.5rem;font-size:0.82rem;color:{COLORS['muted']};">
                {symbol_count} trained symbol{"s" if symbol_count != 1 else ""} · API online
            </p>
            <span class="aegis-chip">{api_base}</span>
            <span class="aegis-chip">/docs</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def apply_plotly_theme(fig, *, height: int | None = None, title: str | None = None):
    layout = dict(PLOTLY_TEMPLATE)
    if height is not None:
        layout["height"] = height
    if title:
        layout["title"] = {
            "text": title,
            "font": {"family": "IBM Plex Sans, sans-serif", "size": 13, "color": COLORS["text"]},
            "x": 0,
            "xanchor": "left",
        }
    fig.update_layout(**layout)
    fig.update_xaxes(showgrid=True, gridwidth=1)
    fig.update_yaxes(showgrid=True, gridwidth=1)
    return fig
