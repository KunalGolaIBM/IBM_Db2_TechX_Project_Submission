from __future__ import annotations

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .agent import GameAssistant
from .config import Settings
from .db import DatabaseError, DatabaseUnavailable, Db2Client
from .models import *
from .repositories import Repository, SessionOwnershipError

settings = Settings.from_env()
db = Db2Client(settings.db2_dsn)
repo = Repository(db)
assistant = GameAssistant(repo, settings.watsonx_llm())

@asynccontextmanager
async def lifespan(_: FastAPI):
    try: db.connect()
    except DatabaseUnavailable: pass
    yield
    db.close()

app = FastAPI(title="Bootcamp Runner AI CEO Edition", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_credentials=True,
                   allow_methods=["GET", "POST"], allow_headers=["*"])

def offline() -> None:
    raise HTTPException(status_code=503, detail={"status": "offline", "message": "Db2 is unavailable"})

def call(fn):
    try:
        return fn()
    except SessionOwnershipError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DatabaseUnavailable: offline()
    except DatabaseError as exc:
        raise HTTPException(
            status_code=500,
            detail={"status": "error", "message": "Database operation failed"},
        ) from exc

@app.get("/health", response_model=None)
def health() -> dict[str, str] | JSONResponse:
    ai_mode = assistant.mode
    if db.connection is None:
        return JSONResponse(
            status_code=503,
            content={"status": "offline", "database": "unavailable", "ai_mode": ai_mode},
        )
    try:
        db.execute("SELECT 1 FROM SYSIBM.SYSDUMMY1")
    except DatabaseUnavailable:
        return JSONResponse(
            status_code=503,
            content={"status": "offline", "database": "unavailable", "ai_mode": ai_mode},
        )
    return {"status": "ok", "database": "connected", "ai_mode": ai_mode}

@app.get("/players/{player_id}/profile")
def profile(player_id: str): return call(lambda: repo.get_profile(player_id))

@app.post("/players/profile", status_code=201)
def save_profile(item: PlayerProfileIn): return call(lambda: repo.save_profile(item))

@app.post("/game/sessions", status_code=201)
def create_session(item: GameSessionIn): return call(lambda: repo.create_session(item))

@app.post("/game/scores", status_code=201)
def save_score(item: ScoreIn): return call(lambda: repo.save_score(item))

@app.get("/players/{player_id}/scores")
def scores(player_id: str, limit: int = Query(20, ge=1, le=100)): return call(lambda: {"scores": repo.list_scores(player_id, limit)})

@app.post("/characters/unlock", status_code=201)
def unlock_character(item: CharacterUnlockIn): return call(lambda: repo.unlock_character(item))

@app.get("/players/{player_id}/characters")
def characters(player_id: str): return call(lambda: {"characters": repo.list_characters(player_id)})

@app.post("/achievements", status_code=201)
def save_achievement(item: AchievementIn): return call(lambda: repo.save_achievement(item))

@app.get("/players/{player_id}/achievements")
def achievements(player_id: str): return call(lambda: {"achievements": repo.list_achievements(player_id)})

@app.post("/missions", status_code=201)
def save_mission(item: MissionIn): return call(lambda: repo.save_mission(item))

@app.get("/players/{player_id}/missions")
def missions(player_id: str): return call(lambda: {"missions": repo.list_missions(player_id)})

@app.get("/leaderboard")
def leaderboard(limit: int = Query(20, ge=1, le=100)): return call(lambda: {"leaderboard": repo.leaderboard(limit)})

@app.post("/assistant/challenge")
def challenge(item: AdaptiveChallengeRequest): return call(lambda: assistant.run(item))

@app.post("/assistant")
def assistant_route(item: AssistantRequest): return call(lambda: assistant.run(item))
