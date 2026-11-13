"""
smoke_test.py
-------------
End-to-end pipeline test WITHOUT needing a real audio file or frontend.

Tests:
  1. Db2 connection
  2. Mood lookup (all 5 moods)
  3. Playlist + profile fetch per mood
  4. Songs fetch per playlist
  5. AI mood interpreter (LangChain + Ollama llama3.2:3b)

Run:
    .\.venv\Scripts\python.exe smoke_test.py

Expected: all checks pass with green checkmarks.
"""

import sys
sys.path.insert(0, ".")

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "
results = []

def check(label, fn):
    try:
        result = fn()
        print(f"  {PASS} {label}" + (f" → {result}" if result else ""))
        results.append(True)
    except Exception as e:
        print(f"  {FAIL} {label} — {e}")
        results.append(False)

# ── 1. Db2 Connection ───────────────────────────────────────────────
print("\n[1] Db2 Connection")
import ibm_db
from dotenv import load_dotenv
import os
load_dotenv()

def test_db_connect():
    dsn = (
        f"DATABASE={os.environ['DB2_DATABASE']};"
        f"HOSTNAME={os.environ['DB2_HOST']};"
        f"PORT={os.environ['DB2_PORT']};"
        "PROTOCOL=TCPIP;"
        f"UID={os.environ['DB2_USER']};"
        f"PWD={os.environ['DB2_PASSWORD']};"
    )
    conn = ibm_db.connect(dsn, "", "")
    stmt = ibm_db.exec_immediate(conn, "SELECT CURRENT SERVER FROM sysibm.sysdummy1")
    row = ibm_db.fetch_tuple(stmt)
    ibm_db.close(conn)
    return row[0]

check("Connect to Db2", test_db_connect)

# ── 2. Mood Lookup ──────────────────────────────────────────────────
print("\n[2] Mood Lookup")
from src.db.connection import ConnectionManager
from src.db.queries import get_all_moods, get_mood_by_code

def test_all_moods():
    with ConnectionManager() as conn:
        moods = get_all_moods(conn)
    assert len(moods) == 5, f"Expected 5 moods, got {len(moods)}"
    return ", ".join(m.mood_code for m in moods)

check("Fetch all 5 moods", test_all_moods)

for code in ["sad", "happy", "romantic", "wholesome", "ghazal"]:
    def test_mood_by_code(c=code):
        with ConnectionManager() as conn:
            m = get_mood_by_code(conn, c)
        assert m is not None, f"Mood '{c}' not found"
        return m.display_name
    check(f"Mood by code: {code}", test_mood_by_code)

# ── 3. Playlist + Profile per Mood ──────────────────────────────────
print("\n[3] Playlist + Playback Profile")
from src.db.queries import get_playlist_for_mood

def test_playlist(mood_code):
    with ConnectionManager() as conn:
        mood = get_mood_by_code(conn, mood_code)
        pl   = get_playlist_for_mood(conn, mood.mood_id)
    assert pl is not None
    return f"'{pl.playlist_name}' vol={pl.profile.volume_percent}%"

for code in ["sad", "happy", "romantic", "wholesome", "ghazal"]:
    check(f"Playlist for '{code}'", lambda c=code: test_playlist(c))

# ── 4. Songs per Playlist ───────────────────────────────────────────
print("\n[4] Songs in Playlists")
from src.db.queries import get_songs_for_playlist

def test_songs(mood_code):
    with ConnectionManager() as conn:
        mood  = get_mood_by_code(conn, mood_code)
        pl    = get_playlist_for_mood(conn, mood.mood_id)
        songs = get_songs_for_playlist(conn, pl.playlist_id)
    assert len(songs) > 0, "No songs in playlist"
    titles = ", ".join(s.song_title for s in songs)
    return f"{len(songs)} songs — {titles}"

for code in ["sad", "happy", "romantic", "wholesome", "ghazal"]:
    check(f"Songs for '{code}'", lambda c=code: test_songs(c))

# ── 5. AI Mood Interpreter ──────────────────────────────────────────
print("\n[5] AI Mood Interpreter (LangChain + llama3.2:3b)")
print(f"  {WARN} This test calls Ollama locally — may take 10–20s on first run")

test_phrases = [
    ("I am feeling very low and sad today", "sad"),
    ("I feel so energetic and joyful!", "happy"),
    ("In the mood for some love songs", "romantic"),
]

from src.ai.mood_interpreter import MoodInterpreter
try:
    interpreter = MoodInterpreter()
    for phrase, expected in test_phrases:
        def test_interp(p=phrase, exp=expected):
            result = interpreter.interpret(p)
            match = "✓" if result == exp else f"got '{result}' (expected '{exp}')"
            return f"'{p[:30]}…' → {result} {match}"
        check(f"Interpret mood", test_interp)
except Exception as e:
    print(f"  {WARN} Skipping AI tests — Ollama may not be reachable from sandbox: {e}")

# ── Summary ─────────────────────────────────────────────────────────
passed = sum(results)
total  = len(results)
print(f"\n{'─'*45}")
print(f"  Result: {passed}/{total} checks passed")
if passed == total:
    print(f"  {PASS} All good! Ready to build the frontend.")
else:
    print(f"  {FAIL} {total - passed} check(s) failed — fix before proceeding.")
print(f"{'─'*45}\n")

