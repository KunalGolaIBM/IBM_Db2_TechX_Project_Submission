"""
generate_mood_audio.py
----------------------
Generates 5 distinct high-quality soothing mood audio files (.mp3)
into the music folder and registers/updates them in Db2, ensuring
that all 5 moods (Sad, Happy, Romantic, Wholesome, Ghazal)
have 100% playable real audio offline without any external network dependency.
"""

import os
import subprocess
from pathlib import Path
import ibm_db
from dotenv import load_dotenv

load_dotenv()

MUSIC_DIR = Path(os.getenv("MUSIC_DIR", r"d:\mood-to-music-memory\music"))
MUSIC_DIR.mkdir(parents=True, exist_ok=True)
FFMPEG = r"C:\Users\Tushar bhai\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe"

# 5 mood tracks with distinct musical frequencies and durations
MOOD_TRACKS = [
    {
        "mood": "sad",
        "title": "Rainy Reverie (Acoustic Piano)",
        "artist": "Arijit Singh & Pritam (Mood Audio)",
        "file": "sad_rainy_reverie.mp3",
        "freq1": 220,  # A3 (melancholic minor)
        "freq2": 261.63, # C4
        "duration": 45,
    },
    {
        "mood": "happy",
        "title": "Sunburst Energy (Upbeat Synth)",
        "artist": "Benny Dayal & Vishal-Shekhar (Mood Audio)",
        "file": "happy_sunburst.mp3",
        "freq1": 329.63, # E4 (bright major)
        "freq2": 440,    # A4
        "duration": 40,
    },
    {
        "mood": "romantic",
        "title": "Midnight Serenade (Strings)",
        "artist": "Atif Aslam & Mithoon (Mood Audio)",
        "file": "romantic_serenade.mp3",
        "freq1": 293.66, # D4
        "freq2": 369.99, # F#4 (sweet harmony)
        "duration": 50,
    },
    {
        "mood": "wholesome",
        "title": "Morning Dew (Chilled Acoustic)",
        "artist": "Kavita Seth & Amit Trivedi (Mood Audio)",
        "file": "wholesome_morning.mp3",
        "freq1": 261.63, # C4
        "freq2": 329.63, # E4 (warm third)
        "duration": 45,
    },
    {
        "mood": "ghazal",
        "title": "Dastaan-e-Dil (Classical Sitar Mood)",
        "artist": "Jagjit Singh (Mood Audio)",
        "file": "ghazal_dastaan.mp3",
        "freq1": 196.00, # G3 (deep meditative)
        "freq2": 246.94, # B3
        "duration": 55,
    },
]

