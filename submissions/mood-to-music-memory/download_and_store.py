"""
download_and_store.py
----------------------
Downloads a song from a YouTube URL using yt-dlp (SSL-safe),
saves the audio to the music folder, and registers it in Db2.

Usage:
    python download_and_store.py <URL> <mood_code>

Example:
    python download_and_store.py "https://youtu.be/C6w075EfZHk" romantic

Mood codes: sad | happy | romantic | wholesome | ghazal
"""

import sys
import os
import re
from pathlib import Path

sys.path.insert(0, ".")

import yt_dlp
from dotenv import load_dotenv
import ibm_db

load_dotenv()

SCHEMA     = "MOODMUSIC"
MUSIC_DIR  = Path(os.getenv("MUSIC_DIR", r"d:\mood-to-music-memory\music"))
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# ── Args ─────────────────────────────────────────────────────────────
if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(1)

URL        = sys.argv[1].strip()
MOOD_CODE  = sys.argv[2].strip().lower()

VALID_MOODS = ["sad", "happy", "romantic", "wholesome", "ghazal"]
if MOOD_CODE not in VALID_MOODS:
    print(f"Invalid mood '{MOOD_CODE}'. Choose from: {', '.join(VALID_MOODS)}")
    sys.exit(1)

# ── Db2 helpers ───────────────────────────────────────────────────────
def get_conn():
    dsn = (
        f"DATABASE={os.environ['DB2_DATABASE']};"
        f"HOSTNAME={os.environ['DB2_HOST']};"
        f"PORT={os.environ['DB2_PORT']};"
        "PROTOCOL=TCPIP;"
        f"UID={os.environ['DB2_USER']};"
        f"PWD={os.environ['DB2_PASSWORD']};"
    )
    conn = ibm_db.connect(dsn, "", "")
    ibm_db.exec_immediate(conn, f"SET CURRENT SCHEMA {SCHEMA}")
    return conn


def safe_name(name: str, max_len: int = 80) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name.strip(". ")[:max_len]


# ── Parameterised query helpers ───────────────────────────────────────
def exec_param(conn, sql: str, params: tuple):
    """Execute a parameterised statement safely (no f-string SQL injection)."""
    stmt = ibm_db.prepare(conn, sql)
    for i, val in enumerate(params, start=1):
        ibm_db.bind_param(stmt, i, val)
    ibm_db.execute(stmt)
    return stmt


# ── Step 1: Fetch info ────────────────────────────────────────────────
print(f"\n[1/4] Fetching info for: {URL}")
ydl_info_opts = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "nocheckcertificate": True,
}
with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
    info = ydl.extract_info(URL, download=False)

title    = info.get("title", "Unknown Title")
artist   = info.get("uploader") or info.get("channel", "Unknown Artist")
duration = info.get("duration")

print(f"    Title   : {title}")
print(f"    Artist  : {artist}")
print(f"    Duration: {duration}s ({(duration or 0)//60}m {(duration or 0)%60}s)")

# ── Step 2: Download audio ────────────────────────────────────────────
fname      = safe_name(title)
output_tpl = str(MUSIC_DIR / f"{fname}.%(ext)s")

print(f"\n[2/4] Downloading audio…")

