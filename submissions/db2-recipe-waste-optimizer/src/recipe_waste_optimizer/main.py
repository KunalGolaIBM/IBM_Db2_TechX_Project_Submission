"""FastAPI Entry Point for AI-Powered Recipe & Ingredient Waste Optimizer."""
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from recipe_waste_optimizer.api.routes_inventory import router as inventory_router
from recipe_waste_optimizer.api.routes_recipes import router as recipe_router
from recipe_waste_optimizer.api.routes_recommend import router as recommend_router
from recipe_waste_optimizer.db.connection import db_manager
from recipe_waste_optimizer.config import settings

app = FastAPI(
    title="AI-Powered Recipe & Ingredient Waste Optimizer",
    description="IBM Db2 TechX Summit 2026 Submission. Intelligent household pantry optimizer and recipe generator that minimizes waste through expiry-aware deterministic ranking.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files directory
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Register API v1 sub-routers
app.include_router(inventory_router, prefix="/api/v1")
app.include_router(recipe_router, prefix="/api/v1")
app.include_router(recommend_router, prefix="/api/v1")


@app.post("/api/v1/recipes/seed_demo", tags=["System"])
def seed_demo_endpoint():
    """Trigger seed of benchmark demo pantry stock."""
    from recipe_waste_optimizer.db.repositories.inventory_repo import InventoryRepository
    from datetime import date, timedelta
    repo = InventoryRepository()
    today = date.today()
    hid = settings.DEFAULT_HOUSEHOLD_ID

    items = [
        {"name": "tomato", "quantity": 3.0, "unit": "pieces", "expiry": today + timedelta(days=1), "loc": "fridge"},
        {"name": "spinach", "quantity": 100.0, "unit": "g", "expiry": today + timedelta(days=1), "loc": "fridge"},
        {"name": "onion", "quantity": 2.0, "unit": "pieces", "expiry": today + timedelta(days=5), "loc": "pantry"},
        {"name": "potato", "quantity": 4.0, "unit": "pieces", "expiry": today + timedelta(days=7), "loc": "pantry"},
        {"name": "eggs", "quantity": 4.0, "unit": "pieces", "expiry": today + timedelta(days=10), "loc": "fridge"},
        {"name": "cooking oil", "quantity": 200.0, "unit": "ml", "expiry": today + timedelta(days=60), "loc": "pantry"},
        {"name": "garlic", "quantity": 10.0, "unit": "cloves", "expiry": today + timedelta(days=14), "loc": "pantry"},
    ]
    for it in items:
        repo.add_inventory_item(
            household_id=hid,
            ingredient_name=it["name"],
            quantity=it["quantity"],
            unit=it["unit"],
            storage_location=it["loc"],
            purchase_date=today - timedelta(days=2),
            expiry_date=it["expiry"]
        )
    return {"status": "success", "message": "Demo pantry successfully seeded into IBM Db2."}


@app.get("/health", tags=["System"])
def health_check():
    """Health status and IBM Db2 live connectivity check."""
    db_status = db_manager.test_connection()
    return {
        "status": "healthy" if db_status.get("status") == "connected" else "degraded",
        "app_env": settings.APP_ENV,
        "database": db_status,
        "llm_provider": settings.LLM_PROVIDER,
        "embedding_model": settings.EMBEDDING_MODEL
    }


@app.get("/", tags=["System"])
def root():
    """Serve the interactive web app dashboard or JSON health."""
    index_file = static_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {
        "message": "AI-Powered Recipe & Ingredient Waste Optimizer API",
        "docs": "/docs",
        "health": "/health",
        "hackathon": "IBM Db2 TechX Summit 2026"
    }


@app.get("/app", tags=["System"])
def serve_app():
    index_file = static_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return {"error": "Dashboard index.html not found"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("recipe_waste_optimizer.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=True)
