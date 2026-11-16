import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.database.base import init_db, get_db_status
from backend.app.ai.haystack.rag_pipeline import protocol_retriever
from backend.app.ai.semantic.db2_vector_store import vector_store
from backend.app.api.v1 import (
    auth, profiles, trusted_contacts, incidents, sos,
    children, elder_care, responders, community, ai
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("neighbourhood_safety.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Neighbourhood Safety Intelligence Network Backend...")
    init_db()  # fails fast if IBM Db2 is unreachable: there is no fallback database
    logger.info("IBM Db2 %s initialised.", settings.DB2_DATABASE)
    yield
    logger.info("Shutting down Neighbourhood Safety Intelligence Network Backend...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Privacy-first civic safety and emergency assistance platform with AI triage and real-time incident coordination.",
    lifespan=lifespan
)

# CORS: explicit origins only (validated in production by core.config)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=(self), camera=(), microphone=()",
    "Cache-Control": "no-store",
}


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Log the full error server-side; never return SQL, driver or stack details to clients.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error. The incident has been logged."})

# Health endpoint
@app.get("/health", tags=["Health & Diagnostics"])
def health_check():
    db_status = get_db_status()
    if settings.APP_ENV.lower() == "production":
        # Do not disclose connection details (host, port, database name) publicly.
        db_status = {k: db_status[k] for k in ("mode", "connected", "driver") if k in db_status}
    return {
        "status": "healthy" if db_status.get("connected") else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.APP_ENV,
        "database": db_status,
        "ai_features": {
            "haystack_retrieval": "hybrid (BM25 + IBM Db2 vector)" if protocol_retriever.hybrid else "BM25",
            "db2_vector_search": "active" if vector_store.enabled else "inactive",
            "triage_agents": "active"
        }
    }

@app.get("/", tags=["Root"])
def root():
    return {
        "message": f"Welcome to the {settings.PROJECT_NAME} API",
        "version": settings.VERSION,
        "docs_url": "/docs",
        "health_check": "/health",
        "api_v1_prefix": settings.API_V1_PREFIX
    }

# Include all API v1 routes
prefix = settings.API_V1_PREFIX
app.include_router(auth.router, prefix=prefix)
app.include_router(profiles.router, prefix=prefix)
app.include_router(trusted_contacts.router, prefix=prefix)
app.include_router(sos.router, prefix=prefix)
app.include_router(incidents.router, prefix=prefix)
app.include_router(children.router, prefix=prefix)
app.include_router(elder_care.router, prefix=prefix)
app.include_router(responders.router, prefix=prefix)
app.include_router(community.router, prefix=prefix)
app.include_router(ai.router, prefix=prefix)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=True)  # Docker passes --host 0.0.0.0
