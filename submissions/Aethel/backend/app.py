import logging
import os
import secrets
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.companion.agent import AgentConfigurationError, AgentUnavailableError, reply_to
from backend.companion.db import Db2Store, Db2UnavailableError, LocalMemoryStore


ROOT_DIR = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT_DIR / "frontend"
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("aethel")
db2_store = Db2Store()
store = db2_store
local_store = LocalMemoryStore()
session_secret = os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(48)
if session_secret.startswith("replace-with-"):
    session_secret = secrets.token_urlsafe(48)
production = os.environ.get("APP_ENV", "development").lower() == "production"


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileInput(APIModel):
    name: str = Field(min_length=1, max_length=60)
    time_zone: str = Field(default="UTC", min_length=1, max_length=80)
    check_ins_enabled: bool = True

    @field_validator("name", "time_zone")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value


class ReminderInput(APIModel):
    task_type: str = Field(pattern="^(pill|health_check)$")
    description: str = Field(min_length=1, max_length=160)
    due_at: datetime

    @field_validator("description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Reminder details cannot be blank.")
        return value


class ChatInput(APIModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank.")
        return value


class ReviewInput(APIModel):
    name: str = Field(default="A family member", min_length=1, max_length=36)
    message: str = Field(min_length=4, max_length=320)

    @field_validator("name", "message")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("message")
    @classmethod
    def validate_message_length(cls, value: str) -> str:
        if len(value) < 4:
            raise ValueError("A community note must be at least four characters.")
        return value


def current_session_id(request: Request) -> str:
    session_id = request.session.get("aethel_session_id")
    if not isinstance(session_id, str) or len(session_id) != 32:
        session_id = uuid.uuid4().hex
        request.session["aethel_session_id"] = session_id
    return session_id


@asynccontextmanager
async def lifespan(application: FastAPI):
    if production:
        configured_secret = os.environ.get("SESSION_SECRET", "")
        if len(configured_secret) < 32 or configured_secret.startswith("replace-with-"):
            raise RuntimeError("Set a high-entropy SESSION_SECRET of at least 32 characters.")
        if os.environ.get("COOKIE_SECURE", "false").lower() != "true":
            raise RuntimeError("COOKIE_SECURE=true is required in production.")
    db2_required = production or os.environ.get("REQUIRE_DB2", "false").lower() == "true"
    application.state.db2_required = db2_required
    application.state.storage = store
    application.state.local_mode = False
    if db2_store.is_configured:
        try:
            db2_store.initialize()
            application.state.db2_ready = True
            logger.info("Connected to Db2 and verified Aethel tables.")
        except Db2UnavailableError:
            application.state.db2_ready = False
            if db2_required:
                logger.exception("Db2 initialization failed and is required.")
                raise
            application.state.storage = local_store
            application.state.local_mode = True
            logger.exception("Db2 initialization failed; using in-memory local storage.")
    else:
        application.state.db2_ready = False
        if db2_required:
            raise RuntimeError("Db2 credentials are required when REQUIRE_DB2=true.")
        application.state.storage = local_store
        application.state.local_mode = True
        logger.info("Db2 is not configured; using in-memory local storage.")
    yield


app = FastAPI(
    title="Aethel Family Companion",
    description="A human-centered family companion for preferences, reminders, supportive conversation, and community feedback.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if not production else None,
    redoc_url=None,
)

allowed_hosts = [
    host.strip()
    for host in os.environ.get(
        "ALLOWED_HOSTS", "localhost,127.0.0.1,testserver"
    ).split(",")
    if host.strip()
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret,
    session_cookie="aethel_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=os.environ.get("COOKIE_SECURE", "false").lower() == "true",
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), geolocation=(), microphone=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    if os.environ.get("COOKIE_SECURE", "false").lower() == "true":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


templates = Jinja2Templates(directory=FRONTEND_DIR / "templates")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")
app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")


def require_db2(request: Request) -> str:
    if not getattr(request.app.state, "db2_ready", False) and not getattr(
        request.app.state, "local_mode", False
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Db2 is not ready. Configure the local TESTDB connection and initialize its tables.",
        )
    return current_session_id(request)


def get_storage(request: Request):
    return getattr(request.app.state, "storage", store)


@app.get("/", include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"page": "home", "title": "Aethel — care that stays close"},
    )


@app.get("/prototype", include_in_schema=False)
def prototype(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="prototype.html",
        context={"page": "prototype", "title": "The companion — Aethel"},
    )


@app.get("/architecture", include_in_schema=False)
def architecture(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="architecture.html",
        context={"page": "architecture", "title": "Inside the care loop — Aethel"},
    )


@app.get("/community", include_in_schema=False)
def community(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="community.html",
        context={"page": "community", "title": "The community board — Aethel"},
    )


@app.get("/api/status")
def service_status(request: Request):
    current_session_id(request)
    local_mode = getattr(request.app.state, "local_mode", False)
    db2_ready = getattr(request.app.state, "db2_ready", False)
    if not local_mode and db2_store.is_configured:
        try:
            db2_ready = bool(db2_store.ping())
        except Db2UnavailableError:
            db2_ready = False
            logger.warning("Db2 health check failed.")
        if not db2_ready and not getattr(request.app.state, "db2_required", False):
            request.app.state.storage = local_store
            request.app.state.local_mode = True
            local_mode = True
    request.app.state.db2_ready = db2_ready
    return {
        "app": "Aethel",
        "db2_configured": db2_store.is_configured,
        "db2_ready": db2_ready,
        "local_mode": local_mode,
        "storage_mode": "local" if local_mode else "db2",
        "chat_configured": bool(
            os.environ.get("OPENAI_API_KEY")
            and not os.environ["OPENAI_API_KEY"].lower().startswith("your-")
        ),
    }


