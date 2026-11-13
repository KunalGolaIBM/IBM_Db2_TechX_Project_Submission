"""Revert Db2 path back to actual .webm file that exists on disk."""
import sys, os
sys.path.insert(0, ".")
import ibm_db
from dotenv import load_dotenv
load_dotenv()

SCHEMA   = "MOODMUSIC"
SONG_ID  = 11
# Point to the actual file that exists
REAL_PATH = r"d:\mood-to-music-memory\music\Broken Love (Video Jukebox) Non-Stop Heart Break _ Heart Touching Sad Songs _ Hi.webm"

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
sql  = f"UPDATE {SCHEMA}.SONGS SET LOCAL_FILE_PATH = ? WHERE SONG_ID = ?"
stmt = ibm_db.prepare(conn, sql)
ibm_db.bind_param(stmt, 1, REAL_PATH)
ibm_db.bind_param(stmt, 2, SONG_ID)
ibm_db.execute(stmt)
ibm_db.close(conn)
print(f"✅ Reverted SONG_ID={SONG_ID} → .webm (actual file on disk)")

