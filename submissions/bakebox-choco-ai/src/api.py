"""
Production FastAPI Application Server for BAKEBOX Choco AI on IBM Db2.

Exposes hardened REST endpoints + self-contained playground (`/demo`):
1. GET  / & GET /api/health               : System health, Db2 mode, RRF & audit integrity status
2. GET  /demo                             : Interactive Judge Engineering & Bakery Storefront UI
3. POST /api/chat                         : Session-isolated CHOCO AI + guardrails + 3-Way RRF
4. GET  /api/cakes/search                 : 3-Way RRF catalog search with metadata filter pushdown
5. GET  /api/cakes/{cake_id}/availability : In-Db2 Multi-Level Recursive BOM CTE availability check
6. POST /api/orders                       : Single-UOW ACID order placement (BOM + WITH RS + Audit)
7. GET  /api/orders/masked-summary        : Query masked view V_MASKED_BAKERY_ORDERS (zero PII)
8. GET  /api/orders/{order_id}            : 2FA phone-verified tracking with PII boundary masking
9. POST /api/orders/{order_id}/refund     : Phone-authenticated Happiness Guarantee + Audit Log
10. GET /api/audit/verify                 : Forensic verification of SHA-256 hash-chained BB_AUDIT_LOG
"""
import hmac
import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

_pkg_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _pkg_root not in sys.path:
    sys.path.insert(0, _pkg_root)

try:
    from fastapi import FastAPI, Header, HTTPException, Path as FPath, Query, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel, Field
except ImportError:
    FastAPI = None
    Header = lambda default=None, **kwargs: default
    HTTPException = None
    Request = Any
    HTMLResponse = None
    JSONResponse = None
    Query = lambda default=..., **kwargs: default
    FPath = lambda default=..., **kwargs: default
    BaseModel = object
    Field = lambda *args, **kwargs: None

from src.db import db_session, execute_query, is_live_db2_available
from src.demo_ui import DEMO_HTML
from src.order_engine import (
    check_recipe_bom_availability,
    evaluate_refund_request,
    is_cake_bakeable,
    place_verified_order_atomic,
    verify_audit_chain,
)
from src.query_engine import ChocoQueryEngine
from src.security import check_prompt_security, extract_client_ip, validate_session_id

START_TIME = time.time()
engine_instance: Optional[ChocoQueryEngine] = None
_engine_lock = threading.Lock()


def _require_operator_key(x_operator_key: Optional[str] = None) -> None:
    """Enforce `X-Operator-Key` header verification when `OPERATOR_API_KEY` is configured."""
    expected = (os.getenv("OPERATOR_API_KEY") or "").strip()
    if not expected or expected == "your_operator_api_key_here":
        return
    supplied = x_operator_key.strip() if isinstance(x_operator_key, str) else ""
    if not supplied or not hmac.compare_digest(supplied, expected):
        if HTTPException is not None:
            raise HTTPException(status_code=401, detail="Missing or invalid X-Operator-Key header.")
        raise PermissionError("Missing or invalid X-Operator-Key header.")


def get_engine() -> ChocoQueryEngine:
    global engine_instance
    if engine_instance is None:
        with _engine_lock:
            if engine_instance is None:
                engine_instance = ChocoQueryEngine(use_llm=True)
    return engine_instance


# ==============================================================================
# PYDANTIC REQUEST/RESPONSE SCHEMAS & STRICT INPUT VALIDATION
# ==============================================================================

