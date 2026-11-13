"""
smoke_test.py
-------------
Quick end-to-end test of the FastAPI + Db2 backend.
Run while uvicorn is active on port 8000:

    .venv\\Scripts\\python.exe smoke_test.py
"""

import sys
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"
PASS = []
FAIL = []


def check(name: str, url: str, method: str = "GET", body: dict = None, expect_status: int = 200):
    try:
        data = json.dumps(body).encode() if body else None
        req  = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            status = r.status
            resp   = json.loads(r.read())
        if status == expect_status:
            PASS.append(name)
            print(f"  ✅ {name}  ({status})")
            return resp
        else:
            FAIL.append(name)
            print(f"  ✗  {name}  expected {expect_status}, got {status}")
    except urllib.error.HTTPError as e:
        if e.code == expect_status:
            PASS.append(name)
            print(f"  ✅ {name}  ({e.code})")
        else:
            FAIL.append(name)
            print(f"  ✗  {name}  HTTP {e.code}: {e.read().decode()[:120]}")
    except Exception as exc:
        FAIL.append(name)
        print(f"  ✗  {name}  {exc}")
    return None


print("\n" + "="*50)
print("  Mood-to-Music Memory — Smoke Test")
print("="*50 + "\n")

# Health
print("[Health]")
check("GET /api/health", f"{BASE}/api/health")

# Moods
print("\n[Moods]")
moods = check("GET /api/moods", f"{BASE}/api/moods")
if moods:
    print(f"     → {len(moods)} moods: {[m['MOOD_CODE'] for m in moods]}")

# Songs
print("\n[Songs]")
songs = check("GET /api/songs", f"{BASE}/api/songs")
if songs:
    print(f"     → {len(songs)} total songs")
sad_songs = check("GET /api/songs?mood=sad", f"{BASE}/api/songs?mood=sad")
if sad_songs:
    print(f"     → {len(sad_songs)} sad songs")

# Playlists
print("\n[Playlists]")
playlists = check("GET /api/playlists", f"{BASE}/api/playlists")
if playlists:
    print(f"     → {len(playlists)} playlists: {[p['name'] for p in playlists]}")

# Memories
print("\n[Memories]")
mems = check("GET /api/memories", f"{BASE}/api/memories")
if mems is not None:
    print(f"     → {len(mems)} memories")

# Create memory
print("\n[Create Memory]")
new_mem = check(
    "POST /api/memories",
    f"{BASE}/api/memories",
    method="POST",
    body={
        "memory_text": "Smoke test memory — delete me",
        "song_title":  "Test Song",
        "artist":      "Test Artist",
        "mood_tag":    "happy",
        "saved_at":    "2026-11-13T09:00:00",
    },
    expect_status=201,
)
mem_id = None
if new_mem:
    mem_id = new_mem.get("id")
    print(f"     → Created memory ID: {mem_id}")

# Delete the test memory
if mem_id:
    print("\n[Delete Memory]")
    check(f"DELETE /api/memories/{mem_id}", f"{BASE}/api/memories/{mem_id}", method="DELETE")

# Session
print("\n[Session]")
sess = check("POST /api/session/start", f"{BASE}/api/session/start", method="POST", body={"mood_code": "happy"}, expect_status=201)
if sess:
    sid = sess.get("session_id")
    print(f"     → Session ID: {sid}")
    check("POST /api/session/end", f"{BASE}/api/session/end", method="POST", body={"session_id": sid, "feedback": "smoke_test"})

# Analytics
print("\n[Analytics]")
analytics = check("GET /api/analytics", f"{BASE}/api/analytics")
if analytics:
    print(f"     → Sessions: {analytics.get('totalSessions')}  Songs: {analytics.get('totalSongs')}  Memories: {analytics.get('totalMemories')}")

# Results
print("\n" + "="*50)
print(f"  PASSED: {len(PASS)}   FAILED: {len(FAIL)}")
if FAIL:
    print(f"  Failed: {', '.join(FAIL)}")
print("="*50 + "\n")

sys.exit(0 if not FAIL else 1)
