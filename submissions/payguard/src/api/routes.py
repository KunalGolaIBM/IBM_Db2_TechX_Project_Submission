"""FastAPI transport routes. Sync handlers run in Starlette's worker thread pool."""
from pathlib import Path
from typing import Literal, cast
import logging
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool
from services.container import Services, get_services
from services.screening import screen_payment
from services.analyst import QUICK_QUESTIONS
from domain.models import ScreenRequest
from adapters import gemini as llm, vision
from services.checkout import Checkout, CheckoutRejected
from config import settings
from api.models import (ScreenIn, PurchaseIn, ReportIn, QuestionIn, OrderIn, CaptureIn, PlatformCheckIn, DemoCheckIn, Method)
from api.security import require_platform_key
from observability import runtime
from services.health import deep_health

router = APIRouter()
log = logging.getLogger("payguard.api")
STATIC = Path(__file__).resolve().parent.parent / "static"
DEMO_LISTINGS = json.loads((STATIC.parent.parent / "data" / "demo_listings.json").read_text(encoding="utf-8"))


def _screen(s: Services, data: ScreenIn, extra: dict | None = None) -> dict:
    req = ScreenRequest(data.merchant, data.payee_email.strip(), data.amount, data.currency,
                        data.payment_method, data.message, data.region,
                        data.seller_account_age_days, data.market_price)
    return screen_payment(s, req, data.language, data.explain, data.source, extra)


# ------------------------------------------------------------------------------- routes
@router.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@router.get("/market", include_in_schema=False)
def market():
    return FileResponse(STATIC / "market.html")


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@router.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(STATIC / "sw.js", media_type="text/javascript")


@router.get("/api/health")
def health(s: Services = Depends(get_services)):
    return deep_health(s)


@router.get("/api/config")
def config():
    return {"paypal_client_id": settings.paypal_client_id if settings.paypal_enabled else "",
            "currency": settings.paypal_currency, "llm": settings.llm_enabled,
            "thresholds": {"review": settings.review_threshold, "block": settings.block_threshold}}


@router.post("/api/screen")
def screen(data: ScreenIn, s: Services = Depends(get_services)):
    return _screen(s, data)


@router.post("/api/screen-image")
async def screen_image(file: UploadFile = File(...), language: Literal["en", "pcm"] = Form("en"),
                       s: Services = Depends(get_services)):
    """One-tap check: a screenshot of the chat/listing -> Gemini vision -> PayGuard screening."""
    return await run_in_threadpool(_screen_image, s, await file.read(vision.MAX_BYTES + 1), file.content_type or "", language, "screenshot")


def _screen_image(s: Services, data: bytes, mime: str, language: Literal["en", "pcm"], source: Literal["screenshot", "share"]) -> dict:
    try:
        ex = vision.read_screenshot(data, mime)
    except vision.ImageError as exc:
        raise HTTPException(422, str(exc))
    except llm.LLMUnavailable:
        raise HTTPException(503, "Reading screenshots needs the AI (GEMINI_API_KEY). Paste the text instead.")
    except Exception as exc:  # network down, Gemini timeout, etc.
        log.warning("screenshot read failed: %s", exc)
        raise HTTPException(503, "Couldn't reach the AI to read the screenshot. Check your internet and try again, or paste the text.")
    message = vision.to_message(ex)
    if not message:
        raise HTTPException(422, "I couldn't read any messages in that image. Try a clearer screenshot.")
    data_in = ScreenIn(merchant=(ex.get("seller_name") or "")[:200], amount=ex["amount"],
                       currency=ex["currency"] if len(ex["currency"]) == 3 else "USD",
                       payment_method=cast(Method, ex.get("payment_method")) if ex.get("payment_method") in
                       ("goods_services", "friends_family", "gift_card", "crypto", "wire") else "goods_services",
                       message=message[:4000], language=language, source=source)
    return _screen(s, data_in, {"screenshot": ex})


@router.post("/share", include_in_schema=False)
async def share_target(title: str = Form(""), text: str = Form(""), url: str = Form(""),
                       media: list[UploadFile] | None = File(None), s: Services = Depends(get_services)):
    """Android share sheet -> installed PayGuard web app. Screens what was shared, then shows the verdict."""
    try:
        if media:
            f = media[0]
            result = await run_in_threadpool(_screen_image, s, await f.read(vision.MAX_BYTES + 1), f.content_type or "", "en", "share")
        else:
            message = "\n".join(x for x in (title, text, url) if x).strip()
            if not message:
                return RedirectResponse("/?error=empty", status_code=303)
            result = await run_in_threadpool(_screen, s, ScreenIn(message=message[:4000], source="share"))
    except HTTPException as exc:
        from urllib.parse import quote

        return RedirectResponse(f"/?error={quote(str(exc.detail))}", status_code=303)
    return RedirectResponse(f"/?r={result['screening_id']}", status_code=303)


@router.get("/api/results/{screening_id}")
def get_result(screening_id: int, s: Services = Depends(get_services)):
    result = s.result(screening_id)
    if result is not None:
        return result
    raise HTTPException(404, "Result expired - please check again.")