def build_ydl_opts(use_ffmpeg: bool) -> dict:
    base = {
        "format": "bestaudio/best",
        "outtmpl": output_tpl,
        "quiet": False,
        "no_warnings": True,
        "nocheckcertificate": True,
    }
    if use_ffmpeg:
        base["ffmpeg_location"] = str(Path(ffmpeg_path).parent)
        base["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    return base

import shutil
_WINGET_FFMPEG = r"C:\Users\Tushar bhai\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"
ffmpeg_path = shutil.which("ffmpeg") or (_WINGET_FFMPEG if Path(_WINGET_FFMPEG).exists() else None)
has_ffmpeg  = ffmpeg_path is not None

if has_ffmpeg:
    print(f"    ffmpeg detected → will convert to MP3")
else:
    print("    ffmpeg not found — saving in native format (m4a/webm/opus)")

with yt_dlp.YoutubeDL(build_ydl_opts(has_ffmpeg)) as ydl:
    ydl.download([URL])

# Find the downloaded file
matches = sorted(MUSIC_DIR.glob(f"{fname}.*"))
if not matches:
    print(f"\nERROR: No file found matching '{fname}.*' in {MUSIC_DIR}")
    sys.exit(1)
file_path = str(matches[-1])
print(f"\n    Saved → {file_path}")

# ── Step 3: Store in Db2 (fully parameterised — no SQL injection) ────
print(f"\n[3/4] Storing in Db2 (parameterised queries)…")
conn = get_conn()

# Get mood_id using parameterised query ✅
stmt = exec_param(
    conn,
    f"SELECT MOOD_ID FROM {SCHEMA}.MOODS WHERE LOWER(MOOD_CODE) = LOWER(?)",
    (MOOD_CODE,),
)
row = ibm_db.fetch_tuple(stmt)
if not row:
    print(f"Mood '{MOOD_CODE}' not found in DB. Run seed_db.py first.")
    ibm_db.close(conn)
    sys.exit(1)
mood_id = row[0]

# Get playlist_id using parameterised query ✅
stmt = exec_param(
    conn,
    f"""
    SELECT pl.PLAYLIST_ID, pl.PLAYLIST_NAME
    FROM {SCHEMA}.MOOD_PLAYLISTS mp
    JOIN {SCHEMA}.PLAYLISTS pl ON mp.PLAYLIST_ID = pl.PLAYLIST_ID
    WHERE mp.MOOD_ID = ? AND pl.IS_ACTIVE = 'Y'
    ORDER BY mp.PRIORITY ASC
    FETCH FIRST 1 ROWS ONLY
    """,
    (mood_id,),
)
row = ibm_db.fetch_tuple(stmt)
if not row:
    print(f"No active playlist for mood '{MOOD_CODE}'.")
    ibm_db.close(conn)
    sys.exit(1)
playlist_id, playlist_name = row

# Get next position in playlist using parameterised query ✅
stmt = exec_param(
    conn,
    f"SELECT COALESCE(MAX(POSITION), 0) + 1 FROM {SCHEMA}.PLAYLIST_SONGS WHERE PLAYLIST_ID = ?",
    (playlist_id,),
)
pos_row  = ibm_db.fetch_tuple(stmt)
position = pos_row[0] if pos_row else 1

# Insert song using parameterised query ✅ (no f-string with user data)
exec_param(
    conn,
    f"INSERT INTO {SCHEMA}.SONGS (SONG_TITLE, ARTIST, ALBUM, LOCAL_FILE_PATH, DURATION_SECONDS) "
    f"VALUES (?, ?, ?, ?, ?)",
    (title, artist, "", file_path, duration),
)

# Get new song_id using parameterised query ✅
stmt = exec_param(
    conn,
    f"SELECT SONG_ID FROM {SCHEMA}.SONGS WHERE LOCAL_FILE_PATH = ? "
    f"ORDER BY CREATED_AT DESC FETCH FIRST 1 ROWS ONLY",
    (file_path,),
)
song_id = ibm_db.fetch_tuple(stmt)[0]

# Link to playlist using parameterised query ✅
exec_param(
    conn,
    f"INSERT INTO {SCHEMA}.PLAYLIST_SONGS (PLAYLIST_ID, SONG_ID, POSITION) VALUES (?, ?, ?)",
    (playlist_id, song_id, position),
)

ibm_db.close(conn)

# ── Step 4: Confirm ───────────────────────────────────────────────────
print(f"\n[4/4] ✅ Done!")
print(f"    Song ID   : {song_id}")
print(f"    Title     : {title}")
print(f"    Artist    : {artist}")
print(f"    File      : {file_path}")
print(f"    Playlist  : {playlist_name} (position {position})")
print(f"    Mood      : {MOOD_CODE}")
