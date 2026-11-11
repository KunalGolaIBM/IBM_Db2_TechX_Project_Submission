from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.logging import setup_logging, logger
from app.database.migrations import run_migrations
from app.api.v1.router import api_v1_router
from app.api.v1.health import router as health_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Initializing Cloud-Loop AI & IBM Db2 Service...")
    run_migrations()
    yield
    logger.info("Cloud-Loop AI Service shutting down.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise Opportunity Intelligence Platform with IBM Db2 and Haystack AI Integration",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Standardized Error Envelope
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    status_code = getattr(exc, "status_code", 500)
    message = getattr(exc, "detail", str(exc)) if settings.DEBUG else "An internal server error occurred."
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": {
                "code": getattr(exc, "code", "INTERNAL_ERROR"),
                "message": message,
            }
        }
    )

# Mount root health check and versioned API v1
app.include_router(health_router)
app.include_router(api_v1_router)

@app.get("/")
def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
        "health": "/health",
        "api_v1": "/api/v1",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
