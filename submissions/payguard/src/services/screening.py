"""Payment screening orchestration, independent of HTTP request objects."""
from services.container import Services
from domain.models import ScreenRequest
from domain.signals import extract_amount
from services.presenter import present
from observability import runtime

PAYPAL_CURRENCIES = {"USD", "GBP", "EUR", "CAD", "AUD"}

def screen_payment(s: Services, req: ScreenRequest, language: str = "en", explain: bool = True, source: str = "paste", extra: dict | None = None) -> dict:
    amount, currency = req.amount, req.currency
    if not amount:
        amount, found_cur = extract_amount(req.message)
        currency = found_cur if amount else currency
        req.amount, req.currency = amount, currency
    result = s.engine.screen(req)
    if explain:
        ai = s.investigator.explain(req, result, language)
        extra_risk = max(0, min(20, int(ai.get("extra_risk") or 0)))
        if ai.get("escalate") and extra_risk:
            new_score = min(100, result.risk_score + extra_risk)
            result.risk_score, result.verdict = new_score, s.engine._verdict(new_score)
        result.ai = ai
        if ai.get("degraded"):
            result.degraded = True
            result.unavailable.append("gemini")
        if result.screening_id is not None:
            try:
                s.repo.update_screening_ai(result.screening_id, ai.get("summary", ""), result.risk_score, result.verdict)
            except Exception:
                result.degraded = True
                result.unavailable.append("persistence")
                # A stale saved verdict must never authorize checkout.
                result.screening_id = None
    out = result.as_dict()
    out.update(amount=amount, currency=currency, source=source, language=language)
    out["paypal_allowed"] = result.screening_id is not None and result.verdict != "BLOCK" and amount > 0 and currency in PAYPAL_CURRENCIES
    out["plain"] = present(out, language)
    if extra:
        out.update(extra)
    runtime.verdict(result.verdict)
    s.remember(out)
    return out


