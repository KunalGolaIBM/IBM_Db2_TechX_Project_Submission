"""
batch_download.py
-----------------
Downloads mood-based songs into the music directory and registers them in Db2.
Uses yt-dlp search with Android/iOS player clients for maximum reliability
against YouTube bot/unavailable errors.

Run:
    .venv\\Scripts\\python.exe batch_download.py
"""

import sys
import os
import re
import shutil
from pathlib import Path

sys.path.insert(0, ".")

import yt_dlp
from dotenv import load_dotenv
import ibm_db

load_dotenv()

SCHEMA    = "MOODMUSIC"
MUSIC_DIR = Path(os.getenv("MUSIC_DIR", r"d:\mood-to-music-memory\music"))
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

# ── Songs to download (Using search queries so dead URLs don't break the script)
SONGS = [
    # SAD
    ("ytsearch1:Tum Hi Ho Arijit Singh audio", "sad", "Tum Hi Ho - Arijit Singh"),
    ("ytsearch1:Channa Mereya Arijit Singh audio", "sad", "Channa Mereya - Arijit Singh"),
    ("ytsearch1:Kal Ho Naa Ho Sonu Nigam audio", "sad", "Kal Ho Naa Ho - Sonu Nigam"),
    # HAPPY
    ("ytsearch1:Badtameez Dil Benny Dayal audio", "happy", "Badtameez Dil - Benny Dayal"),
    ("ytsearch1:Gallan Goodiyaan audio Dil Dhadakne Do", "happy", "Gallan Goodiyaan - Various"),
    # ROMANTIC
    ("ytsearch1:Tere Sang Yaara Atif Aslam audio", "romantic", "Tere Sang Yaara - Atif Aslam"),
    ("ytsearch1:Raabta Arijit Singh audio", "romantic", "Raabta - Arijit Singh"),
    # WHOLESOME
    ("ytsearch1:Iktara Kavita Seth Wake Up Sid audio", "wholesome", "Iktara - Kavita Seth"),
    ("ytsearch1:Phir Kabhi Arijit Singh MS Dhoni audio", "wholesome", "Phir Kabhi - Arijit Singh"),
    # GHAZAL
    ("ytsearch1:Chaudhvin Ka Chand Ho Mohammad Rafi audio", "ghazal", "Chaudhvin Ka Chand - Rafi"),
    ("ytsearch1:Lag Ja Gale Lata Mangeshkar audio", "ghazal", "Lag Ja Gale - Lata Mangeshkar"),
]

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

def exec_param(conn, sql: str, params: tuple):
    stmt = ibm_db.prepare(conn, sql)
    for i, val in enumerate(params, start=1):
        ibm_db.bind_param(stmt, i, val)
    ibm_db.execute(stmt)
    return stmt

def safe_name(name: str, max_len: int = 80) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    return name.strip(". ")[:max_len]

# Detect ffmpeg
_WINGET_FFMPEG = r"C:\Users\Tushar bhai\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"
ffmpeg_path = shutil.which("ffmpeg") or (_WINGET_FFMPEG if Path(_WINGET_FFMPEG).exists() else None)
has_ffmpeg  = ffmpeg_path is not None
print(f"ffmpeg status: {'Found at ' + str(ffmpeg_path) if has_ffmpeg else 'Not found — saving original format'}")

# Detect Node for JS runtime
node_path = shutil.which("node")
print(f"Node.js runtime: {'Found at ' + str(node_path) if node_path else 'Not found'}\n")

def get_base_ydl_opts(out_tpl: str | None = None) -> dict:
    opts = {
        "quiet": False,
        "no_warnings": True,
        "nocheckcertificate": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "ios", "mweb", "web"],
            }
        },
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        },
    }
    if out_tpl:
        opts["format"] = "bestaudio/best"
        opts["outtmpl"] = out_tpl
        if has_ffmpeg:
            opts["ffmpeg_location"] = str(Path(ffmpeg_path).parent)
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
    return opts

