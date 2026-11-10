from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .agent import AdaptiveAgent, build_watsonx_llm
from .config import Settings
from .db import DatabaseUnavailable, Db2Client
from .models import AdaptiveSessionIn, AttemptIn, LearningProfileIn, RecommendationIn
from .repositories import Repository

settings = Settings.from_env()
db = Db2Client(settings.db2_dsn)
repo = Repository(db)
agent = AdaptiveAgent(repo, build_watsonx_llm(settings))


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        db.connect()
    except DatabaseUnavailable:
        pass
    yield
    db.close()


app = FastAPI(title="Bootcamp Runner AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["*"])


def offline() -> None:
    raise HTTPException(status_code=503, detail={"status": "offline", "message": "Db2 is unavailable"})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok" if db.connection is not None else "offline", "ai_mode": agent.mode}


@app.get("/dashboard/{learner_id}")
def dashboard(learner_id: str) -> dict:
    if not learner_id.strip():
        raise HTTPException(422, "learner_id is required")
    try:
        return {"learner": repo.get_learner(learner_id), "history": repo.get_learning_history(learner_id),
                "profile": repo.get_profile(learner_id), "recommendations": repo.get_recommendations(learner_id)}
    except DatabaseUnavailable:
        offline()


@app.post("/attempts", status_code=201)
def create_attempt(attempt: AttemptIn) -> dict:
    try:
        return repo.save_attempt(attempt)
    except DatabaseUnavailable:
        offline()


@app.get("/recommendations/{learner_id}")
def recommendations(learner_id: str, limit: int = Query(20, ge=1, le=100)) -> dict:
    try:
        return {"recommendations": repo.get_recommendations(learner_id, limit)}
    except DatabaseUnavailable:
        offline()


@app.get("/attempts/{learner_id}")
def attempts(learner_id: str, limit: int = Query(20, ge=1, le=100)) -> dict:
    try:
        return {"attempts": repo.get_learning_history(learner_id, limit)}
    except DatabaseUnavailable:
        offline()


@app.post("/profiles", status_code=201)
def create_profile(profile: LearningProfileIn) -> dict:
    try:
        return repo.save_profile(profile)
    except DatabaseUnavailable:
        offline()


@app.post("/adaptive-session")
def adaptive_session(request: AdaptiveSessionIn) -> dict:
    try:
        return agent.run(request.learner_id, request.topic, request.requested_difficulty)
    except DatabaseUnavailable:
        offline()


@app.post("/recommendations", status_code=201)
def create_recommendation(recommendation: RecommendationIn) -> dict:
    try:
        return repo.save_recommendation(recommendation)
    except DatabaseUnavailable:
        offline()