if BaseModel is not object:
    class CakeCardSchema(BaseModel):
        name: str = Field(..., description="Cake title")
        price: float = Field(..., description="Base retail price in INR")
        eggless: bool = Field(True, description="Whether pure veg eggless is available")
        branches: List[str] = Field(
            default_factory=lambda: ["Holigate (Mathura)", "Gosna Highway Kitchen"],
            description="Mathura branch availability",
        )
        shelf_life: str = Field("24 Hours (Fresh Chilled)", description="Recommended consumption window")
        slug: str = Field(..., description="URL slug or SKU identifier")
        score: Optional[float] = Field(None, description="Fused 3-Way RRF ranking score")

    class ChatRequest(BaseModel):
        session_id: str = Field(
            "session_default",
            min_length=1,
            max_length=64,
            pattern=r"^[a-zA-Z0-9_-]+$",
            description="Unique client session ID for buffer memory isolation",
        )
        message: str = Field(..., min_length=1, max_length=2000, description="Customer natural language message")

    class ChatResponse(BaseModel):
        reply: str
        ui_cards: List[CakeCardSchema] = []
        intent: str
        session_id: str
        guardrail_triggered: bool = False

    class OrderCreateRequest(BaseModel):
        cake_id: int = Field(..., ge=1, description="Target cake ID from BB_CAKES")
        customer_name: str = Field(..., min_length=2, max_length=120, description="Customer full name")
        customer_phone: str = Field(..., min_length=10, max_length=20, description="Registered 10-digit mobile")
        quantity: int = Field(1, ge=1, le=20, description="Order quantity")
        cake_base: str = Field("Khoaa (Eggless)", max_length=64)
        custom_message: str = Field("", max_length=200)
        delivery_address: str = Field("Mathura, UP", max_length=400)
        session_id: str = Field("api_order", min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")

    class RefundRequest(BaseModel):
        phone: str = Field("", max_length=20, description="Registered 10-digit customer phone for 2FA")
        reason: str = Field(
            "Cake damaged in transit or incorrect base delivered",
            min_length=3,
            max_length=500,
            description="Reason for refund request",
        )
else:
    class CakeCardSchema:
        def __init__(self, name: str, price: float, eggless: bool = True, branches=None, shelf_life="24h", slug="", score=None):
            self.name = name
            self.price = price
            self.eggless = eggless
            self.branches = branches or ["Holigate", "Gosna"]
            self.shelf_life = shelf_life
            self.slug = slug
            self.score = score

    class ChatRequest:
        def __init__(self, session_id: str = "default", message: str = ""):
            self.session_id = session_id
            self.message = message

    class ChatResponse:
        def __init__(self, reply: str, ui_cards: list = None, intent: str = "", session_id: str = "", guardrail_triggered: bool = False):
            self.reply = reply
            self.ui_cards = ui_cards or []
            self.intent = intent
            self.session_id = session_id
            self.guardrail_triggered = guardrail_triggered

    class OrderCreateRequest:
        def __init__(self, cake_id: int = 1, customer_name: str = "", customer_phone: str = "", quantity: int = 1, cake_base: str = "Khoaa (Eggless)", custom_message: str = "", delivery_address: str = "Mathura, UP", session_id: str = "api_order"):
            self.cake_id = cake_id
            self.customer_name = customer_name
            self.customer_phone = customer_phone
            self.quantity = quantity
            self.cake_base = cake_base
            self.custom_message = custom_message
            self.delivery_address = delivery_address
            self.session_id = session_id

    class RefundRequest:
        def __init__(self, phone: str = "", reason: str = "Damaged"):
            self.phone = phone
            self.reason = reason


# ==============================================================================
# CORE REST BUSINESS LOGIC ENDPOINTS
# ==============================================================================

def get_health_status() -> Dict[str, Any]:
    """Return live system health, Db2 connectivity mode, catalog count, and audit state."""
    engine = get_engine()
    live_db2 = is_live_db2_available()
    with db_session() as conn:
        audit_ok, bad_id, _ = verify_audit_chain(conn)

    return {
        "status": "HEALTHY",
        "uptime_seconds": round(time.time() - START_TIME, 2),
        "db2_mode": "LIVE_DB2" if live_db2 else "MOCK_DB2_OFFLINE_SANDBOX",
        "db2_features_active": [
            "3-Way Hybrid Reciprocal Rank Fusion (k=60) + Metadata Pushdown",
            "Db2 Native Vector Store (DB2LlamaVS / Offline Cosine Mirror)",
            "Row-Level ACID Concurrency (SELECT FOR UPDATE WITH RS + SP_RESERVE_CAKE_STOCK)",
            "In-Database Multi-Level Recursive Bill-of-Materials (BOM) CTE",
            "Cryptographic SHA-256 Hash-Chained Audit Trail (BB_AUDIT_LOG)",
            "Db2-Backed Conversation Buffer (BB_USER_CONVERSATION_BUFFER)",
            "Least-Privilege Db2 RBAC & Append-Only Audit Enforcement",
        ],
        "catalog_items_indexed": len(engine.retriever.corpus_nodes) if hasattr(engine.retriever, "corpus_nodes") else 0,
        "audit_chain_intact": audit_ok,
        "compromised_audit_log_id": bad_id,
        "session_isolation": "ENABLED",
        "active_sessions": len(engine.sessions),
    }


def chat_endpoint(req: ChatRequest, request: Request = None) -> ChatResponse:
    """Process customer natural language chat through CHOCO AI with security guardrails."""
    try:
        clean_session_id = validate_session_id(req.session_id)
    except ValueError:
        if HTTPException is not None:
            raise HTTPException(status_code=400, detail="Invalid session_id format.")
        raise

    is_safe, _ = check_prompt_security(req.message)
    if not is_safe:
        return ChatResponse(
            reply=(
                "Radhe Radhe ji! Shri Ram Baker's Choco AI customer safety filter triggered. "
                "Aapka request hamare automated security guidelines ke mutabiq reject kar diya gaya hai. "
                "Hum keval authentic bakery queries aur real order tracking process karte hain."
            ),
            ui_cards=[],
            intent="SECURITY_VIOLATION",
            session_id=clean_session_id,
            guardrail_triggered=True,
        )

    engine = get_engine()
    result = engine.query(req.message, session_id=clean_session_id, client_ip=extract_client_ip(request))
    cards = [
        CakeCardSchema(
            name=card.get("name", "Artisan Cake"),
            price=float(card.get("price", 499.0)),
            eggless=bool(card.get("is_eggless_available", True)),
            branches=["Holigate (Mathura)", "Gosna Highway Kitchen"],
            shelf_life="24 Hours (Chilled)",
            slug=card.get("sku_id", "cake-sku"),
            score=card.get("rrf_score", card.get("score")),
        )
        for card in result.get("ui_cards", [])
    ]
    return ChatResponse(
        reply=result.get("reply", "Radhe Radhe ji!"),
        ui_cards=cards,
        intent=result.get("intent", "UNKNOWN"),
        session_id=clean_session_id,
        guardrail_triggered=bool(result.get("guardrail_triggered", False)),
    )


def search_cakes(
    q: str = Query(..., min_length=1, max_length=300, description="Cake search query"),
    eggless_only: bool = False,
    max_price: Optional[float] = Query(None, gt=0, description="Optional max INR budget"),
) -> Dict[str, Any]:
    """Execute 3-Way RRF search with security validation and metadata pushdown."""
    clean_q = (q or "").strip()
    if not clean_q or len(clean_q) > 300:
        raise ValueError("Search query must be between 1 and 300 characters.")
    is_safe, _ = check_prompt_security(clean_q)
    if not is_safe:
        raise ValueError("Search query rejected by security policy.")

    engine = get_engine()
    # Guard direct Python calls where Query/None defaults might pass FastAPI's Query(...) object
    budget = max_price if isinstance(max_price, (int, float)) else None
    cards = engine.tool_recommend_cakes(clean_q, limit=6, eggless_only=eggless_only, max_price=budget)
    return {
        "query": clean_q,
        "total_matches": len(cards),
        "algorithm": "3-Way Reciprocal Rank Fusion (k=60)",
        "results": cards,
    }


def get_cake_bom_availability(
    cake_id: int = FPath(..., ge=1, description="Numeric Cake ID"),
) -> Dict[str, Any]:
    """Run In-Db2 Multi-Level Recursive BOM CTE and fetch live finished cake inventory."""
    if not isinstance(cake_id, int) or cake_id <= 0:
        raise ValueError("cake_id must be a positive integer.")
    with db_session() as conn:
        cakes = execute_query(conn, "SELECT CAKE_ID, NAME, SKU_ID, STOCK_QTY, PRICE FROM BB_CAKES WHERE CAKE_ID = ?", (cake_id,))
        if not cakes:
            return {"cake_id": cake_id, "found": False, "message": f"Cake ID #{cake_id} not found."}
        bom_rows = check_recipe_bom_availability(conn, cake_id)
        bakeable, missing = is_cake_bakeable(conn, cake_id)
        return {
            "cake_id": cake_id,
            "found": True,
            "cake": cakes[0],
            "bakeable_from_raw_bom": bakeable,
            "missing_ingredients": missing,
            "bom_tree": bom_rows,
        }


def post_create_order(req: OrderCreateRequest) -> Dict[str, Any]:
    """Execute Single-UOW Atomic Order Placement with BOM check, WITH RS stock lock & SHA-256 audit."""
    clean_sid = validate_session_id(req.session_id)
    with db_session() as conn:
        return place_verified_order_atomic(
            conn,
            cake_id=req.cake_id,
            customer_name=req.customer_name,
            customer_phone=req.customer_phone,
            quantity=req.quantity,
            cake_base=req.cake_base,
            custom_message=req.custom_message,
            delivery_address=req.delivery_address,
            session_id=clean_sid,
        )


def get_masked_order_summary(
    x_operator_key: Optional[str] = Header(default=None, alias="X-Operator-Key"),
) -> Dict[str, Any]:
    """Read `V_MASKED_BAKERY_ORDERS` view inside IBM Db2 (never exposes raw customer PII)."""
    _require_operator_key(x_operator_key)
    with db_session() as conn:
        rows = execute_query(
            conn,
            "SELECT ORDER_ID, MASKED_CUSTOMER_NAME, MASKED_PHONE, ORDER_TYPE, ORDER_STATUS, TOTAL_AMOUNT, CREATED_AT FROM V_MASKED_BAKERY_ORDERS",
        )
        return {"view": "V_MASKED_BAKERY_ORDERS", "count": len(rows), "orders": rows}


def get_order_tracking(
    order_id: int = FPath(..., ge=1, description="Numeric Order ID"),
    phone: Optional[str] = Query(None, min_length=10, max_length=20, description="Registered 10-digit mobile number"),
    request: Request = None,
) -> Dict[str, Any]:
    """Retrieve verified order tracking with 2FA phone verification and PII boundary masking."""
    if not isinstance(order_id, int) or order_id <= 0:
        raise ValueError("order_id must be a positive integer.")
    engine = get_engine()
    order = engine.tool_track_live_order(
        order_id=order_id,
        phone_number=phone,
        client_ip=extract_client_ip(request),
    )
    if not order:
        return {"status": "ORDER_NOT_FOUND", "message": f"Order #{order_id} not found."}
    return order


def post_refund_request(
    order_id: int = FPath(..., ge=1, description="Numeric Order ID"),
    req: Optional[RefundRequest] = None,
    request: Request = None,
) -> Dict[str, Any]:
    """Evaluate Happiness Guarantee refund with 2FA phone verification and atomic audit log."""
    phone = req.phone if req else ""
    reason = req.reason if req else "Customer claim"
    with db_session() as conn:
        return evaluate_refund_request(
            conn,
            order_id=order_id,
            reason=reason,
            customer_phone=phone,
            require_phone_auth=True,
            client_ip=extract_client_ip(request),
        )


def get_audit_verification(
    x_operator_key: Optional[str] = Header(default=None, alias="X-Operator-Key"),
) -> Dict[str, Any]:
    """Verify full cryptographic integrity of `BB_AUDIT_LOG` hash chain."""
    _require_operator_key(x_operator_key)
    with db_session() as conn:
        is_valid, compromised_id, details = verify_audit_chain(conn)
        cnt_rows = execute_query(conn, "SELECT COUNT(*) AS CNT FROM BB_AUDIT_LOG", ())
        total_records = cnt_rows[0]["CNT"] if cnt_rows else 0
    return {
        "audit_table": "BB_AUDIT_LOG",
        "chain_intact": is_valid,
        "total_records": total_records,
        "compromised_log_id": compromised_id,
        "details": details or "All cryptographic HMAC-SHA256 links verified.",
    }


def serve_demo_ui() -> Any:
    """Serve self-contained HTML engineering playground for 10-second live verification."""
    return HTMLResponse(content=DEMO_HTML) if HTMLResponse is not None else DEMO_HTML


# ==============================================================================
# FASTAPI APP INSTANTIATION (HARDENED CORS)
# ==============================================================================

if FastAPI is not None:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        eng = get_engine()
        try:
            yield
        finally:
            if getattr(eng, "vector_store", None) is not None and hasattr(eng.vector_store, "close"):
                eng.vector_store.close()

    _raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:8000")
    _allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
    _allow_creds = "*" not in _allowed_origins

    app = FastAPI(
        title="BAKEBOX Choco AI — IBM Db2 Autonomous Bakery Management API",
        description="Official REST API for BAKEBOX Choco AI (IBM Db2 TechX Summit 2026).",
        version="2.3.0",
        lifespan=lifespan,
    )

    @app.exception_handler(ValueError)
    async def value_error_exception_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins,
        allow_credentials=_allow_creds,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-Operator-Key"],
    )

    app.get("/", tags=["Health"])(get_health_status)
    app.get("/api/health", tags=["Health"])(get_health_status)
    app.get("/demo", tags=["Interactive UI"])(serve_demo_ui)
    app.post("/api/chat", response_model=ChatResponse, tags=["AI Agent"])(chat_endpoint)
    app.get("/api/cakes/search", tags=["Catalog Search"])(search_cakes)
    app.get("/api/cakes/{cake_id}/availability", tags=["Inventory & BOM"])(get_cake_bom_availability)
    app.post("/api/orders", tags=["Orders"])(post_create_order)
    app.get("/api/orders/masked-summary", tags=["Orders"])(get_masked_order_summary)
    app.get("/api/orders/{order_id}", tags=["Orders"])(get_order_tracking)
    app.post("/api/orders/{order_id}/refund", tags=["Orders"])(post_refund_request)
    app.get("/api/audit/verify", tags=["Security & Audit"])(get_audit_verification)
else:
    app = None
