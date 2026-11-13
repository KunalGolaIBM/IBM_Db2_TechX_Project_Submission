"""
backend/main.py
---------------
FastAPI REST API for Mood-to-Music Memory.
Bridges the React frontend to IBM Db2 (schema: MOODMUSIC).

Start:
    cd d:\\mood-to-music-memory
    .venv\\Scripts\\uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations
import os
import sys
from datetime import datetime
from typing import Optional

import ibm_db
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Allow running from project root
sys.path.insert(0, str(os.path.dirname(os.path.dirname(__file__))))

from backend.db import SCHEMA, exec_sql, exec_immediate, fetch_all, fetch_one, get_conn

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Mood-to-Music Memory API",
    description="IBM Db2-backed REST API for the Mood-to-Music Memory app",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve downloaded music files statically
MUSIC_DIR = os.getenv("MUSIC_DIR", r"d:\mood-to-music-memory\music")
if os.path.isdir(MUSIC_DIR):
    app.mount("/music", StaticFiles(directory=MUSIC_DIR), name="music")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class MemoryCreate(BaseModel):
    memory_text: str
    song_title: str
    artist: str
    mood_tag: str
    saved_at: Optional[str] = None  # ISO timestamp; defaults to NOW

class MemoryUpdate(BaseModel):
    memory_text: Optional[str] = None
    mood_tag: Optional[str] = None

class SessionStart(BaseModel):
    mood_code: str

class SessionEnd(BaseModel):
    session_id: int
    feedback: Optional[str] = None

class ImportSong(BaseModel):
    song_title: str
    artist: str
    album: Optional[str] = ""
    local_file_path: str
    duration_seconds: Optional[int] = None
    mood_code: str  # used to find the right playlist


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    try:
        stmt = exec_immediate(
            "SELECT CURRENT SERVER, CURRENT TIMESTAMP FROM SYSIBM.SYSDUMMY1"
        )
        row = fetch_one(stmt)
        return {"status": "ok", "db2": row}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Db2 unreachable: {exc}")


# ---------------------------------------------------------------------------
# Moods
# ---------------------------------------------------------------------------

@app.get("/api/moods")
def get_moods():
    stmt = exec_sql(
        f"SELECT MOOD_ID, MOOD_CODE, DISPLAY_NAME, DESCRIPTION "
        f"FROM {SCHEMA}.MOODS ORDER BY DISPLAY_NAME"
    )
    return fetch_all(stmt)


# ---------------------------------------------------------------------------
# Songs
# ---------------------------------------------------------------------------

@app.get("/api/songs")
def get_songs(mood: Optional[str] = Query(None)):
    """
    Return all songs, optionally filtered by mood code.
    Each row includes playlist and mood info via JOIN.
    """
    if mood:
        sql = f"""
            SELECT DISTINCT
                s.SONG_ID,
                s.SONG_TITLE,
                s.ARTIST,
                s.ALBUM,
                s.LOCAL_FILE_PATH,
                s.DURATION_SECONDS,
                s.CREATED_AT,
                m.MOOD_CODE,
                m.DISPLAY_NAME AS MOOD_DISPLAY,
                pl.PLAYLIST_NAME
            FROM {SCHEMA}.SONGS s
            JOIN {SCHEMA}.PLAYLIST_SONGS ps ON s.SONG_ID = ps.SONG_ID
            JOIN {SCHEMA}.PLAYLISTS pl ON ps.PLAYLIST_ID = pl.PLAYLIST_ID
            JOIN {SCHEMA}.MOOD_PLAYLISTS mp ON pl.PLAYLIST_ID = mp.PLAYLIST_ID
            JOIN {SCHEMA}.MOODS m ON mp.MOOD_ID = m.MOOD_ID
            WHERE LOWER(m.MOOD_CODE) = LOWER(?)
            ORDER BY ps.POSITION ASC
        """
        stmt = exec_sql(sql, (mood,))
    else:
        sql = f"""
            SELECT DISTINCT
                s.SONG_ID,
                s.SONG_TITLE,
                s.ARTIST,
                s.ALBUM,
                s.LOCAL_FILE_PATH,
                s.DURATION_SECONDS,
                s.CREATED_AT,
                m.MOOD_CODE,
                m.DISPLAY_NAME AS MOOD_DISPLAY,
                pl.PLAYLIST_NAME
            FROM {SCHEMA}.SONGS s
            LEFT JOIN {SCHEMA}.PLAYLIST_SONGS ps ON s.SONG_ID = ps.SONG_ID
            LEFT JOIN {SCHEMA}.PLAYLISTS pl ON ps.PLAYLIST_ID = pl.PLAYLIST_ID
            LEFT JOIN {SCHEMA}.MOOD_PLAYLISTS mp ON pl.PLAYLIST_ID = mp.PLAYLIST_ID
            LEFT JOIN {SCHEMA}.MOODS m ON mp.MOOD_ID = m.MOOD_ID
            ORDER BY s.CREATED_AT DESC
        """
        stmt = exec_sql(sql)
    rows = fetch_all(stmt)
    # Normalise keys to camelCase for the React frontend
    return [_normalise_song(r) for r in rows]


def _normalise_song(r: dict) -> dict:
    """Convert Db2 uppercase keys + add a playable URL."""
    file_path = r.get("LOCAL_FILE_PATH") or ""
    filename = os.path.basename(file_path) if file_path else ""
    file_exists = os.path.isfile(file_path)
    return {
        "id": str(r.get("SONG_ID", "")),
        "title": r.get("SONG_TITLE", ""),
        "artist": r.get("ARTIST", ""),
        "album": r.get("ALBUM") or "",
        "duration": _fmt_duration(r.get("DURATION_SECONDS")),
        "durationSeconds": r.get("DURATION_SECONDS"),
        "mood": (r.get("MOOD_CODE") or "").lower(),
        "moodDisplay": r.get("MOOD_DISPLAY") or "",
        "playlist": r.get("PLAYLIST_NAME") or "",
        "localFilePath": file_path,
        "audioUrl": f"/music/{filename}" if (filename and file_exists) else None,
    }


def _fmt_duration(secs) -> str:
    if secs is None:
        return "0:00"
    secs = int(secs)
    return f"{secs // 60}:{secs % 60:02d}"


# ---------------------------------------------------------------------------
# Playlists
# ---------------------------------------------------------------------------

@app.get("/api/playlists")
def get_playlists():
    sql = f"""
        SELECT
            pl.PLAYLIST_ID,
            pl.PLAYLIST_NAME,
            pl.DESCRIPTION,
            m.MOOD_CODE,
            m.DISPLAY_NAME AS MOOD_DISPLAY,
            pp.VOLUME_PERCENT,
            pp.SPEED_MULTIPLIER,
            COUNT(ps.SONG_ID) AS SONG_COUNT
        FROM {SCHEMA}.PLAYLISTS pl
        JOIN {SCHEMA}.MOOD_PLAYLISTS mp ON pl.PLAYLIST_ID = mp.PLAYLIST_ID
        JOIN {SCHEMA}.MOODS m ON mp.MOOD_ID = m.MOOD_ID
        JOIN {SCHEMA}.PLAYBACK_PROFILES pp ON pl.PROFILE_ID = pp.PROFILE_ID
        LEFT JOIN {SCHEMA}.PLAYLIST_SONGS ps ON pl.PLAYLIST_ID = ps.PLAYLIST_ID
        WHERE pl.IS_ACTIVE = 'Y'
        GROUP BY pl.PLAYLIST_ID, pl.PLAYLIST_NAME, pl.DESCRIPTION,
                 m.MOOD_CODE, m.DISPLAY_NAME, pp.VOLUME_PERCENT, pp.SPEED_MULTIPLIER
        ORDER BY m.DISPLAY_NAME
    """
    stmt = exec_sql(sql)
    rows = fetch_all(stmt)
    return [
        {
            "id": str(r["PLAYLIST_ID"]),
            "name": r["PLAYLIST_NAME"],
            "description": r.get("DESCRIPTION") or "",
            "mood": (r.get("MOOD_CODE") or "").lower(),
            "moodDisplay": r.get("MOOD_DISPLAY") or "",
            "songCount": int(r.get("SONG_COUNT") or 0),
            "volume": int(r.get("VOLUME_PERCENT") or 80),
        }
        for r in rows
    ]


@app.get("/api/playlists/{playlist_id}/songs")
def get_playlist_songs(playlist_id: int):
    sql = f"""
        SELECT
            s.SONG_ID, s.SONG_TITLE, s.ARTIST, s.ALBUM,
            s.LOCAL_FILE_PATH, s.DURATION_SECONDS, ps.POSITION
        FROM {SCHEMA}.PLAYLIST_SONGS ps
        JOIN {SCHEMA}.SONGS s ON ps.SONG_ID = s.SONG_ID
        WHERE ps.PLAYLIST_ID = ?
        ORDER BY ps.POSITION ASC
    """
    stmt = exec_sql(sql, (playlist_id,))
    rows = fetch_all(stmt)
    return [_normalise_song(r) for r in rows]


# ---------------------------------------------------------------------------
# Memories
# ---------------------------------------------------------------------------

@app.get("/api/memories")
def get_memories(mood: Optional[str] = Query(None)):
    if mood:
        sql = (
            f"SELECT MEMORY_ID, MEMORY_TEXT, SONG_TITLE, ARTIST, MOOD_TAG, SAVED_AT, CREATED_AT "
            f"FROM {SCHEMA}.MEMORIES WHERE LOWER(MOOD_TAG) = LOWER(?) ORDER BY SAVED_AT DESC"
        )
        stmt = exec_sql(sql, (mood,))
    else:
        sql = (
            f"SELECT MEMORY_ID, MEMORY_TEXT, SONG_TITLE, ARTIST, MOOD_TAG, SAVED_AT, CREATED_AT "
            f"FROM {SCHEMA}.MEMORIES ORDER BY SAVED_AT DESC"
        )
        stmt = exec_sql(sql)
    return [_normalise_memory(r) for r in fetch_all(stmt)]


@app.post("/api/memories", status_code=201)
def create_memory(body: MemoryCreate):
    saved_at = body.saved_at or datetime.utcnow().isoformat()
    sql = (
        f"INSERT INTO {SCHEMA}.MEMORIES "
        f"(MEMORY_TEXT, SONG_TITLE, ARTIST, MOOD_TAG, SAVED_AT) "
        f"VALUES (?, ?, ?, ?, ?)"
    )
    exec_sql(sql, (body.memory_text, body.song_title, body.artist, body.mood_tag, saved_at))

    # Fetch inserted record
    stmt = exec_sql(
        f"SELECT MEMORY_ID, MEMORY_TEXT, SONG_TITLE, ARTIST, MOOD_TAG, SAVED_AT, CREATED_AT "
        f"FROM {SCHEMA}.MEMORIES WHERE SONG_TITLE = ? AND ARTIST = ? "
        f"ORDER BY CREATED_AT DESC FETCH FIRST 1 ROWS ONLY",
        (body.song_title, body.artist),
    )
    row = fetch_one(stmt)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to retrieve inserted memory")

    # Optionally store embedding via AI module
    _try_embed_memory(body.memory_text, body.song_title, body.artist, body.mood_tag)

    return _normalise_memory(row)


@app.put("/api/memories/{memory_id}")
def update_memory(memory_id: int, body: MemoryUpdate):
    updates = []
    params = []
    if body.memory_text is not None:
        updates.append("MEMORY_TEXT = ?")
        params.append(body.memory_text)
    if body.mood_tag is not None:
        updates.append("MOOD_TAG = ?")
        params.append(body.mood_tag)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    params.append(memory_id)
    sql = f"UPDATE {SCHEMA}.MEMORIES SET {', '.join(updates)} WHERE MEMORY_ID = ?"
    exec_sql(sql, tuple(params))
    return {"ok": True, "memory_id": memory_id}


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int):
    exec_sql(f"DELETE FROM {SCHEMA}.MEMORIES WHERE MEMORY_ID = ?", (memory_id,))
    return {"ok": True}


@app.get("/api/memories/{memory_id}/similar")
def similar_memories(memory_id: int, k: int = 3):
    """Return k memories semantically similar to the given memory."""
    stmt = exec_sql(
        f"SELECT MEMORY_TEXT FROM {SCHEMA}.MEMORIES WHERE MEMORY_ID = ?",
        (memory_id,),
    )
    row = fetch_one(stmt)
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")

    query_text = row["MEMORY_TEXT"]
    try:
        from src.ai.memory_search import MemorySearch
        ms = MemorySearch()
        docs = ms.search(query_text, k=k + 1)  # +1 to exclude self
        results = []
        for doc in docs:
            if doc.page_content != query_text:
                results.append({
                    "text": doc.page_content,
                    "song_title": doc.metadata.get("song_title", ""),
                    "artist": doc.metadata.get("artist", ""),
                    "mood_tag": doc.metadata.get("mood_tag", ""),
                })
        return results[:k]
    except Exception:
        # Fallback: return most recent other memories with same mood
        stmt2 = exec_sql(
            f"SELECT MEMORY_ID, MEMORY_TEXT, SONG_TITLE, ARTIST, MOOD_TAG, SAVED_AT, CREATED_AT "
            f"FROM {SCHEMA}.MEMORIES WHERE MEMORY_ID <> ? "
            f"ORDER BY SAVED_AT DESC FETCH FIRST ? ROWS ONLY",
            (memory_id, k),
        )
        return [_normalise_memory(r) for r in fetch_all(stmt2)]


def _normalise_memory(r: dict) -> dict:
    return {
        "id": str(r.get("MEMORY_ID", "")),
        "text": r.get("MEMORY_TEXT", ""),
        "songTitle": r.get("SONG_TITLE", ""),
        "artist": r.get("ARTIST", ""),
        "moodTag": (r.get("MOOD_TAG") or "").lower(),
        "savedAt": str(r.get("SAVED_AT") or ""),
        "createdAt": str(r.get("CREATED_AT") or ""),
    }


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

@app.post("/api/session/start", status_code=201)
def session_start(body: SessionStart):
    """Start a new playback session. Returns session_id."""
    # Get mood_id
    stmt = exec_sql(
        f"SELECT MOOD_ID FROM {SCHEMA}.MOODS WHERE LOWER(MOOD_CODE) = LOWER(?)",
        (body.mood_code,),
    )
    mood_row = fetch_one(stmt)
    if not mood_row:
        raise HTTPException(status_code=404, detail=f"Mood not found: {body.mood_code}")
    mood_id = mood_row["MOOD_ID"]

    # Get playlist_id
    stmt2 = exec_sql(
        f"""
        SELECT pl.PLAYLIST_ID
        FROM {SCHEMA}.MOOD_PLAYLISTS mp
        JOIN {SCHEMA}.PLAYLISTS pl ON mp.PLAYLIST_ID = pl.PLAYLIST_ID
        WHERE mp.MOOD_ID = ? AND pl.IS_ACTIVE = 'Y'
        ORDER BY mp.PRIORITY ASC FETCH FIRST 1 ROWS ONLY
        """,
        (mood_id,),
    )
    pl_row = fetch_one(stmt2)
    if not pl_row:
        raise HTTPException(status_code=404, detail=f"No playlist for mood: {body.mood_code}")
    playlist_id = pl_row["PLAYLIST_ID"]

    # Insert session
    exec_sql(
        f"INSERT INTO {SCHEMA}.PLAYBACK_SESSIONS (MOOD_ID, PLAYLIST_ID) VALUES (?, ?)",
        (mood_id, playlist_id),
    )

    # Get session ID
    stmt3 = exec_sql(
        f"SELECT SESSION_ID FROM {SCHEMA}.PLAYBACK_SESSIONS "
        f"WHERE MOOD_ID = ? AND PLAYLIST_ID = ? "
        f"ORDER BY STARTED_AT DESC FETCH FIRST 1 ROWS ONLY",
        (mood_id, playlist_id),
    )
    sess_row = fetch_one(stmt3)
    session_id = sess_row["SESSION_ID"] if sess_row else -1
    return {"session_id": session_id, "mood_id": mood_id, "playlist_id": playlist_id}


@app.post("/api/session/end")
def session_end(body: SessionEnd):
    exec_sql(
        f"UPDATE {SCHEMA}.PLAYBACK_SESSIONS "
        f"SET ENDED_AT = CURRENT TIMESTAMP, FEEDBACK = ? "
        f"WHERE SESSION_ID = ?",
        (body.feedback, body.session_id),
    )
    return {"ok": True}


# ---------------------------------------------------------------------------
# AI — Mood detection
# ---------------------------------------------------------------------------

@app.post("/api/detect-mood")
def detect_mood(payload: dict):
    """
    POST { "text": "I feel nostalgic and a bit low" }
    Returns { "mood_code": "sad", "source": "ai" | "fallback" }
    """
    text = (payload.get("text") or "").strip()
    if not text:
        return {"mood_code": "happy", "source": "fallback"}
    try:
        from src.ai.mood_interpreter import MoodInterpreter
        interp = MoodInterpreter()
        code = interp.interpret(text)
        return {"mood_code": code, "source": "ai"}
    except Exception as exc:
        return {"mood_code": "happy", "source": "fallback", "error": str(exc)}


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

@app.get("/api/analytics")
def analytics():
    """Return aggregated listening analytics from Db2."""
    conn = get_conn()

    # Total sessions
    stmt = exec_immediate(
        f"SELECT COUNT(*) FROM {SCHEMA}.PLAYBACK_SESSIONS"
    )
    total_sessions = ibm_db.fetch_tuple(stmt)[0] or 0

    # Total memories
    stmt = exec_immediate(
        f"SELECT COUNT(*) FROM {SCHEMA}.MEMORIES"
    )
    total_memories = ibm_db.fetch_tuple(stmt)[0] or 0

    # Total songs
    stmt = exec_immediate(
        f"SELECT COUNT(*) FROM {SCHEMA}.SONGS"
    )
    total_songs = ibm_db.fetch_tuple(stmt)[0] or 0

    # Mood distribution
    stmt = exec_sql(
        f"""
        SELECT m.MOOD_CODE, m.DISPLAY_NAME, COUNT(ps.SESSION_ID) AS SESSION_COUNT
        FROM {SCHEMA}.MOODS m
        LEFT JOIN {SCHEMA}.PLAYBACK_SESSIONS ps ON m.MOOD_ID = ps.MOOD_ID
        GROUP BY m.MOOD_ID, m.MOOD_CODE, m.DISPLAY_NAME
        ORDER BY SESSION_COUNT DESC
        """
    )
    mood_dist = fetch_all(stmt)

    # Most played mood
    most_played_mood = (mood_dist[0].get("DISPLAY_NAME") or "—") if mood_dist else "—"

    # Recent sessions (last 7)
    stmt = exec_sql(
        f"""
        SELECT
            ps.SESSION_ID,
            m.MOOD_CODE,
            m.DISPLAY_NAME AS MOOD_DISPLAY,
            ps.STARTED_AT,
            ps.ENDED_AT,
            ps.FEEDBACK
        FROM {SCHEMA}.PLAYBACK_SESSIONS ps
        JOIN {SCHEMA}.MOODS m ON ps.MOOD_ID = m.MOOD_ID
        ORDER BY ps.STARTED_AT DESC FETCH FIRST 10 ROWS ONLY
        """
    )
    recent_sessions = fetch_all(stmt)

    # Top songs by playlist appearance
    stmt = exec_sql(
        f"""
        SELECT s.SONG_TITLE, s.ARTIST, COUNT(ps.PLAYLIST_ID) AS APPEARANCES
        FROM {SCHEMA}.SONGS s
        JOIN {SCHEMA}.PLAYLIST_SONGS ps ON s.SONG_ID = ps.SONG_ID
        GROUP BY s.SONG_ID, s.SONG_TITLE, s.ARTIST
        ORDER BY APPEARANCES DESC
        FETCH FIRST 5 ROWS ONLY
        """
    )
    top_songs = fetch_all(stmt)

    return {
        "totalSessions": int(total_sessions),
        "totalMemories": int(total_memories),
        "totalSongs": int(total_songs),
        "mostPlayedMood": most_played_mood,
        "moodDistribution": [
            {
                "mood": r.get("MOOD_CODE", "").lower(),
                "moodDisplay": r.get("DISPLAY_NAME") or "",
                "count": int(r.get("SESSION_COUNT") or 0),
            }
            for r in mood_dist
        ],
        "recentSessions": [
            {
                "sessionId": r.get("SESSION_ID"),
                "mood": (r.get("MOOD_CODE") or "").lower(),
                "moodDisplay": r.get("MOOD_DISPLAY") or "",
                "startedAt": str(r.get("STARTED_AT") or ""),
                "endedAt": str(r.get("ENDED_AT") or ""),
                "feedback": r.get("FEEDBACK") or "",
            }
            for r in recent_sessions
        ],
        "topSongs": [
            {
                "title": r.get("SONG_TITLE", ""),
                "artist": r.get("ARTIST", ""),
                "appearances": int(r.get("APPEARANCES") or 0),
            }
            for r in top_songs
        ],
    }


# ---------------------------------------------------------------------------
# Song import (manual / from Library page)
# ---------------------------------------------------------------------------

@app.post("/api/songs/import", status_code=201)
def import_song(body: ImportSong):
    """
    Register a locally-available song file into Db2 and add it
    to the appropriate mood playlist.
    """
    # Insert song
    sql = (
        f"INSERT INTO {SCHEMA}.SONGS "
        f"(SONG_TITLE, ARTIST, ALBUM, LOCAL_FILE_PATH, DURATION_SECONDS) "
        f"VALUES (?, ?, ?, ?, ?)"
    )
    exec_sql(sql, (body.song_title, body.artist, body.album or "", body.local_file_path, body.duration_seconds))

    # Get song_id
    stmt = exec_sql(
        f"SELECT SONG_ID FROM {SCHEMA}.SONGS WHERE LOCAL_FILE_PATH = ? "
        f"ORDER BY CREATED_AT DESC FETCH FIRST 1 ROWS ONLY",
        (body.local_file_path,),
    )
    row = fetch_one(stmt)
    if not row:
        raise HTTPException(status_code=500, detail="Song inserted but ID not found")
    song_id = row["SONG_ID"]

    # Find playlist for this mood
    stmt2 = exec_sql(
        f"""
        SELECT pl.PLAYLIST_ID
        FROM {SCHEMA}.MOOD_PLAYLISTS mp
        JOIN {SCHEMA}.PLAYLISTS pl ON mp.PLAYLIST_ID = pl.PLAYLIST_ID
        JOIN {SCHEMA}.MOODS m ON mp.MOOD_ID = m.MOOD_ID
        WHERE LOWER(m.MOOD_CODE) = LOWER(?) AND pl.IS_ACTIVE = 'Y'
        ORDER BY mp.PRIORITY ASC FETCH FIRST 1 ROWS ONLY
        """,
        (body.mood_code,),
    )
    pl_row = fetch_one(stmt2)
    if pl_row:
        playlist_id = pl_row["PLAYLIST_ID"]
        # Get next position
        stmt3 = exec_sql(
            f"SELECT COALESCE(MAX(POSITION), 0) + 1 FROM {SCHEMA}.PLAYLIST_SONGS WHERE PLAYLIST_ID = ?",
            (playlist_id,),
        )
        pos_row = ibm_db.fetch_tuple(exec_sql(
            f"SELECT COALESCE(MAX(POSITION), 0) + 1 FROM {SCHEMA}.PLAYLIST_SONGS WHERE PLAYLIST_ID = ?",
            (playlist_id,),
        ))
        position = pos_row[0] if pos_row else 1
        exec_sql(
            f"INSERT INTO {SCHEMA}.PLAYLIST_SONGS (PLAYLIST_ID, SONG_ID, POSITION) VALUES (?, ?, ?)",
            (playlist_id, song_id, position),
        )

    return {"song_id": song_id, "title": body.song_title, "artist": body.artist}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _try_embed_memory(text: str, song_title: str, artist: str, mood_tag: str) -> None:
    """Best-effort: embed memory and store in Db2 vector store."""
    try:
        from src.ai.memory_search import MemorySearch
        ms = MemorySearch()
        ms.add_memory(text, song_title, artist, mood_tag)
    except Exception:
        pass  # Vector store is optional


# ---------------------------------------------------------------------------
# Entry point (direct run)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

