from backend.db import exec_sql, fetch_all, exec_immediate
import ibm_db

stmt = exec_sql("SELECT SONG_ID, SONG_TITLE, ARTIST, LOCAL_FILE_PATH FROM MOODMUSIC.SONGS ORDER BY SONG_ID")
songs = fetch_all(stmt)
print(f"Total songs: {len(songs)}")
for s in songs:
    print(f"  [{s['SONG_ID']}] {s['SONG_TITLE']} - {s['ARTIST']}")

stmt2 = exec_sql("SELECT pl.PLAYLIST_ID, pl.PLAYLIST_NAME, m.MOOD_CODE FROM MOODMUSIC.PLAYLISTS pl JOIN MOODMUSIC.MOOD_PLAYLISTS mp ON pl.PLAYLIST_ID = mp.PLAYLIST_ID JOIN MOODMUSIC.MOODS m ON mp.MOOD_ID = m.MOOD_ID ORDER BY pl.PLAYLIST_ID")
playlists = fetch_all(stmt2)
print(f"\nTotal playlists: {len(playlists)}")
for p in playlists:
    print(f"  [{p['PLAYLIST_ID']}] {p['PLAYLIST_NAME']} ({p['MOOD_CODE']})")
