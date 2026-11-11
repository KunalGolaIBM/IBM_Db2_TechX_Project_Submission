"""SplitSync AI backend application factory."""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from config import settings
    from api.router import router as api_router
    from api.health import router as health_router
    from api.middleware import (
        AppError,
        app_error_handler,
        value_error_handler,
        generic_exception_handler,
    )
except ImportError:
    from backend.config import settings
    from backend.api.router import router as api_router
    from backend.api.health import router as health_router
    from backend.api.middleware import (
        AppError,
        app_error_handler,
        value_error_handler,
        generic_exception_handler,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("splitsync")

app = FastAPI(
    title="SplitSync AI API",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(ValueError, value_error_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Routers
app.include_router(health_router)
app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event() -> None:
    """Execute database migrations and log application startup."""
    try:
        try:
            from db.migrations.runner import run_migrations
        except ImportError:
            from backend.db.migrations.runner import run_migrations

        applied = run_migrations()
        if applied:
            logger.info("Db2 migrations applied on startup: %s", applied)
        else:
            logger.info("Db2 database schema is up to date.")
    except Exception as exc:
        logger.warning("Db2 migrations skipped or failed during startup: %s", exc)

    logger.info("SplitSync AI backend started")


@app.get("/")
async def root() -> dict[str, str]:
    """Root status endpoint."""
    return {
        "name": "SplitSync AI API",
        "version": "1.0.0",
        "status": "running",
    }
