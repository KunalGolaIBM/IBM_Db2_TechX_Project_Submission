"""
ClaimGuard AI - Main FastAPI Application
Agentic AI-powered Insurance Claim Verification and Fraud Detection System
Official Submission: IBM Db2Hack 2026
Author: Nitesh Barnwal (GitHub: Nitesh0517)
"""

import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .config import settings
from .routes import audit, auth, claims, health, policies, verification

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("claimguard.api")

app = FastAPI(
    title="ClaimGuard AI API",
    description=(
        "Enterprise Insurance Claim Verification & Fraud Detection System "
        "powered by IBM Db2, LangChain, LangGraph, and Google Gemini."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_and_audit_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-Db2-Backend"] = "IBM Db2 Enterprise"
    response.headers["X-System-Mode"] = "DEMO" if settings.DEMO_MODE else "LIVE"
    return response


# Include Routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(claims.router)
app.include_router(policies.router)
app.include_router(audit.router)
app.include_router(verification.router)


@app.get("/")
def root():
    return {
        "project": "ClaimGuard AI",
        "tagline": "Agentic Intelligence for Smarter Insurance Claim Verification.",
        "version": "1.0.0",
        "author": "Nitesh Barnwal (Nitesh0517)",
        "hackathon": "IBM Db2Hack 2026",
        "docs_url": "/docs",
        "health_check": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=True
    )
