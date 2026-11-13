"""
src/db/queries.py
-----------------
All parameterised SQL helpers for the Mood-to-Music Memory app.
Every query uses ibm_db.prepare + ibm_db.execute with ? markers —
never string interpolation with user-supplied values.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import ibm_db

SCHEMA = "MOODMUSIC"


# ---------------------------------------------------------------------------
# Data models (plain dataclasses — no ORM needed)
# ---------------------------------------------------------------------------

@dataclass
class Mood:
    mood_id: int
    mood_code: str
    display_name: str
    description: str


@dataclass
class PlaybackProfile:
    profile_id: int
    profile_code: str
    volume_percent: int
    speed_multiplier: float
    fade_in_seconds: int


@dataclass
class Playlist:
    playlist_id: int
    playlist_name: str
    description: str
    profile: PlaybackProfile


@dataclass
class Song:
    song_id: int
    song_title: str
    artist: str
    album: Optional[str]
    local_file_path: str
    duration_seconds: Optional[int]
    position: int  # order within the playlist


# ---------------------------------------------------------------------------
# Mood queries
# ---------------------------------------------------------------------------

def get_all_moods(conn) -> list[Mood]:
    """Return all active moods ordered by display name."""
    stmt = ibm_db.exec_immediate(
        conn,
        f"SELECT MOOD_ID, MOOD_CODE, DISPLAY_NAME, DESCRIPTION "
        f"FROM {SCHEMA}.MOODS ORDER BY DISPLAY_NAME",
    )
    moods: list[Mood] = []
    row = ibm_db.fetch_tuple(stmt)
    while row:
        moods.append(Mood(*row))
        row = ibm_db.fetch_tuple(stmt)
    return moods


def get_mood_by_code(conn, mood_code: str) -> Optional[Mood]:
    """Fetch a single mood by its code (e.g. 'sad')."""
    sql = (
        f"SELECT MOOD_ID, MOOD_CODE, DISPLAY_NAME, DESCRIPTION "
        f"FROM {SCHEMA}.MOODS WHERE MOOD_CODE = ?"
    )
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, mood_code)
    ibm_db.execute(stmt)
    row = ibm_db.fetch_tuple(stmt)
    return Mood(*row) if row else None


# ---------------------------------------------------------------------------
# Playlist + profile queries
# ---------------------------------------------------------------------------

def get_playlist_for_mood(conn, mood_id: int) -> Optional[Playlist]:
    """
    Return the highest-priority active playlist for a mood,
    including its playback profile.
    """
    sql = f"""
        SELECT
            pl.PLAYLIST_ID,
            pl.PLAYLIST_NAME,
            pl.DESCRIPTION,
            pp.PROFILE_ID,
            pp.PROFILE_CODE,
            pp.VOLUME_PERCENT,
            pp.SPEED_MULTIPLIER,
            pp.FADE_IN_SECONDS
        FROM {SCHEMA}.MOOD_PLAYLISTS mp
        JOIN {SCHEMA}.PLAYLISTS pl
            ON mp.PLAYLIST_ID = pl.PLAYLIST_ID
        JOIN {SCHEMA}.PLAYBACK_PROFILES pp
            ON pl.PROFILE_ID = pp.PROFILE_ID
        WHERE mp.MOOD_ID = ?
          AND pl.IS_ACTIVE = 'Y'
        ORDER BY mp.PRIORITY ASC
        FETCH FIRST 1 ROWS ONLY
    """
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, mood_id)
    ibm_db.execute(stmt)
    row = ibm_db.fetch_tuple(stmt)
    if not row:
        return None
    pl_id, pl_name, pl_desc, pr_id, pr_code, vol, speed, fade = row
    profile = PlaybackProfile(pr_id, pr_code, vol, float(speed), fade)
    return Playlist(pl_id, pl_name, pl_desc or "", profile)


# ---------------------------------------------------------------------------
# Song queries
# ---------------------------------------------------------------------------

def get_songs_for_playlist(conn, playlist_id: int) -> list[Song]:
    """Return ordered songs for a playlist."""
    sql = f"""
        SELECT
            s.SONG_ID,
            s.SONG_TITLE,
            s.ARTIST,
            s.ALBUM,
            s.LOCAL_FILE_PATH,
            s.DURATION_SECONDS,
            ps.POSITION
        FROM {SCHEMA}.PLAYLIST_SONGS ps
        JOIN {SCHEMA}.SONGS s ON ps.SONG_ID = s.SONG_ID
        WHERE ps.PLAYLIST_ID = ?
        ORDER BY ps.POSITION ASC
    """
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, playlist_id)
    ibm_db.execute(stmt)
    songs: list[Song] = []
    row = ibm_db.fetch_tuple(stmt)
    while row:
        songs.append(Song(*row))
        row = ibm_db.fetch_tuple(stmt)
    return songs


def insert_song(conn, title: str, artist: str, album: str,
                file_path: str, duration: Optional[int]) -> int:
    """Insert a new song and return its SONG_ID."""
    sql = (
        f"INSERT INTO {SCHEMA}.SONGS "
        f"(SONG_TITLE, ARTIST, ALBUM, LOCAL_FILE_PATH, DURATION_SECONDS) "
        f"VALUES (?, ?, ?, ?, ?)"
    )
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, title)
    ibm_db.bind_param(stmt, 2, artist)
    ibm_db.bind_param(stmt, 3, album)
    ibm_db.bind_param(stmt, 4, file_path)
    ibm_db.bind_param(stmt, 5, duration)
    ibm_db.execute(stmt)

    # Fetch the generated ID
    id_stmt = ibm_db.exec_immediate(
        conn,
        f"SELECT SONG_ID FROM {SCHEMA}.SONGS "
        f"WHERE LOCAL_FILE_PATH = '{file_path}' "
        f"ORDER BY CREATED_AT DESC FETCH FIRST 1 ROWS ONLY",
    )
    row = ibm_db.fetch_tuple(id_stmt)
    return row[0] if row else -1


def add_song_to_playlist(conn, playlist_id: int, song_id: int, position: int) -> None:
    """Link a song to a playlist at a given position."""
    sql = (
        f"INSERT INTO {SCHEMA}.PLAYLIST_SONGS (PLAYLIST_ID, SONG_ID, POSITION) "
        f"VALUES (?, ?, ?)"
    )
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, playlist_id)
    ibm_db.bind_param(stmt, 2, song_id)
    ibm_db.bind_param(stmt, 3, position)
    ibm_db.execute(stmt)


# ---------------------------------------------------------------------------
# Session tracking
# ---------------------------------------------------------------------------

def start_session(conn, mood_id: int, playlist_id: int) -> int:
    """Insert a new playback session and return its SESSION_ID."""
    sql = (
        f"INSERT INTO {SCHEMA}.PLAYBACK_SESSIONS (MOOD_ID, PLAYLIST_ID) "
        f"VALUES (?, ?)"
    )
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, mood_id)
    ibm_db.bind_param(stmt, 2, playlist_id)
    ibm_db.execute(stmt)

    id_stmt = ibm_db.exec_immediate(
        conn,
        f"SELECT SESSION_ID FROM {SCHEMA}.PLAYBACK_SESSIONS "
        f"WHERE MOOD_ID = {mood_id} AND PLAYLIST_ID = {playlist_id} "
        f"ORDER BY STARTED_AT DESC FETCH FIRST 1 ROWS ONLY",
    )
    row = ibm_db.fetch_tuple(id_stmt)
    return row[0] if row else -1


def end_session(conn, session_id: int, feedback: Optional[str] = None) -> None:
    """Mark session as ended with optional feedback."""
    sql = (
        f"UPDATE {SCHEMA}.PLAYBACK_SESSIONS "
        f"SET ENDED_AT = CURRENT TIMESTAMP, FEEDBACK = ? "
        f"WHERE SESSION_ID = ?"
    )
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, feedback)
    ibm_db.bind_param(stmt, 2, session_id)
    ibm_db.execute(stmt)


# ---------------------------------------------------------------------------
# Memory queries
# ---------------------------------------------------------------------------

def save_memory(conn, text: str, song_title: str, artist: str,
                mood_tag: str, saved_at: str) -> int:
    """Insert a music memory and return its MEMORY_ID."""
    sql = (
        f"INSERT INTO {SCHEMA}.MEMORIES "
        f"(MEMORY_TEXT, SONG_TITLE, ARTIST, MOOD_TAG, SAVED_AT) "
        f"VALUES (?, ?, ?, ?, ?)"
    )
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, text)
    ibm_db.bind_param(stmt, 2, song_title)
    ibm_db.bind_param(stmt, 3, artist)
    ibm_db.bind_param(stmt, 4, mood_tag)
    ibm_db.bind_param(stmt, 5, saved_at)
    ibm_db.execute(stmt)

    id_stmt = ibm_db.exec_immediate(
        conn,
        f"SELECT MEMORY_ID FROM {SCHEMA}.MEMORIES "
        f"WHERE SONG_TITLE = '{song_title}' AND ARTIST = '{artist}' "
        f"ORDER BY CREATED_AT DESC FETCH FIRST 1 ROWS ONLY",
    )
    row = ibm_db.fetch_tuple(id_stmt)
    return row[0] if row else -1


def get_memories_by_mood(conn, mood_tag: str) -> list[dict]:
    """Fetch all memories for a mood tag."""
    sql = (
        f"SELECT MEMORY_ID, MEMORY_TEXT, SONG_TITLE, ARTIST, MOOD_TAG, SAVED_AT "
        f"FROM {SCHEMA}.MEMORIES WHERE MOOD_TAG = ? ORDER BY SAVED_AT DESC"
    )
    stmt = ibm_db.prepare(conn, sql)
    ibm_db.bind_param(stmt, 1, mood_tag)
    ibm_db.execute(stmt)
    results = []
    row = ibm_db.fetch_assoc(stmt)
    while row:
        results.append(dict(row))
        row = ibm_db.fetch_assoc(stmt)
    return results

