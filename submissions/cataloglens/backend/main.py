"""
CatalogLens Backend Entrypoint.
FastAPI Application serving database intelligence and LangGraph investigation pipelines.
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .core.config import get_settings
from .api.routes import router
from .db.connection import Db2ConnectionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("CatalogLens")

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=settings.app_description,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")
app.include_router(router)  # Also expose without /api prefix for convenience


@app.get("/", include_in_schema=False)
def root():
    """Redirect root to interactive Swagger UI."""
    return RedirectResponse(url="/docs")


@app.on_event("startup")
async def startup_event():
    logger.info("Starting %s v%s...", settings.app_name, settings.app_version)
    driver_ok = Db2ConnectionManager.is_driver_available()
    logger.info("IBM Db2 Native Driver (ibm_db): %s", "INSTALLED" if driver_ok else "NOT FOUND (Demo Mode Active)")
    logger.info("Anthropic Claude Reasoning: %s", "CONFIGURED" if settings.has_anthropic_key() else "UNCONFIGURED (Heuristic Fallback Active)")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=settings.backend_host, port=settings.backend_port, reload=True)
