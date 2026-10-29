from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import httpx

from backend.app.core.config import load_settings

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def generate_gemini_analysis(
    question: str,
    context: Dict[str, Any],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Generate financial analysis using Gemini 3.5 Flash with live model telemetry."""
    settings = load_settings()
    key = api_key or settings.gemini_api_key
    selected_model = model or settings.gemini_model or "gemini-3.5-flash"

    if not key:
        return ""

    symbol = context.get("symbol", "UNKNOWN")
    horizon = context.get("horizon", "5m")
    last_close = context.get("last_close")
    expected_return = context.get("expected_return")
    expected_price = context.get("expected_price")
    p_up = context.get("p_up")
    p_down_1 = context.get("p_down_1")
    p_down_2 = context.get("p_down_2")
    interval_low = context.get("interval_low")
    interval_high = context.get("interval_high")
    advice_label = context.get("advice_label", "Neutral")
    advice_reason = context.get("advice_reason", "")

    p_up_str = f"{float(p_up) * 100:.1f}%" if p_up is not None else "N/A"
    exp_ret_str = f"{float(expected_return) * 100:+.2f}%" if expected_return is not None else "N/A"
    exp_price_str = f"₹{float(expected_price):,.2f}" if expected_price is not None else "N/A"
    last_close_str = f"₹{float(last_close):,.2f}" if last_close is not None else "N/A"
    p_down_1_str = f"{float(p_down_1) * 100:.2f}%" if p_down_1 is not None else "N/A"
    p_down_2_str = f"{float(p_down_2) * 100:.2f}%" if p_down_2 is not None else "N/A"
    band_str = (
        f"{float(interval_low) * 100:+.2f}% to {float(interval_high) * 100:+.2f}%"
        if interval_low is not None and interval_high is not None
        else "N/A"
    )

    system_instruction = (
        "You are the Aegis AI Analyst, an institutional quantitative finance and risk intelligence assistant. "
        "You analyze market telemetry produced by Aegis Analytics AI, which combines LightGBM dual-head models "
        "(regression & classification), isotonic probability calibration (P_up), distribution-free conformal prediction bounds, "
        "and downside tail-risk estimation. Be concise, highly professional, analytical, and structured in Markdown. "
        "Always remind the user that forecasts are probabilistic and not financial advice."
    )

    prompt = f"""[MARKET TELEMETRY CONTEXT]
- Asset Symbol: {symbol}
- Forecast Horizon: {horizon}
- Last Close Price: {last_close_str}
- Model Expected Return: {exp_ret_str}
- Target Projected Price: {exp_price_str}
- Calibrated Directional Confidence P(Up): {p_up_str}
- 90% Conformal Prediction Interval: {band_str}
- Downside Tail Risk P(Return < -1%): {p_down_1_str}
- Severe Downside Tail Risk P(Return < -2%): {p_down_2_str}
- Derived Signal: {advice_label} ({advice_reason})

[USER QUESTION]
{question}

Provide a crisp, actionable quantitative response addressing the user's inquiry based on this telemetry."""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_instruction}\n\n{prompt}"}
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 800,
            "temperature": 0.3,
        },
    }

    url = f"{GEMINI_BASE_URL}/{selected_model}:generateContent?key={key}"

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
            else:
                logger.warning(
                    "Gemini API returned status %s: %s", resp.status_code, resp.text
                )
    except Exception as e:
        logger.error("Error invoking Gemini API: %s", e)

    return ""
