"""
Seed the MOODMUSIC schema with moods, playback profiles, playlists,
and a few placeholder songs so the app has something to run on.

Run once after setup_db2.py:
    .\.venv\Scripts\python.exe db\seed_db.py
"""

import os
from pathlib import Path
import ibm_db
from dotenv import load_dotenv

SCHEMA = "MOODMUSIC"


def required(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(f"Missing required env var: {name}")
    return val


def dsn() -> str:
    return (
        f"DATABASE={required('DB2_DATABASE')};"
        f"HOSTNAME={required('DB2_HOST')};"
        f"PORT={required('DB2_PORT')};"
        "PROTOCOL=TCPIP;"
        f"UID={required('DB2_USER')};"
        f"PWD={required('DB2_PASSWORD')};"
    )


def run(conn, sql: str, label: str = "") -> None:
    try:
        ibm_db.exec_immediate(conn, sql)
        if label:
            print(f"  ✓ {label}")
    except Exception as e:
        msg = str(e)
        # Ignore duplicate-row errors (SQL0803N unique constraint)
        if "SQL0803N" in msg or "-803" in msg:
            if label:
                print(f"  ~ already exists: {label}")
        else:
            raise


def seed_moods(conn) -> None:
    print("\n[Moods]")
    moods = [
        ("sad",       "Sad",       "Comforting songs for low or melancholic moods"),
        ("happy",     "Happy",     "Energetic and uplifting songs"),
        ("romantic",  "Romantic",  "Soft and romantic melodies"),
        ("wholesome", "Wholesome", "Warm and feel-good tracks"),
        ("ghazal",    "Ghazal",    "Classical and semi-classical Ghazals"),
    ]
    for code, name, desc in moods:
        run(
            conn,
            f"INSERT INTO {SCHEMA}.MOODS (MOOD_CODE, DISPLAY_NAME, DESCRIPTION) "
            f"VALUES ('{code}', '{name}', '{desc}')",
            f"mood: {code}",
        )


def seed_profiles(conn) -> None:
    print("\n[Playback Profiles]")
    profiles = [
        ("sad",       30, "1.00", 4),
        ("happy",     70, "1.05", 1),
        ("romantic",  50, "0.95", 3),
        ("wholesome", 55, "1.00", 2),
        ("ghazal",    45, "0.95", 3),
    ]
    for code, vol, speed, fade in profiles:
        run(
            conn,
            f"INSERT INTO {SCHEMA}.PLAYBACK_PROFILES "
            f"(PROFILE_CODE, VOLUME_PERCENT, SPEED_MULTIPLIER, FADE_IN_SECONDS) "
            f"VALUES ('{code}', {vol}, {speed}, {fade})",
            f"profile: {code}",
        )


def seed_playlists(conn) -> None:
    """
    Each playlist needs the PROFILE_ID of its matching profile.
    We look up profile IDs by code, then insert playlists referencing them.
    """
    print("\n[Playlists]")
    moods_and_playlists = [
        ("sad",       "Rainy Day Comfort",      "Soft songs for quiet, low moments"),
        ("happy",     "Feel-Good Hits",         "Upbeat tracks to brighten the day"),
        ("romantic",  "Love Notes",             "Melodies that speak of love"),
        ("wholesome", "Sunday Morning Vibes",   "Cosy, feel-good listening"),
        ("ghazal",    "Ghazal Classics",        "Timeless Ghazal collection"),
    ]
    for profile_code, playlist_name, desc in moods_and_playlists:
        # Fetch profile id
        stmt = ibm_db.exec_immediate(
            conn,
            f"SELECT PROFILE_ID FROM {SCHEMA}.PLAYBACK_PROFILES "
            f"WHERE PROFILE_CODE = '{profile_code}'",
        )
        row = ibm_db.fetch_tuple(stmt)
        if not row:
            print(f"  ! profile '{profile_code}' not found, skipping playlist")
            continue
        profile_id = row[0]
        run(
            conn,
            f"INSERT INTO {SCHEMA}.PLAYLISTS (PLAYLIST_NAME, DESCRIPTION, PROFILE_ID) "
            f"VALUES ('{playlist_name}', '{desc}', {profile_id})",
            f"playlist: {playlist_name}",
        )


def seed_mood_playlist_links(conn) -> None:
    """Link each mood to its playlist by matching names."""
    print("\n[Mood → Playlist links]")
    pairs = [
        ("sad",       "Rainy Day Comfort"),
        ("happy",     "Feel-Good Hits"),
        ("romantic",  "Love Notes"),
        ("wholesome", "Sunday Morning Vibes"),
        ("ghazal",    "Ghazal Classics"),
    ]
    for mood_code, playlist_name in pairs:
        stmt_m = ibm_db.exec_immediate(
            conn,
            f"SELECT MOOD_ID FROM {SCHEMA}.MOODS WHERE MOOD_CODE = '{mood_code}'",
        )
        row_m = ibm_db.fetch_tuple(stmt_m)

        stmt_p = ibm_db.exec_immediate(
            conn,
            f"SELECT PLAYLIST_ID FROM {SCHEMA}.PLAYLISTS "
            f"WHERE PLAYLIST_NAME = '{playlist_name}'",
        )
        row_p = ibm_db.fetch_tuple(stmt_p)

        if not row_m or not row_p:
            print(f"  ! skipping link {mood_code} → {playlist_name}")
            continue
        run(
            conn,
            f"INSERT INTO {SCHEMA}.MOOD_PLAYLISTS (MOOD_ID, PLAYLIST_ID, PRIORITY) "
            f"VALUES ({row_m[0]}, {row_p[0]}, 1)",
            f"{mood_code} → {playlist_name}",
        )


def seed_placeholder_songs(conn) -> None:
    """
    Add placeholder song rows. LOCAL_FILE_PATH values use a generic
    path — replace them in the app or via the Import Media feature.
    """
    print("\n[Placeholder Songs]")
    songs = [
        # (title, artist, album, path, duration_seconds, playlist_name, position)
        ("Tum Hi Ho",          "Arijit Singh",  "Aashiqui 2",   r"C:\Music\tum_hi_ho.mp3",         262, "Love Notes",           1),
        ("Kal Ho Naa Ho",      "Sonu Nigam",    "Kal Ho Na Ho", r"C:\Music\kal_ho_na_ho.mp3",       325, "Rainy Day Comfort",    1),
        ("Phir Le Aaya Dil",   "Arijit Singh",  "Barfi",        r"C:\Music\phir_le_aaya_dil.mp3",   280, "Rainy Day Comfort",    2),
        ("Badtameez Dil",      "Benny Dayal",   "Yeh Jawaani",  r"C:\Music\badtameez_dil.mp3",      230, "Feel-Good Hits",       1),
        ("Gallan Goodiyaan",   "Various",       "Dil Dhadakne", r"C:\Music\gallan_goodiyaan.mp3",   264, "Feel-Good Hits",       2),
        ("Pehla Nasha",        "Udit Narayan",  "Jo Jeeta",     r"C:\Music\pehla_nasha.mp3",        310, "Sunday Morning Vibes", 3),
        ("Chaudhary",          "Mame Khan",     "Highway",      r"C:\Music\chaudhary.mp3",          285, "Sunday Morning Vibes", 1),
        ("Tere Bina",          "AR Rahman",     "Guru",         r"C:\Music\tere_bina.mp3",          298, "Sunday Morning Vibes", 2),
        ("Dil Ke Arman",       "Jagjit Singh",  "Ghazals",      r"C:\Music\dil_ke_arman.mp3",       350, "Ghazal Classics",      1),
        ("Hum Ko Mann Ki",     "Jagjit Singh",  "Ghazals",      r"C:\Music\hum_ko_mann_ki.mp3",     320, "Ghazal Classics",      2),
    ]

    for title, artist, album, path, dur, playlist_name, position in songs:
        # Insert song
        try:
            ibm_db.exec_immediate(
                conn,
                f"INSERT INTO {SCHEMA}.SONGS "
                f"(SONG_TITLE, ARTIST, ALBUM, LOCAL_FILE_PATH, DURATION_SECONDS) "
                f"VALUES ('{title}', '{artist}', '{album}', '{path}', {dur})",
            )
            print(f"  ✓ song: {title}")
        except Exception as e:
            if "SQL0803N" in str(e) or "-803" in str(e):
                print(f"  ~ already exists: {title}")
            else:
                raise

        # Fetch the song id just inserted (or existing)
        stmt_s = ibm_db.exec_immediate(
            conn,
            f"SELECT SONG_ID FROM {SCHEMA}.SONGS "
            f"WHERE SONG_TITLE = '{title}' AND ARTIST = '{artist}'",
        )
        row_s = ibm_db.fetch_tuple(stmt_s)
        if not row_s:
            continue
        song_id = row_s[0]

        # Fetch playlist id
        stmt_pl = ibm_db.exec_immediate(
            conn,
            f"SELECT PLAYLIST_ID FROM {SCHEMA}.PLAYLISTS "
            f"WHERE PLAYLIST_NAME = '{playlist_name}'",
        )
        row_pl = ibm_db.fetch_tuple(stmt_pl)
        if not row_pl:
            print(f"    ! playlist '{playlist_name}' not found")
            continue
        pl_id = row_pl[0]

        run(
            conn,
            f"INSERT INTO {SCHEMA}.PLAYLIST_SONGS (PLAYLIST_ID, SONG_ID, POSITION) "
            f"VALUES ({pl_id}, {song_id}, {position})",
            f"  linked to '{playlist_name}' at position {position}",
        )


def main() -> None:
    load_dotenv()
    print("Connecting to Db2…")
    conn = ibm_db.connect(dsn(), "", "")
    try:
        seed_moods(conn)
        seed_profiles(conn)
        seed_playlists(conn)
        seed_mood_playlist_links(conn)
        seed_placeholder_songs(conn)
        print("\n✅ Seed complete.")
        print(
            "\nNOTE: Song paths are placeholders (C:\\Music\\*.mp3).\n"
            "Replace them with your real local paths, or use the\n"
            "Import Media feature once the backend is ready."
        )
    finally:
        ibm_db.close(conn)


if __name__ == "__main__":
    main()

