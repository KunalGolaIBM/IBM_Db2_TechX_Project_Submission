"""
src/services/media_import.py
----------------------------
Downloads audio from a URL using yt-dlp, extracts metadata,
and stores the song + file path in IBM Db2.

LEGAL NOTICE
------------
Only use this feature for content you own, have purchased,
or that is freely and legally available (e.g. Creative Commons
licensed YouTube videos, your own uploads, public domain music).
Do NOT use it to bypass DRM, subscriptions, or platform access
controls. The app shows a consent prompt before every download.

Usage:
    from src.services.media_import import MediaImportService
    svc = MediaImportService()
    song = svc.import_from_url(
        url="https://www.youtube.com/watch?v=EXAMPLE",
        playlist_id=2,          # which playlist to add it to
        position=3,             # order within that playlist
        confirmed_legal=True,   # user must explicitly confirm
    )
    print(song.song_title, song.local_file_path)
"""

from __future__ import annotations
import os
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import yt_dlp

from src.db.connection import ConnectionManager
from src.db.queries import insert_song, add_song_to_playlist, Song

# Where downloaded audio files are saved
MUSIC_DIR = Path(os.getenv("MUSIC_DIR", r"d:\mood-to-music-memory\music"))


@dataclass
class ImportResult:
    song_id: int
    song_title: str
    artist: str
    album: str
    local_file_path: str
    duration_seconds: Optional[int]
    source_url: str


class MediaImportService:
    """
    Downloads permitted audio and registers it in Db2.

    Parameters
    ----------
    music_dir : Path
        Folder where audio files are saved. Defaults to MUSIC_DIR.
    """

    def __init__(self, music_dir: Path = MUSIC_DIR) -> None:
        self.music_dir = Path(music_dir)
        self.music_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_info(self, url: str) -> dict:
        """
        Fetch metadata WITHOUT downloading — use to preview
        what will be downloaded before the user confirms.
        Returns a dict with keys: title, uploader, duration, thumbnail.
        """
        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "nocheckcertificate": True,   # bypass SSL verification
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "title":    info.get("title", "Unknown Title"),
            "uploader": info.get("uploader") or info.get("channel", "Unknown Artist"),
            "duration": info.get("duration"),          # seconds
            "thumbnail": info.get("thumbnail", ""),
            "webpage_url": info.get("webpage_url", url),
        }

    def import_from_url(
        self,
        url: str,
        playlist_id: int,
        position: int,
        confirmed_legal: bool = False,
    ) -> ImportResult:
        """
        Download audio from url, save to MUSIC_DIR, insert into Db2,
        and link to the given playlist at the given position.

        Parameters
        ----------
        url : str
            The video/audio URL to download from.
        playlist_id : int
            Db2 PLAYLIST_ID to link the new song to.
        position : int
            Order position within the playlist.
        confirmed_legal : bool
            Must be True — the user has confirmed they have the right
            to download this content. Import is blocked if False.

        Raises
        ------
        PermissionError
            If confirmed_legal is False.
        RuntimeError
            If the download fails or the output file is not found.
        """
        if not confirmed_legal:
            raise PermissionError(
                "Import blocked. You must confirm that you own this content "
                "or have legal permission to download it before proceeding."
            )

        print(f"[Import] Fetching info for: {url}")
        info = self.get_info(url)
        title    = info["title"]
        artist   = info["uploader"]
        duration = info["duration"]

        print(f"[Import] Title   : {title}")
        print(f"[Import] Artist  : {artist}")
        print(f"[Import] Duration: {duration}s")
        print(f"[Import] Downloading audio…")

        # Build a safe filename from the title
        safe_name = _safe_filename(title)
        output_template = str(self.music_dir / f"{safe_name}.%(ext)s")

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": False,
            "no_warnings": False,
            "nocheckcertificate": True,   # bypass SSL verification
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Find the downloaded file
        expected = self.music_dir / f"{safe_name}.mp3"
        if not expected.exists():
            # yt-dlp may have kept a different extension
            matches = list(self.music_dir.glob(f"{safe_name}.*"))
            if not matches:
                raise RuntimeError(
                    f"Download appeared to succeed but no file found "
                    f"matching '{safe_name}.*' in {self.music_dir}"
                )
            expected = matches[0]

        file_path = str(expected)
        print(f"[Import] Saved to: {file_path}")

        # Insert into Db2
        with ConnectionManager() as conn:
            song_id = insert_song(
                conn,
                title=title,
                artist=artist,
                album="",
                file_path=file_path,
                duration=duration,
            )
            add_song_to_playlist(conn, playlist_id, song_id, position)

        print(f"[Import] ✓ Saved to Db2 — SONG_ID={song_id}, linked to playlist {playlist_id}")

        return ImportResult(
            song_id=song_id,
            song_title=title,
            artist=artist,
            album="",
            local_file_path=file_path,
            duration_seconds=duration,
            source_url=url,
        )

    def import_local_file(
        self,
        file_path: str,
        title: str,
        artist: str,
        playlist_id: int,
        position: int,
        album: str = "",
        duration: Optional[int] = None,
    ) -> ImportResult:
        """
        Register an existing local audio file into Db2 without downloading.
        Use this if you already have the MP3 on your disk.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with ConnectionManager() as conn:
            song_id = insert_song(conn, title, artist, album, str(path), duration)
            add_song_to_playlist(conn, playlist_id, song_id, position)

        print(f"[Import] ✓ Registered '{title}' — SONG_ID={song_id}")

        return ImportResult(
            song_id=song_id,
            song_title=title,
            artist=artist,
            album=album,
            local_file_path=str(path),
            duration_seconds=duration,
            source_url="local",
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_filename(name: str, max_len: int = 80) -> str:
    """Strip characters that are invalid in Windows filenames."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.strip(". ")
    return name[:max_len] if len(name) > max_len else name