# --- Platform API: marketplaces send the chat + seller signals at "Pay" time; the buyer pastes nothing ---
@router.post("/api/v1/checkout/verify", dependencies=[Depends(require_platform_key)])
@router.post("/api/checkout/verify", dependencies=[Depends(require_platform_key)], include_in_schema=False)
def platform_verify(data: PlatformCheckIn, s: Services = Depends(get_services)):
    transcript = "\n".join(f"{c.sender.title()}: {c.text}" for c in data.chat)
    contacts = " ".join(x for x in (data.seller_phone, data.seller_account_number) if x)
    message = f"Listing: {data.listing_title}\n{transcript}\n{contacts}".strip()
    result = _screen(s, ScreenIn(merchant=data.seller_name, payee_email=data.seller_email, amount=data.amount,
                                 currency=data.currency.upper(), payment_method=data.payment_method,
                                 message=message[:4000], language=data.language, source="platform",
                                 seller_account_age_days=data.seller_account_age_days,
                                 market_price=data.market_price))
    return {"screening_id": result["screening_id"], "verdict": result["verdict"], "risk_score": result["risk_score"],
            "allow_payment": result["verdict"] != "BLOCK" and result["screening_id"] is not None,
            "require_confirmation": result["verdict"] == "REVIEW" or result["degraded"],
            "degraded": result["degraded"],
            "headline": result["plain"]["headline"], "reasons": result["plain"]["reasons"],
            "summary": result["plain"]["subline"], "paypal_allowed": result["paypal_allowed"]}


@router.post("/api/agent/purchase")
def agent_purchase(data: PurchaseIn, s: Services = Depends(get_services)):
    """Agentic commerce: sentence -> structured order -> PayGuard screening -> (if allowed) PayPal checkout."""
    intent = s.investigator.parse_purchase(data.instruction)
    method = intent.get("payment_method") or "goods_services"
    if method not in ("goods_services", "friends_family", "gift_card", "crypto", "wire"):
        method = "goods_services"
    screen_in = ScreenIn(
        merchant=str(intent.get("merchant") or "")[:200], payee_email=str(intent.get("payee_email") or "")[:320],
        amount=max(0.0, float(intent.get("amount") or 0)), currency=str(intent.get("currency") or "USD")[:3],
        payment_method=cast(Method, method),
        message=(str(intent.get("seller_message") or "") + "\n" + data.instruction)[:4000],
        language=data.language, source="agent",
    )
    return {"intent": intent, "screening": _screen(s, screen_in)}


@router.post("/api/report")
def report(data: ReportIn, s: Services = Depends(get_services)):
    value = data.value.strip().lower()
    if data.entity_type == "email" and "@" not in value:
        raise HTTPException(422, "Enter a valid e-mail address.")
    vec = s.embedder.embed([data.narrative])[0]
    return s.repo.file_report(data.entity_type, value, data.reporter, data.category, data.amount,
                              data.currency.upper(), data.narrative, vec)


@router.post("/api/ask")
def ask(data: QuestionIn, s: Services = Depends(get_services)):
    return s.investigator.ask(data.question, s.analyst)


@router.get("/api/analyst/quick")
def analyst_quick():
    return list(QUICK_QUESTIONS)


@router.post("/api/analyst")
def analyst(data: QuestionIn, s: Services = Depends(get_services)):
    return s.analyst.answer(data.question)


@router.get("/api/stats")
def stats(s: Services = Depends(get_services)):
    return s.repo.stats()


@router.get("/api/screenings/recent")
def recent(s: Services = Depends(get_services)):
    return s.repo.recent_screenings(15)


@router.get("/api/screenings/{screening_id}")
def screening(screening_id: int, s: Services = Depends(get_services)):
    row = s.repo.get_screening(screening_id)
    if not row:
        raise HTTPException(404, "Screening not found")
    return row


# --- PayPal: the server re-checks the Db2 verdict; the browser cannot bypass PayGuard ---------
@router.post("/api/paypal/orders")
def create_order(data: OrderIn, s: Services = Depends(get_services)):
    try:
        return Checkout(s.repo, s.paypal).create_order(data.screening_id, data.acknowledge_risk)
    except CheckoutRejected as exc:
        raise HTTPException(exc.status, exc.detail) from exc


@router.post("/api/paypal/orders/{order_id}/capture")
def capture_order(order_id: str, data: CaptureIn, s: Services = Depends(get_services)):
    try:
        return Checkout(s.repo, s.paypal).capture_order(order_id, data.screening_id)
    except CheckoutRejected as exc:
        raise HTTPException(exc.status, exc.detail) from exc


@router.post("/api/demo/checkout/verify", include_in_schema=False)
def demo_verify(data: DemoCheckIn, s: Services = Depends(get_services)):
    if not settings.platform_demo_enabled:
        raise HTTPException(404, "Demo disabled")
    return platform_verify(PlatformCheckIn.model_validate(DEMO_LISTINGS[data.listing_id]), s)


@router.get("/api/metrics")
def metrics(s: Services = Depends(get_services)):
    return {**runtime.snapshot(), "cache": {
        "embeddings": s.embedder.cache.stats(), "entities": s.repo.entities.stats(),
        "patterns": s.repo.patterns.stats(),
    }}
