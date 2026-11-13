"""Quick DB inspection script — shows row counts and sample data for all tables."""
import os, ibm_db
from dotenv import load_dotenv

load_dotenv()
SCHEMA = "MOODMUSIC"

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

tables = ["MOODS", "PLAYBACK_PROFILES", "PLAYLISTS", "MOOD_PLAYLISTS",
          "SONGS", "PLAYLIST_SONGS", "PLAYBACK_SESSIONS", "MEMORIES"]

print(f"\n{'Table':<25} {'Rows':>6}")
print("-" * 33)
for t in tables:
    try:
        stmt = ibm_db.exec_immediate(conn, f"SELECT COUNT(*) FROM {SCHEMA}.{t}")
        row = ibm_db.fetch_tuple(stmt)
        print(f"{t:<25} {row[0]:>6}")
    except Exception as e:
        print(f"{t:<25}  ERROR: {e}")

# Show mood data if any
print("\n--- MOODS ---")
try:
    stmt = ibm_db.exec_immediate(conn, f"SELECT MOOD_ID, MOOD_CODE, DISPLAY_NAME FROM {SCHEMA}.MOODS")
    row = ibm_db.fetch_assoc(stmt)
    if not row:
        print("  (empty)")
    while row:
        print(f"  {dict(row)}")
        row = ibm_db.fetch_assoc(stmt)
except Exception as e:
    print(f"  ERROR: {e}")

# Show songs if any
print("\n--- SONGS (first 5) ---")
try:
    stmt = ibm_db.exec_immediate(conn, f"SELECT SONG_ID, SONG_TITLE, ARTIST, LOCAL_FILE_PATH FROM {SCHEMA}.SONGS FETCH FIRST 5 ROWS ONLY")
    row = ibm_db.fetch_assoc(stmt)
    if not row:
        print("  (empty)")
    while row:
        print(f"  {dict(row)}")
        row = ibm_db.fetch_assoc(stmt)
except Exception as e:
    print(f"  ERROR: {e}")

ibm_db.close(conn)

