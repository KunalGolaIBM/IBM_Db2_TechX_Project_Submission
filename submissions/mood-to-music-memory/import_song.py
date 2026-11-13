"""
import_song.py
--------------
Interactive CLI to download a song from a URL and add it to a playlist.

Run:
    .\.venv\Scripts\python.exe import_song.py

Steps:
  1. Paste the URL
  2. Preview song info (title, artist, duration)
  3. Choose which mood playlist to add it to
  4. Confirm you have legal rights to download it
  5. Download starts — MP3 saved to music\ folder
  6. Song + path registered in Db2
"""

import sys
sys.path.insert(0, ".")

from src.services.media_import import MediaImportService
from src.db.connection import ConnectionManager
from src.db.queries import get_all_moods, get_playlist_for_mood

svc = MediaImportService()

print("\n╔══════════════════════════════════════╗")
print("║   Mood-to-Music — Import a Song      ║")
print("╚══════════════════════════════════════╝\n")

url = input("Paste the song URL: ").strip()
if not url:
    print("No URL entered. Exiting.")
    sys.exit(0)

# Preview info
print("\nFetching info…")
try:
    info = svc.get_info(url)
except Exception as e:
    print(f"\n✗ Could not fetch info: {e}")
    sys.exit(1)

print(f"\n  Title   : {info['title']}")
print(f"  Artist  : {info['uploader']}")
dur = info.get("duration")
print(f"  Duration: {dur}s ({dur//60}m {dur%60}s)" if dur else "  Duration: unknown")

# Pick a mood / playlist
print("\nWhich mood playlist should this song go into?\n")
with ConnectionManager() as conn:
    moods = get_all_moods(conn)
    for i, m in enumerate(moods, 1):
        print(f"  [{i}] {m.display_name}")

choice = input("\nEnter number: ").strip()
try:
    mood = moods[int(choice) - 1]
except (ValueError, IndexError):
    print("Invalid choice. Exiting.")
    sys.exit(1)

with ConnectionManager() as conn:
    playlist = get_playlist_for_mood(conn, mood.mood_id)

if not playlist:
    print(f"No active playlist found for mood '{mood.mood_code}'.")
    sys.exit(1)

print(f"\n  → Will add to: '{playlist.playlist_name}'")

# Ask for position
pos_input = input("Position in playlist (press Enter for end): ").strip()
position = int(pos_input) if pos_input.isdigit() else 99

# Legal consent — required
print("""
⚠️  LEGAL NOTICE
   Only download content you own, have purchased, or that is
   legally free to download (Creative Commons / public domain).
   Do NOT download copyrighted music you do not have rights to.
""")
consent = input("I confirm I have the legal right to download this content (yes/no): ").strip().lower()
if consent != "yes":
    print("Download cancelled. No files or DB changes made.")
    sys.exit(0)

# Download
print("\nDownloading…\n")
try:
    result = svc.import_from_url(
        url=url,
        playlist_id=playlist.playlist_id,
        position=position,
        confirmed_legal=True,
    )
    print(f"\n✅ Done!")
    print(f"   Song  : {result.song_title}")
    print(f"   File  : {result.local_file_path}")
    print(f"   Db2 ID: SONG_ID={result.song_id} in '{playlist.playlist_name}'")
except Exception as e:
    print(f"\n✗ Import failed: {e}")
    sys.exit(1)