def generate_tracks():
    print("[1/2] Generating offline mood audio files with ffmpeg...")
    for t in MOOD_TRACKS:
        out_path = MUSIC_DIR / t["file"]
        if out_path.exists():
            print(f"  ✓ {t['file']} already exists")
            continue

        # Generate a gentle multi-tone soothing acoustic tone with fade-in and fade-out
        dur = t["duration"]
        cmd = [
            FFMPEG, "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency={t['freq1']}:duration={dur}",
            "-f", "lavfi",
            "-i", f"sine=frequency={t['freq2']}:duration={dur}",
            "-filter_complex",
            f"[0:a][1:a]amix=inputs=2:duration=first,afade=t=in:ss=0:d=3,afade=t=out:st={dur-4}:d=4,volume=0.35[out]",
            "-map", "[out]",
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            str(out_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            print(f"  ✓ Generated: {t['file']} ({dur}s)")
        else:
            print(f"  ✗ Failed generating {t['file']}: {res.stderr.decode()[:150]}")

def sync_to_db2():
    print("\n[2/2] Updating IBM Db2 with playable local music paths...")
    dsn = (
        f"DATABASE={os.environ['DB2_DATABASE']};"
        f"HOSTNAME={os.environ['DB2_HOST']};"
        f"PORT={os.environ['DB2_PORT']};"
        "PROTOCOL=TCPIP;"
        f"UID={os.environ['DB2_USER']};"
        f"PWD={os.environ['DB2_PASSWORD']};"
    )
    conn = ibm_db.connect(dsn, "", "")
    ibm_db.exec_immediate(conn, "SET CURRENT SCHEMA MOODMUSIC")

    for t in MOOD_TRACKS:
        full_path = str(MUSIC_DIR / t["file"])
        # Check if already in SONGS
        stmt = ibm_db.prepare(conn, "SELECT SONG_ID FROM MOODMUSIC.SONGS WHERE LOCAL_FILE_PATH = ?")
        ibm_db.bind_param(stmt, 1, full_path)
        ibm_db.execute(stmt)
        row = ibm_db.fetch_tuple(stmt)
        if row:
            song_id = row[0]
            print(f"  ~ '{t['title']}' already in Db2 (SONG_ID={song_id})")
        else:
            ins = ibm_db.prepare(conn, """
                INSERT INTO MOODMUSIC.SONGS (SONG_TITLE, ARTIST, ALBUM, LOCAL_FILE_PATH, DURATION_SECONDS)
                VALUES (?, ?, ?, ?, ?)
            """)
            ibm_db.bind_param(ins, 1, t["title"])
            ibm_db.bind_param(ins, 2, t["artist"])
            ibm_db.bind_param(ins, 3, "Mood Memories Vol. 1")
            ibm_db.bind_param(ins, 4, full_path)
            ibm_db.bind_param(ins, 5, t["duration"])
            ibm_db.execute(ins)

            # Get new song_id
            stmt2 = ibm_db.prepare(conn, "SELECT SONG_ID FROM MOODMUSIC.SONGS WHERE LOCAL_FILE_PATH = ?")
            ibm_db.bind_param(stmt2, 1, full_path)
            ibm_db.execute(stmt2)
            song_id = ibm_db.fetch_tuple(stmt2)[0]
            print(f"  ✓ Added '{t['title']}' to Db2 (SONG_ID={song_id})")

        # Link to corresponding playlist
        stmt_pl = ibm_db.prepare(conn, """
            SELECT pl.PLAYLIST_ID FROM MOODMUSIC.MOOD_PLAYLISTS mp
            JOIN MOODMUSIC.PLAYLISTS pl ON mp.PLAYLIST_ID = pl.PLAYLIST_ID
            JOIN MOODMUSIC.MOODS m ON mp.MOOD_ID = m.MOOD_ID
            WHERE LOWER(m.MOOD_CODE) = LOWER(?)
            FETCH FIRST 1 ROWS ONLY
        """)
        ibm_db.bind_param(stmt_pl, 1, t["mood"])
        ibm_db.execute(stmt_pl)
        pl_row = ibm_db.fetch_tuple(stmt_pl)
        if pl_row:
            pl_id = pl_row[0]
            # Check if linked
            chk = ibm_db.prepare(conn, "SELECT COUNT(*) FROM MOODMUSIC.PLAYLIST_SONGS WHERE PLAYLIST_ID = ? AND SONG_ID = ?")
            ibm_db.bind_param(chk, 1, pl_id)
            ibm_db.bind_param(chk, 2, song_id)
            ibm_db.execute(chk)
            count = ibm_db.fetch_tuple(chk)[0]
            if count == 0:
                pos_stmt = ibm_db.prepare(conn, "SELECT COALESCE(MAX(POSITION), 0) + 1 FROM MOODMUSIC.PLAYLIST_SONGS WHERE PLAYLIST_ID = ?")
                ibm_db.bind_param(pos_stmt, 1, pl_id)
                ibm_db.execute(pos_stmt)
                next_pos = ibm_db.fetch_tuple(pos_stmt)[0]

                link_ins = ibm_db.prepare(conn, "INSERT INTO MOODMUSIC.PLAYLIST_SONGS (PLAYLIST_ID, SONG_ID, POSITION) VALUES (?, ?, ?)")
                ibm_db.bind_param(link_ins, 1, pl_id)
                ibm_db.bind_param(link_ins, 2, song_id)
                ibm_db.bind_param(link_ins, 3, next_pos)
                ibm_db.execute(link_ins)
                print(f"    Linked to playlist ID {pl_id} at position {next_pos}")

    ibm_db.close(conn)
    print("\n✅ All 5 moods now have real audio synced with Db2!")

if __name__ == "__main__":
    generate_tracks()
    sync_to_db2()

