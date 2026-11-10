from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings, parse_cors_origins
from app.api.v1.health import router as health_router
from app.api.v1.analysis import router as analysis_router
from app.integrations.db2.client import test_db2_connection

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Autonomous Power Grid Intelligence and Cascading Failure Prevention"
)

# CORS origins come from CORS_ORIGINS (comma-separated). Unset => "*" for local dev.
# On Render, set CORS_ORIGINS to the deployed frontend origin(s).
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": "BLACKSTART AI",
        "status": "online",
        "database": "IBM Db2"
    }


@app.get("/api/v1/db2/status")
def db2_status():
    return test_db2_connection()