def download_one(target: str, mood_code: str, hint: str) -> bool:
    print(f"\n{'='*60}")
    print(f"  Target: {hint}  [{mood_code.upper()}]")
    print(f"  Query:  {target}")

    try:
        info_opts = get_base_ydl_opts()
        info_opts["skip_download"] = True
        with yt_dlp.YoutubeDL(info_opts) as ydl:
            res = ydl.extract_info(target, download=False)
            if "entries" in res:
                entries = [e for e in res["entries"] if e]
                if not entries:
                    print("  ✗ No search results returned")
                    return False
                info = entries[0]
            else:
                info = res
    except Exception as e:
        print(f"  ✗ Metadata extraction failed: {e}")
        return False

    title       = info.get("title", hint)
    artist      = info.get("uploader") or info.get("channel") or "Various Artists"
    duration    = info.get("duration") or 210
    webpage_url = info.get("webpage_url") or target
    fname       = safe_name(hint)  # Use the clean hint name for consistent filenames
    out_tpl     = str(MUSIC_DIR / f"{fname}.%(ext)s")

    print(f"  Found:  {title}")
    print(f"  Artist: {artist} | Duration: {duration}s")

    # Download
    dl_opts = get_base_ydl_opts(out_tpl)
    try:
        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([webpage_url])
    except Exception as e:
        print(f"  ✗ Download error: {e}")
        return False

    matches = sorted(MUSIC_DIR.glob(f"{fname}.*"))
    if not matches:
        # Check if yt-dlp named it with video title instead
        alt_fname = safe_name(title)
        matches = sorted(MUSIC_DIR.glob(f"{alt_fname}.*"))

    if not matches:
        print(f"  ✗ Downloaded file not located in {MUSIC_DIR}")
        return False

    file_path = str(matches[-1])
    print(f"  → Saved file: {file_path}")

    # Register in Db2
    try:
        conn = get_conn()

        # Mood ID
        stmt = exec_param(conn,
            f"SELECT MOOD_ID FROM {SCHEMA}.MOODS WHERE LOWER(MOOD_CODE) = LOWER(?)",
            (mood_code,))
        row = ibm_db.fetch_tuple(stmt)
        if not row:
            print(f"  ✗ Mood '{mood_code}' not found in Db2")
            ibm_db.close(conn)
            return False
        mood_id = row[0]

        # Playlist ID
        stmt = exec_param(conn, f"""
            SELECT pl.PLAYLIST_ID, pl.PLAYLIST_NAME
            FROM {SCHEMA}.MOOD_PLAYLISTS mp
            JOIN {SCHEMA}.PLAYLISTS pl ON mp.PLAYLIST_ID = pl.PLAYLIST_ID
            WHERE mp.MOOD_ID = ? AND pl.IS_ACTIVE = 'Y'
            ORDER BY mp.PRIORITY ASC FETCH FIRST 1 ROWS ONLY
        """, (mood_id,))
        row = ibm_db.fetch_tuple(stmt)
        if not row:
            print(f"  ✗ No playlist found for mood '{mood_code}'")
            ibm_db.close(conn)
            return False
        playlist_id, playlist_name = row

        # Next position
        stmt = exec_param(conn,
            f"SELECT COALESCE(MAX(POSITION), 0) + 1 FROM {SCHEMA}.PLAYLIST_SONGS WHERE PLAYLIST_ID = ?",
            (playlist_id,))
        pos_row  = ibm_db.fetch_tuple(stmt)
        position = pos_row[0] if pos_row else 1

        # Check existing
        stmt = exec_param(conn,
            f"SELECT SONG_ID FROM {SCHEMA}.SONGS WHERE LOCAL_FILE_PATH = ?",
            (file_path,))
        dup = ibm_db.fetch_tuple(stmt)
        if dup:
            song_id = dup[0]
            print(f"  ~ Song already in Db2 (ID: {song_id})")
        else:
            # Insert song
            exec_param(conn,
                f"INSERT INTO {SCHEMA}.SONGS (SONG_TITLE, ARTIST, ALBUM, LOCAL_FILE_PATH, DURATION_SECONDS) "
                f"VALUES (?, ?, ?, ?, ?)",
                (title, artist, "", file_path, duration))

            stmt = exec_param(conn,
                f"SELECT SONG_ID FROM {SCHEMA}.SONGS WHERE LOCAL_FILE_PATH = ? "
                f"ORDER BY CREATED_AT DESC FETCH FIRST 1 ROWS ONLY",
                (file_path,))
            song_id = ibm_db.fetch_tuple(stmt)[0]

        # Link to playlist if not already linked
        stmt_link = exec_param(conn,
            f"SELECT COUNT(*) FROM {SCHEMA}.PLAYLIST_SONGS WHERE PLAYLIST_ID = ? AND SONG_ID = ?",
            (playlist_id, song_id))
        is_linked = ibm_db.fetch_tuple(stmt_link)[0] > 0

        if not is_linked:
            exec_param(conn,
                f"INSERT INTO {SCHEMA}.PLAYLIST_SONGS (PLAYLIST_ID, SONG_ID, POSITION) VALUES (?, ?, ?)",
                (playlist_id, song_id, position))

        ibm_db.close(conn)
        print(f"  ✅ Registered in Db2 → Song ID: {song_id} | Playlist: '{playlist_name}' (pos {position})")
        return True

    except Exception as e:
        print(f"  ✗ Db2 registration error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("  Mood-to-Music Memory — Batch Song Downloader & Db2 Sync")
    print("=" * 60)

    success = 0
    failed = 0

    for target, mood, hint in SONGS:
        if download_one(target, mood, hint):
            success += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"  SUMMARY: {success} downloaded & synced to Db2, {failed} failed")
    print("=" * 60)
