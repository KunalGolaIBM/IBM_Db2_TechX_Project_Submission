import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.database.base import init_db, get_db_status
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
    try:
        init_db()
        logger.info(f"Database initialized in [{settings.DATABASE_MODE.upper()}] mode.")
    except Exception as e:
        logger.error(f"Database initialization failure: {e}")
        # Note: In db2 mode, strict failure will bubble up as required
        if settings.DATABASE_MODE.lower() == "db2":
            raise e
    yield
    logger.info("Shutting down Neighbourhood Safety Intelligence Network Backend...")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Privacy-first civic safety and emergency assistance platform with AI triage and real-time incident coordination.",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health endpoint
@app.get("/health", tags=["Health & Diagnostics"])
def health_check():
    db_status = get_db_status()
    return {
        "status": "healthy" if db_status.get("connected") else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.APP_ENV,
        "database": db_status,
        "ai_features": {
            "haystack_rag": "active",
            "crewai_agents": "active"
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
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
