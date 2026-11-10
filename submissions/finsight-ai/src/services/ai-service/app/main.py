import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, chat, search, anomalies, internal, imports
from app.db import db_manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("finsight.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FinSight AI Python Service (v0.1.0)...")
    try:
        # Pre-flight check to verify Db2 engine
        health_info = db_manager.health_check()
        logger.info(
            "Connected to IBM Db2 %s (Server: %s, Tx Count: %d, Latency: %.2f ms)",
            health_info["database"],
            health_info["server_version"],
            health_info["total_transactions"],
            health_info["latency_ms"]
        )
    except Exception as e:
        logger.warning("IBM Db2 pre-flight check warning (will retry on demand): %s", e)
    yield
    logger.info("Shutting down FinSight AI Python Service...")

app = FastAPI(
    title="FinSight AI Service",
    description="LangChain-powered Financial Intelligence Service on IBM Db2",
    version="0.1.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Timing & Safety Middleware
@app.middleware("http")
async def add_timing_and_security(request: Request, call_next):
    t0 = time.time()
    try:
        response = await call_next(request)
        elapsed = (time.time() - t0) * 1000.0
        response.headers["X-Response-Time-Ms"] = f"{elapsed:.2f}"
        return response
    except Exception as e:
        logger.exception("Unhandled error processing request: %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred. Financial queries remain protected."}
        )

# Routers
app.include_router(health.router)
app.include_router(chat.router)
app.include_router(search.router)
app.include_router(anomalies.router)
app.include_router(imports.router)
app.include_router(internal.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.ai_service_host, port=settings.ai_service_port, reload=True)
