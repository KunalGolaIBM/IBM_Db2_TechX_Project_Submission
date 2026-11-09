"""FastAPI application entrypoint for PACT — Procurement Audit & Counterfactual Triage."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.models import ErrorDetail, ErrorEnvelope
from api.routers import cases, health, reconciliation

app = FastAPI(
    title="PACT API — Procurement Audit & Counterfactual Triage",
    description="High-integrity procurement audit, 3-way matching, counterfactual triage, and human review system backed by genuine IBM Db2.",
    version="1.0.0",
)

# CORS Middleware for Frontend Development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Consistent Error Envelope Handler for HTTPExceptions
@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    # If detail is already formatted with an error envelope
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)

    error_code = "HTTP_ERROR"
    if exc.status_code == 400:
        error_code = "BAD_REQUEST"
    elif exc.status_code == 404:
        error_code = "NOT_FOUND"
    elif exc.status_code == 409:
        error_code = "CONFLICT"
    elif exc.status_code == 502:
        error_code = "BAD_GATEWAY"
    elif exc.status_code == 503:
        error_code = "SERVICE_UNAVAILABLE"

    retryable = exc.status_code in (502, 503, 409)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": error_code,
                "message": str(exc.detail),
                "retryable": retryable,
            }
        },
    )


# Consistent Error Envelope Handler for 422 Request Validation Errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    msg = "; ".join(f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}" for err in errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": msg,
                "retryable": False,
            }
        },
    )


# Unhandled Internal Exceptions
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": str(exc),
                "retryable": False,
            }
        },
    )


# Include Routers
app.include_router(health.router)
app.include_router(cases.router)
app.include_router(reconciliation.router)


@app.get("/", summary="Root Index")
def root():
    return {
        "service": "PACT API",
        "description": "Procurement Audit & Counterfactual Triage backed by genuine IBM Db2",
        "docs_url": "/docs",
        "health_check": "/health/ready",
    }

