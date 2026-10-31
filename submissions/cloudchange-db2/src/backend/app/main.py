"""CloudChange Backend API Application."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api import health, runs
from backend.app.config import settings
from backend.app.models.error import APIError

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Infrastructure change impact prediction and verification engine.",
    version=settings.VERSION,
)

# Enable CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """Handle custom application API errors with standardized error envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map FastAPI request validation errors into standardized INVALID_PAYLOAD envelope with 400 status."""
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "INVALID_PAYLOAD",
                "message": "Request payload validation failed.",
                "details": exc.errors(),
            }
        },
    )


# Mount system health and API v1 routes
app.include_router(health.router)
app.include_router(runs.router, prefix=settings.API_V1_PREFIX)
