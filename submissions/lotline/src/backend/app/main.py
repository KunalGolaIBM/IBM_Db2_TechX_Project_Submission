from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment configuration
load_dotenv()
load_dotenv("backend/.env")

from app.routers import api

app = FastAPI(
    title="LOTLINE - Agentic Recall Intelligence API",
    description="IBM Db2-backed Recall Intelligence Platform",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router)


@app.get("/")
def root():
    return {
        "brand": "LOTLINE",
        "system": "Agentic Product Recall Intelligence Platform",
        "database": "IBM Db2 12.1",
        "status": "operational"
    }
