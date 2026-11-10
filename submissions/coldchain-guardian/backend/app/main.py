from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .database.db import test_connection
from .routes.products import router as products_router
from .routes.shipments import router as shipments_router
from .routes.incidents import router as incidents_router
from .routes.recommendations import router as recommendations_router
from .routes.dashboard import router as dashboard_router
from .routes.readings import router as readings_router
from .routes.workflow import router as workflow_router
from .routes.crew import router as crew_router

app = FastAPI(
    title="ColdChain Guardian API",
    description="AI-powered cold-chain monitoring and incident management",
    version="1.0.0"
)

# CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    try:
        result = test_connection()
        print(f"Connected to Db2: {result['database_name']}")
    except Exception as exc:
        raise RuntimeError(f"Failed to connect to Db2: {exc}") from exc


@app.get("/", tags=["monitoring"])
async def root():
    return {
        "message": "Welcome to ColdChain Guardian API",
        "status": "running"
    }


@app.get("/health", tags=["monitoring"])
async def health_check():
    try:
        result = test_connection()
        return {
            "status": "healthy",
            "database": result["database_name"],
            "db2_status": result["status"]
        }
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable"
        )


app.include_router(products_router)
app.include_router(shipments_router)
app.include_router(incidents_router)
app.include_router(recommendations_router)
app.include_router(dashboard_router)
app.include_router(readings_router)
app.include_router(workflow_router)
app.include_router(crew_router)
