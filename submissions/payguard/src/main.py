"""PayGuard API + web UI (FastAPI).

Run:  uvicorn main:app --app-dir src --reload
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from agent import Investigator
from analyst import QUICK_QUESTIONS, Analyst
from config import settings
from embeddings import get_embedder
import llm
import vision
from paypal import PayPalClient, PayPalError
from presenter import present
from risk import RiskEngine, ScreenRequest
from signals import extract_amount

PAYPAL_CURRENCIES = {"USD", "GBP", "EUR", "CAD", "AUD"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("payguard")
STATIC = Path(__file__).resolve().parent / "static"

app = FastAPI(title="PayGuard", version="1.0.0",
              description="AI payment-fraud firewall on IBM Db2 with PayPal checkout")


class Services:
    def __init__(self, repo, embedder, paypal: PayPalClient):
        self.repo, self.embedder, self.paypal = repo, embedder, paypal
        self.engine = RiskEngine(repo, embedder)
        self.investigator = Investigator(repo, embedder, self.engine)
        self.analyst = Analyst(repo)
        self.results: OrderedDict[int, dict] = OrderedDict()  # recent full results for share-target redirects

    def remember(self, result: dict) -> None:
        self.results[result["screening_id"]] = result
        while len(self.results) > 300:
            self.results.popitem(last=False)


@lru_cache(maxsize=1)
def get_services() -> Services:
    from db import Db2Repository

    return Services(Db2Repository(), get_embedder(), PayPalClient())


# ------------------------------------------------------------------------------- models
Method = Literal["goods_services", "friends_family", "gift_card", "crypto", "wire"]


class ScreenIn(BaseModel):
    merchant: str = Field("", max_length=200)
    payee_email: str = Field("", max_length=320)
    amount: float = Field(0, ge=0, le=1_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)
    payment_method: Method = "goods_services"
    message: str = Field("", max_length=4000)
    region: str = Field("NG", max_length=20)
    language: Literal["en", "pcm"] = "en"
    explain: bool = True
    seller_account_age_days: int | None = Field(None, ge=0, le=100_000)
    market_price: float | None = Field(None, ge=0)
    source: Literal["paste", "screenshot", "share", "platform", "agent"] = "paste"

    @field_validator("currency")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.upper()


class PurchaseIn(BaseModel):
    instruction: str = Field(..., min_length=5, max_length=3000)
    language: Literal["en", "pcm"] = "en"


class ReportIn(BaseModel):
    entity_type: Literal["email", "phone", "domain", "wallet", "account"]
    value: str = Field(..., min_length=3, max_length=320)
    category: str = Field("other", max_length=40)
    amount: float = Field(0, ge=0, le=1_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)
    narrative: str = Field(..., min_length=10, max_length=2000)
    reporter: str = Field("anonymous", max_length=100)


class QuestionIn(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)


class OrderIn(BaseModel):
    screening_id: int
    acknowledge_risk: bool = False


class CaptureIn(BaseModel):
    screening_id: int


# ------------------------------------------------------------------------------- helpers
def _screen(s: Services, data: ScreenIn, extra: dict | None = None) -> dict:
    amount, currency = data.amount, data.currency
    if not amount:  # buyers just paste the chat; take the price from it
        amount, found_cur = extract_amount(data.message)
        currency = found_cur if amount else currency
    req = ScreenRequest(data.merchant, data.payee_email.strip(), amount, currency,
                        data.payment_method, data.message, data.region,
                        data.seller_account_age_days, data.market_price)
    result = s.engine.screen(req)
    if data.explain:
        ai = s.investigator.explain(req, result, data.language)
        if ai.get("escalate") and ai.get("extra_risk"):
            new_score = min(100, result.risk_score + ai["extra_risk"])
            result.risk_score, result.verdict = new_score, s.engine._verdict(new_score)
        result.ai = ai
        s.repo.update_screening_ai(result.screening_id, ai.get("summary", ""), result.risk_score, result.verdict)
    out = result.as_dict()
    out.update(amount=amount, currency=currency, source=data.source, language=data.language)
    out["paypal_allowed"] = result.verdict != "BLOCK" and amount > 0 and currency in PAYPAL_CURRENCIES
    out["plain"] = present(out, data.language)
    if extra:
        out.update(extra)
    s.remember(out)
    return out


# ------------------------------------------------------------------------------- routes
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/market", include_in_schema=False)
def market():
    return FileResponse(STATIC / "market.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(STATIC / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js", include_in_schema=False)
def service_worker():
    return FileResponse(STATIC / "sw.js", media_type="text/javascript")


@app.get("/api/health")
def health(s: Services = Depends(get_services)):
    try:
        db_ok = s.repo.ping()
    except Exception as exc:
        log.warning("Db2 ping failed: %s", exc)
        db_ok = False
    return {"db2": db_ok, "embedder": s.embedder.name, "llm": settings.llm_enabled,
            "paypal": s.paypal.enabled, "model": settings.gemini_model if settings.llm_enabled else None}


@app.get("/api/config")
def config():
    return {"paypal_client_id": settings.paypal_client_id if settings.paypal_enabled else "",
            "currency": settings.paypal_currency, "llm": settings.llm_enabled,
            "thresholds": {"review": settings.review_threshold, "block": settings.block_threshold}}


@app.post("/api/screen")
def screen(data: ScreenIn, s: Services = Depends(get_services)):
    return _screen(s, data)


@app.post("/api/screen-image")
async def screen_image(file: UploadFile = File(...), language: Literal["en", "pcm"] = Form("en"),
                       s: Services = Depends(get_services)):
    """One-tap check: a screenshot of the chat/listing -> Gemini vision -> PayGuard screening."""
    return _screen_image(s, await file.read(), file.content_type or "", language, "screenshot")


def _screen_image(s: Services, data: bytes, mime: str, language: str, source: str) -> dict:
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
                       payment_method=ex.get("payment_method") if ex.get("payment_method") in
                       ("goods_services", "friends_family", "gift_card", "crypto", "wire") else "goods_services",
                       message=message[:4000], language=language, source=source)
    return _screen(s, data_in, {"screenshot": ex})


@app.post("/share", include_in_schema=False)
async def share_target(title: str = Form(""), text: str = Form(""), url: str = Form(""),
                       media: list[UploadFile] | None = File(None), s: Services = Depends(get_services)):
    """Android share sheet -> installed PayGuard web app. Screens what was shared, then shows the verdict."""
    try:
        if media:
            f = media[0]
            result = _screen_image(s, await f.read(), f.content_type or "", "en", "share")
        else:
            message = "\n".join(x for x in (title, text, url) if x).strip()
            if not message:
                return RedirectResponse("/?error=empty", status_code=303)
            result = _screen(s, ScreenIn(message=message[:4000], source="share"))
    except HTTPException as exc:
        from urllib.parse import quote

        return RedirectResponse(f"/?error={quote(str(exc.detail))}", status_code=303)
    return RedirectResponse(f"/?r={result['screening_id']}", status_code=303)


@app.get("/api/results/{screening_id}")
def get_result(screening_id: int, s: Services = Depends(get_services)):
    if screening_id in s.results:
        return s.results[screening_id]
    raise HTTPException(404, "Result expired - please check again.")


# --- Platform API: marketplaces send the chat + seller signals at "Pay" time; the buyer pastes nothing ---
class ChatLine(BaseModel):
    sender: Literal["buyer", "seller"]
    text: str = Field(..., max_length=2000)


class PlatformCheckIn(BaseModel):
    platform: str = Field(..., max_length=60)
    seller_name: str = Field("", max_length=200)
    seller_email: str = Field("", max_length=320)
    seller_phone: str = Field("", max_length=40)
    seller_account_number: str = Field("", max_length=20)
    seller_account_age_days: int | None = Field(None, ge=0)
    listing_title: str = Field("", max_length=200)
    amount: float = Field(..., gt=0, le=1_000_000)
    currency: str = Field("USD", min_length=3, max_length=3)
    market_price: float | None = Field(None, ge=0)
    payment_method: Method = "goods_services"
    chat: list[ChatLine] = Field(default_factory=list, max_length=60)
    language: Literal["en", "pcm"] = "en"


@app.post("/api/v1/checkout/verify")
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
            "allow_payment": result["verdict"] != "BLOCK", "require_confirmation": result["verdict"] == "REVIEW",
            "headline": result["plain"]["headline"], "reasons": result["plain"]["reasons"],
            "summary": result["plain"]["subline"], "paypal_allowed": result["paypal_allowed"]}


@app.post("/api/agent/purchase")
def agent_purchase(data: PurchaseIn, s: Services = Depends(get_services)):
    """Agentic commerce: sentence -> structured order -> PayGuard screening -> (if allowed) PayPal checkout."""
    intent = s.investigator.parse_purchase(data.instruction)
    method = intent.get("payment_method") or "goods_services"
    if method not in ("goods_services", "friends_family", "gift_card", "crypto", "wire"):
        method = "goods_services"
    screen_in = ScreenIn(
        merchant=str(intent.get("merchant") or "")[:200], payee_email=str(intent.get("payee_email") or "")[:320],
        amount=max(0.0, float(intent.get("amount") or 0)), currency=str(intent.get("currency") or "USD")[:3],
        payment_method=method,
        message=(str(intent.get("seller_message") or "") + "\n" + data.instruction)[:4000],
        language=data.language, source="agent",
    )
    return {"intent": intent, "screening": _screen(s, screen_in)}


@app.post("/api/report")
def report(data: ReportIn, s: Services = Depends(get_services)):
    value = data.value.strip().lower()
    if data.entity_type == "email" and "@" not in value:
        raise HTTPException(422, "Enter a valid e-mail address.")
    eid = s.repo.upsert_entity(data.entity_type, value, "SUSPECT", count_report=True)
    vec = s.embedder.embed([data.narrative])[0]
    rid = s.repo.add_report(eid, data.reporter, data.category, data.amount, data.currency.upper(),
                            data.narrative, vec)
    entity = s.repo.lookup_entities([(data.entity_type, value)])
    return {"report_id": rid, "entity": entity[0] if entity else None}


@app.post("/api/ask")
def ask(data: QuestionIn, s: Services = Depends(get_services)):
    return s.investigator.ask(data.question, s.analyst)


@app.get("/api/analyst/quick")
def analyst_quick():
    return list(QUICK_QUESTIONS)


@app.post("/api/analyst")
def analyst(data: QuestionIn, s: Services = Depends(get_services)):
    return s.analyst.answer(data.question)


@app.get("/api/stats")
def stats(s: Services = Depends(get_services)):
    return s.repo.stats()


@app.get("/api/screenings/recent")
def recent(s: Services = Depends(get_services)):
    return s.repo.recent_screenings(15)


@app.get("/api/screenings/{screening_id}")
def screening(screening_id: int, s: Services = Depends(get_services)):
    row = s.repo.get_screening(screening_id)
    if not row:
        raise HTTPException(404, "Screening not found")
    return row


# --- PayPal: the server re-checks the Db2 verdict; the browser cannot bypass PayGuard ---------
@app.post("/api/paypal/orders")
def create_order(data: OrderIn, s: Services = Depends(get_services)):
    if not s.paypal.enabled:
        raise HTTPException(503, "PayPal sandbox keys are not configured.")
    sc = s.repo.get_screening(data.screening_id)
    if not sc:
        raise HTTPException(404, "Screening not found")
    if sc["verdict"] == "BLOCK":
        raise HTTPException(403, "PayGuard blocked this payment.")
    if sc["verdict"] == "REVIEW" and not data.acknowledge_risk:
        raise HTTPException(409, "This payment needs review. Confirm you understand the risks to continue.")
    if sc["paypal_order_id"] and sc["paypal_status"] in ("COMPLETED",):
        raise HTTPException(409, "This screening was already paid.")
    if float(sc["amount"]) <= 0:
        raise HTTPException(422, "Amount must be greater than zero.")
    desc = f'{sc["merchant"] or "Purchase"} (PayGuard {sc["verdict"]}, risk {sc["risk_score"]})'
    try:
        order = s.paypal.create_order(amount=float(sc["amount"]), currency=sc["currency"], description=desc,
                                      screening_id=sc["id"], risk_score=sc["risk_score"], verdict=sc["verdict"])
    except PayPalError as exc:
        raise HTTPException(exc.status if exc.status < 500 else 502, str(exc))
    s.repo.update_screening_paypal(sc["id"], order["id"], order.get("status", "CREATED"))
    return {"id": order["id"], "status": order.get("status")}


@app.post("/api/paypal/orders/{order_id}/capture")
def capture_order(order_id: str, data: CaptureIn, s: Services = Depends(get_services)):
    sc = s.repo.get_screening(data.screening_id)
    if not sc or sc["paypal_order_id"] != order_id:
        raise HTTPException(404, "Order does not belong to this screening.")
    if sc["verdict"] == "BLOCK":
        raise HTTPException(403, "PayGuard blocked this payment.")
    try:
        result = s.paypal.capture_order(order_id)
    except PayPalError as exc:
        raise HTTPException(exc.status if exc.status < 500 else 502, str(exc))
    status = result.get("status", "UNKNOWN")
    s.repo.update_screening_paypal(sc["id"], order_id, status)
    capture = (((result.get("purchase_units") or [{}])[0].get("payments") or {}).get("captures") or [{}])[0]
    return {"id": order_id, "status": status, "capture_id": capture.get("id"),
            "payer": (result.get("payer") or {}).get("email_address")}


app.mount("/static", StaticFiles(directory=STATIC), name="static")
