"""Context-aware dashboard assistant (hybrid: Google Gemini 3.5 Flash + deterministic fallback)."""

from __future__ import annotations

from typing import Any

from dashboard.theme import horizon_label


def _pct(value: float, *, digits: int = 3) -> str:
    return f"{value * 100:+.{digits}f}%"


def build_market_context(
    *,
    symbol: str,
    horizon: str,
    timeframe: str,
    pred: dict[str, Any],
    risk: dict[str, Any],
    advice_label: str,
    advice_reason: str,
    horizon_rows: list[dict[str, Any]],
    period_return: float,
    volatility: float,
    strategy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "horizon": horizon,
        "horizon_label": horizon_label(horizon),
        "timeframe": timeframe,
        "last_close": float(pred["last_close"]),
        "expected_return": float(pred["expected_return"]),
        "expected_price": float(pred["expected_price"]),
        "p_up": pred.get("p_up"),
        "interval_low": float(pred["interval_low"]),
        "interval_high": float(pred["interval_high"]),
        "p_down_1": float(risk["p_return_below_minus_1pct"]),
        "p_down_2": float(risk["p_return_below_minus_2pct"]),
        "advice_label": advice_label,
        "advice_reason": advice_reason,
        "horizon_rows": horizon_rows,
        "period_return": period_return,
        "volatility": volatility,
        "strategy": strategy or {},
    }


def evaluate_strategy(context: dict[str, Any]) -> tuple[bool, list[str]]:
    strategy = context.get("strategy") or {}
    if not strategy.get("name"):
        return False, ["No saved strategy yet. Open the Strategy tab to define rules."]

    checks: list[str] = []
    passed = True

    min_return = float(strategy.get("min_return", 0.002))
    min_p_up = float(strategy.get("min_p_up", 0.55))
    max_downside = float(strategy.get("max_downside", 0.35))

    exp_ret = float(context["expected_return"])
    ok_ret = exp_ret >= min_return
    passed = passed and ok_ret
    checks.append(
        f"{'✓' if ok_ret else '✗'} Expected return {_pct(exp_ret)} ≥ {_pct(min_return)}"
    )

    p_up = context.get("p_up")
    if p_up is None:
        passed = False
        checks.append("✗ P(up) unavailable")
    else:
        ok_p = float(p_up) >= min_p_up
        passed = passed and ok_p
        checks.append(
            f"{'✓' if ok_p else '✗'} P(up) {float(p_up) * 100:.1f}% ≥ {min_p_up * 100:.1f}%"
        )

    p_down = float(context["p_down_2"])
    ok_risk = p_down <= max_downside
    passed = passed and ok_risk
    checks.append(
        f"{'✓' if ok_risk else '✗'} Downside P(<−2%) {p_down * 100:.1f}% ≤ {max_downside * 100:.1f}%"
    )

    return passed, checks


