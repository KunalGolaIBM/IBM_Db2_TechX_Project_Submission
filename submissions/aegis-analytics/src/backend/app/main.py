from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router
from backend.app.api.db2_routes import router as db2_router
from backend.app.core.config import load_settings
from backend.app.services.storage import init_db

settings = load_settings()
init_db(settings.data_db_path)

app = FastAPI(title="Aegis Analytics AI")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(db2_router)
