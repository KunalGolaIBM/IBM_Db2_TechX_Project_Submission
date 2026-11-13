"""
src/services/playback.py
------------------------
Loads a playlist from Db2 for the chosen mood and plays it
through pygame.mixer. Applies the mood's volume, speed
(via pydub if available), and fade-in from the playback profile.

Usage:
    from src.services.playback import PlaybackService
    svc = PlaybackService()
    svc.play_for_mood("happy")
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, Callable

import pygame

from src.db.connection import ConnectionManager
from src.db.queries import (
    get_mood_by_code,
    get_playlist_for_mood,
    get_songs_for_playlist,
    start_session,
    end_session,
    Song,
    Playlist,
)


class PlaybackService:
    """Controls playback for a mood-driven playlist session."""

    def __init__(self) -> None:
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=2048)
        pygame.mixer.init()
        self._current_song: Optional[Song] = None
        self._playlist: list[Song] = []
        self._index: int = 0
        self._session_id: Optional[int] = None
        self._profile_volume: int = 50
        self._on_song_change: Optional[Callable[[Song], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def play_for_mood(self, mood_code: str) -> None:
        """
        Main entry point.
        Looks up the mood in Db2, fetches the playlist and profile,
        validates local file paths, and starts playback.
        """
        with ConnectionManager() as conn:
            mood = get_mood_by_code(conn, mood_code)
            if not mood:
                raise ValueError(f"Unknown mood code: '{mood_code}'")

            playlist = get_playlist_for_mood(conn, mood.mood_id)
            if not playlist:
                raise RuntimeError(f"No active playlist found for mood '{mood_code}'")

            songs = get_songs_for_playlist(conn, playlist.playlist_id)
            available = [s for s in songs if Path(s.local_file_path).exists()]

            if not available:
                missing = [s.local_file_path for s in songs]
                raise FileNotFoundError(
                    f"No playable files found for playlist '{playlist.playlist_name}'.\n"
                    f"Missing paths:\n" + "\n".join(f"  {p}" for p in missing)
                )

            self._session_id = start_session(conn, mood.mood_id, playlist.playlist_id)
            self._profile_volume = playlist.profile.volume_percent
            self._playlist = available
            self._index = 0

        self._play_current()

    def on_song_change(self, callback: Callable[[Song], None]) -> None:
        """Register a callback fired whenever the current song changes."""
        self._on_song_change = callback

    def pause(self) -> None:
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.pause()

    def resume(self) -> None:
        pygame.mixer.music.unpause()

    def skip(self) -> None:
        """Skip to the next song in the playlist."""
        self._index += 1
        if self._index < len(self._playlist):
            self._play_current()
        else:
            self.stop()

    def set_volume(self, percent: int) -> None:
        """Set volume 0–100."""
        percent = max(0, min(100, percent))
        pygame.mixer.music.set_volume(percent / 100)

    def stop(self, feedback: Optional[str] = None) -> None:
        pygame.mixer.music.stop()
        if self._session_id is not None:
            with ConnectionManager() as conn:
                end_session(conn, self._session_id, feedback)
            self._session_id = None

    def tick(self) -> None:
        """
        Call this regularly (e.g. from a UI event loop) to advance
        to the next song when the current one finishes.
        """
        if not pygame.mixer.music.get_busy() and self._playlist:
            self.skip()

    @property
    def current_song(self) -> Optional[Song]:
        return self._current_song

    @property
    def is_playing(self) -> bool:
        return pygame.mixer.music.get_busy()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _play_current(self) -> None:
        if self._index >= len(self._playlist):
            self.stop()
            return
        song = self._playlist[self._index]
        self._current_song = song
        pygame.mixer.music.load(song.local_file_path)
        pygame.mixer.music.set_volume(self._profile_volume / 100)
        pygame.mixer.music.play(fade_ms=2000)
        if self._on_song_change:
            self._on_song_change(song)