@app.get("/api/health")
def health(request: Request):
    local_mode = getattr(request.app.state, "local_mode", False)
    ready = getattr(request.app.state, "db2_ready", False)
    if not local_mode and db2_store.is_configured:
        try:
            ready = bool(db2_store.ping())
        except Db2UnavailableError:
            logger.warning("Db2 health check failed.")
            ready = False
        if not ready and not getattr(request.app.state, "db2_required", False):
            request.app.state.storage = local_store
            request.app.state.local_mode = True
            local_mode = True
    request.app.state.db2_ready = ready
    return JSONResponse(
        status_code=(
            status.HTTP_200_OK
            if ready or local_mode
            else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={
            "status": "ok" if ready or local_mode else "degraded",
            "db2": ready,
            "storage_mode": "local" if local_mode else "db2",
        },
    )


@app.get("/api/profile")
def get_profile(request: Request):
    session_id = require_db2(request)
    return get_storage(request).get_profile(session_id) or {}


@app.put("/api/profile")
def save_profile(payload: ProfileInput, request: Request):
    session_id = require_db2(request)
    try:
        ZoneInfo(payload.time_zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(status_code=422, detail="Choose a valid IANA time zone.")
    profile = payload.model_dump()
    get_storage(request).save_profile(session_id, profile)
    return profile


@app.get("/api/tasks")
def list_tasks(request: Request):
    return get_storage(request).list_tasks(require_db2(request))


@app.post("/api/tasks", status_code=status.HTTP_201_CREATED)
def create_task(payload: ReminderInput, request: Request):
    session_id = require_db2(request)
    storage = get_storage(request)
    profile = storage.get_profile(session_id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Complete onboarding before adding reminders.")

    due_at = payload.due_at
    if due_at.tzinfo is None:
        try:
            local_zone = ZoneInfo(profile["time_zone"])
        except (KeyError, ZoneInfoNotFoundError, ValueError):
            raise HTTPException(status_code=422, detail="Update your saved time zone and try again.")
        local_due_at = due_at.replace(tzinfo=local_zone)
        if local_due_at.astimezone(timezone.utc).astimezone(local_zone).replace(tzinfo=None) != due_at:
            raise HTTPException(
                status_code=422,
                detail="That local time does not exist due to a clock change. Choose another time.",
            )
        due_at = local_due_at
    if len(payload.description) == 0:
        raise HTTPException(status_code=422, detail="Reminder details cannot be blank.")

    task = {
        "id": uuid.uuid4().hex,
        "task_type": payload.task_type,
        "description": payload.description,
        "due_at": due_at.astimezone(timezone.utc),
    }
    storage.create_task(session_id, task)
    return {**task, "due_at": task["due_at"].isoformat(), "status": "pending"}


@app.get("/api/reminders/due")
def due_reminders(request: Request):
    return get_storage(request).claim_due_tasks(require_db2(request))


@app.post("/api/tasks/{task_id}/complete")
def complete_task(task_id: str, request: Request):
    if not get_storage(request).complete_task(require_db2(request), task_id):
        raise HTTPException(status_code=404, detail="Reminder not found or already completed.")
    return {"completed": True}


@app.get("/api/history")
def get_history(request: Request):
    return get_storage(request).get_history(require_db2(request))


@app.post("/api/chat")
def chat(payload: ChatInput, request: Request):
    session_id = require_db2(request)
    storage = get_storage(request)
    profile = storage.get_profile(session_id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Complete onboarding before starting a conversation.")
    history = storage.get_history(session_id)
    try:
        answer = reply_to(payload.message, profile, history)
    except AgentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except AgentUnavailableError as exc:
        logger.exception("The configured chat provider could not complete the request.")
        raise HTTPException(status_code=502, detail="The companion is temporarily unavailable. Please try again.") from exc
    storage.add_turn(session_id, payload.message, answer)
    return {"reply": answer}


@app.get("/api/reviews")
def list_reviews(request: Request):
    require_db2(request)
    return get_storage(request).list_reviews()


@app.post("/api/reviews", status_code=status.HTTP_201_CREATED)
def create_review(payload: ReviewInput, request: Request):
    session_id = require_db2(request)
    review = {
        "id": uuid.uuid4().hex,
        "name": payload.name,
        "message": payload.message,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    get_storage(request).create_review(session_id, review)
    return review


@app.exception_handler(Db2UnavailableError)
async def handle_db2_unavailable(request: Request, exc: Db2UnavailableError):
    logger.error("Db2 request failed for %s: %s", request.method, exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Db2 is unavailable. Check the local TESTDB service and connection settings."},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.app:app",
        host=os.environ.get("APP_HOST", "127.0.0.1"),
        port=int(os.environ.get("APP_PORT", "8000")),
        reload=os.environ.get("APP_ENV", "development").lower() != "production",
    )
