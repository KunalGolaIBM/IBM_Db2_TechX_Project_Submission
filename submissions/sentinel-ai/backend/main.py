import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database.schema import init_database_tables
from app.database.seed_data import seed_database
from app.routes import auth, dashboard, monitoring, incidents, responses

app = FastAPI(
    title=settings.APP_NAME,
    description=f"{settings.APP_TAGLINE} — Agentic AI-Powered Account Compromise Detection for Defence Networks",
    version=settings.VERSION
)

# Enable CORS for local Vite dev server and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database schema and synthetic seed data on startup
@app.on_event("startup")
def on_startup():
    init_database_tables()
    seed_database()

# Register API routes
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_PREFIX)
app.include_router(monitoring.router, prefix=settings.API_PREFIX)
app.include_router(incidents.router, prefix=settings.API_PREFIX)
app.include_router(responses.router, prefix=settings.API_PREFIX)

@app.get("/api/health")
def health_check():
    return {
        "status": "HEALTHY",
        "system": settings.APP_NAME,
        "version": settings.VERSION,
        "tagline": settings.APP_TAGLINE
    }

# Mount frontend dist static files if they exist
frontend_dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    @app.get("/")
    def serve_root():
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        file_path = os.path.join(frontend_dist_path, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