def answer_question(question: str, context: dict[str, Any], *, use_gemini: bool = True) -> str:
    q = question.lower().strip()
    if not q:
        return "Ask about the forecast, risk, horizons, strategy, or how to log a trade."

    # First attempt: Gemini AI reasoning
    if use_gemini:
        try:
            from backend.app.services.gemini_service import generate_gemini_analysis
            gemini_ans = generate_gemini_analysis(question, context)
            if gemini_ans:
                return gemini_ans
        except Exception:
            pass

    # Deterministic fallback rules
    sym = context.get("symbol", "ASSET")
    hz = context.get("horizon_label", context.get("horizon", "5m"))
    exp_ret = float(context.get("expected_return", 0.0))
    exp_price = float(context.get("expected_price", 0.0))
    last_close = float(context.get("last_close", 0.0))
    p_up = context.get("p_up")
    p_up_txt = "unavailable" if p_up is None else f"{float(p_up) * 100:.1f}%"
    advice = context.get("advice_label", "Hold")
    reason = context.get("advice_reason", "")

    if any(w in q for w in ("hello", "hi", "help", "what can you")):
        return (
            "I can explain the current ML forecast, compare horizons, review risk, "
            "check your strategy rules, and suggest when to log a buy/sell in the Trade Journal. "
            f"Right now you're viewing **{sym}** on a **{hz}** horizon."
        )

    if any(w in q for w in ("buy", "sell", "signal", "should i", "trade")):
        strat_ok, checks = evaluate_strategy(context)
        strat_block = ""
        if checks:
            strat_block = "\n\n**Strategy checklist:**\n" + "\n".join(f"- {c}" for c in checks)
            if context.get("strategy", {}).get("name"):
                verdict = "Strategy conditions are met." if strat_ok else "Strategy conditions are not fully met."
                strat_block += f"\n\n{verdict}"
        return (
            f"**Signal: {advice}**\n\n{reason}\n\n"
            f"Expected return {_pct(exp_ret)} → target **₹{exp_price:,.2f}** "
            f"(last close ₹{last_close:,.2f}). P(up) = {p_up_txt}."
            f"{strat_block}\n\n"
            "_Not financial advice — use the Trade Journal to record your decisions._"
        )

    if any(w in q for w in ("risk", "downside", "tail", "loss")):
        p1 = context.get("p_down_1", 0.0)
        p2 = context.get("p_down_2", 0.0)
        ilow = context.get("interval_low", 0.0)
        ihigh = context.get("interval_high", 0.0)
        return (
            f"**Risk for {sym} ({hz})**\n\n"
            f"- P(return < −1%): **{p1 * 100:.2f}%**\n"
            f"- P(return < −2%): **{p2 * 100:.2f}%**\n"
            f"- Return band: {_pct(ilow, digits=2)} to {_pct(ihigh, digits=2)}\n"
            f"- Price band: ₹{last_close * (1 + ilow):,.2f} – "
            f"₹{last_close * (1 + ihigh):,.2f}\n\n"
            "Higher tail probabilities mean more downside uncertainty over this horizon."
        )

    if any(w in q for w in ("horizon", "compare", "5m", "15m", "60m", "1d", "timeframe")):
        rows = context.get("horizon_rows") or []
        if not rows:
            return "Horizon comparison data is not loaded yet. Try refreshing the dashboard."
        lines = ["**Horizon comparison:**"]
        for row in rows:
            h = horizon_label(str(row.get("horizon", "")))
            r = float(row.get("expected_return", 0))
            p = row.get("p_up")
            p_txt = "—" if p is None else f"{float(p) * 100:.0f}%"
            marker = " ← active" if str(row.get("horizon")) == context.get("horizon") else ""
            lines.append(f"- **{h}**{marker}: return {_pct(r)}, P(up) {p_txt}")
        best = max(rows, key=lambda r: float(r.get("expected_return", 0)))
        lines.append(
            f"\nStrongest expected return right now: **{horizon_label(str(best.get('horizon', '')))}** "
            f"at {_pct(float(best.get('expected_return', 0)))}."
        )
        return "\n".join(lines)

    if any(w in q for w in ("forecast", "predict", "expected", "target", "price")):
        ilow = context.get("interval_low", 0.0)
        ihigh = context.get("interval_high", 0.0)
        return (
            f"**Forecast — {sym} ({hz})**\n\n"
            f"- Last close: **₹{last_close:,.2f}**\n"
            f"- Expected return: **{_pct(exp_ret)}**\n"
            f"- Target price: **₹{exp_price:,.2f}**\n"
            f"- P(up): **{p_up_txt}**\n"
            f"- Interval: {_pct(ilow, digits=2)} to {_pct(ihigh, digits=2)}\n\n"
            "Forecasts come from trained LightGBM models with conformal intervals and calibrated direction."
        )

    if any(w in q for w in ("strategy", "plan", "rule", "threshold")):
        strat_ok, checks = evaluate_strategy(context)
        if not context.get("strategy", {}).get("name"):
            return (
                "No strategy saved yet. Go to **Strategy** and set minimum return, P(up), "
                "and maximum downside thresholds, then save."
            )
        name = context["strategy"]["name"]
        status = "All rules pass — strategy aligned with current forecast." if strat_ok else "Some rules fail — proceed with caution."
        return f"**Strategy: {name}**\n\n" + "\n".join(f"- {c}" for c in checks) + f"\n\n{status}"

    if any(w in q for w in ("volatility", "volume", "period", "stats", "market")):
        pret = context.get("period_return", 0.0)
        vol = context.get("volatility", 0.0)
        tf = context.get("timeframe", "1m")
        return (
            f"**Market stats — {sym}**\n\n"
            f"- Period return (loaded window): **{_pct(pret, digits=2)}**\n"
            f"- 1-bar volatility (std): **{vol * 100:.2f}%**\n"
            f"- Timeframe: **{tf}**\n\n"
            "Use a longer history window in the sidebar for smoother volatility estimates."
        )

    if any(w in q for w in ("journal", "record", "log", "portfolio")):
        return (
            "Open the **Trade Journal** tab to log buys and sells with quantity, price, and notes. "
            "Records are stored per account and can be reviewed or deleted later."
        )

    return (
        f"For **{sym} ({hz})**, the current signal is **{advice}** "
        f"with expected return {_pct(exp_ret)}. Try asking:\n"
        "- Should I buy or sell?\n"
        "- Explain the risk\n"
        "- Compare horizons\n"
        "- Check my strategy"
    )
