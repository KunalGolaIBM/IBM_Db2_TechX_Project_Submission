"""
src/ui/app.py
-------------
Tkinter desktop frontend for Mood-to-Music Memory.

Window flow:
  1. Mood picker — 5 big buttons (Sad / Happy / Romantic / Wholesome / Ghazal)
     + optional free-text box → AI interprets it via LangChain + Ollama
  2. Now Playing screen — song title, artist, playlist name, controls
     (Pause/Resume, Skip, Volume slider, Change Mood, Stop)

Run:
    python src/ui/app.py
"""

from __future__ import annotations
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

sys.path.insert(0, ".")

from src.db.connection import ConnectionManager
from src.db.queries import get_all_moods, Mood, Song
from src.services.playback import PlaybackService

# ── Colour palette ───────────────────────────────────────────────────
BG        = "#1a1a2e"   # dark navy
CARD      = "#16213e"   # slightly lighter panel
ACCENT    = "#e94560"   # vibrant pink-red
BTN_FG    = "#ffffff"
TEXT_PRI  = "#eaeaea"
TEXT_SEC  = "#a0a0b0"

MOOD_COLOURS = {
    "sad":       "#4a90d9",   # cool blue
    "happy":     "#f5a623",   # warm amber
    "romantic":  "#e94560",   # rose
    "wholesome": "#7ed321",   # fresh green
    "ghazal":    "#9b59b6",   # purple
}

MOOD_EMOJI = {
    "sad": "😢", "happy": "😄",
    "romantic": "💕", "wholesome": "🌻", "ghazal": "🎶",
}

FONT_TITLE   = ("Segoe UI", 22, "bold")
FONT_HEADING = ("Segoe UI", 14, "bold")
FONT_BODY    = ("Segoe UI", 11)
FONT_SMALL   = ("Segoe UI", 9)
FONT_BTN     = ("Segoe UI", 12, "bold")
FONT_MOOD    = ("Segoe UI", 13, "bold")


class MoodMusicApp(tk.Tk):
    """Root window — manages switching between screens."""

    def __init__(self):
        super().__init__()
        self.title("Mood-to-Music Memory")
        self.geometry("560x600")
        self.minsize(480, 520)
        self.configure(bg=BG)
        self.resizable(True, True)

        self._playback = PlaybackService()
        self._moods: list[Mood] = []
        self._current_frame: Optional[tk.Frame] = None

        self._load_moods()
        self._show_mood_picker()

        # Tick playback every second (auto-advance songs)
        self._tick()

    # ── Mood data ───────────────────────────────────────────────────

    def _load_moods(self) -> None:
        try:
            with ConnectionManager() as conn:
                self._moods = get_all_moods(conn)
        except Exception as e:
            messagebox.showerror("Db2 Error", f"Cannot connect to Db2:\n{e}")
            self.destroy()

    # ── Screen switching ────────────────────────────────────────────

    def _switch(self, frame: tk.Frame) -> None:
        if self._current_frame:
            self._current_frame.destroy()
        self._current_frame = frame
        frame.pack(fill="both", expand=True)

    def _show_mood_picker(self) -> None:
        self._switch(MoodPickerFrame(self))

    def _show_now_playing(self, mood_code: str) -> None:
        try:
            self._playback.play_for_mood(mood_code)
            self._switch(NowPlayingFrame(self, self._playback))
        except FileNotFoundError as e:
            messagebox.showwarning(
                "No local files",
                f"{e}\n\nAdd real MP3 paths via 'Import Song' or update Db2 paths."
            )
        except Exception as e:
            messagebox.showerror("Playback error", str(e))

    # ── Tick ────────────────────────────────────────────────────────

    def _tick(self) -> None:
        self._playback.tick()
        if isinstance(self._current_frame, NowPlayingFrame):
            self._current_frame.refresh()
        self.after(1000, self._tick)


# ── Mood Picker ─────────────────────────────────────────────────────

class MoodPickerFrame(tk.Frame):

    def __init__(self, app: MoodMusicApp):
        super().__init__(app, bg=BG)
        self._app = app
        self._build()

    def _build(self) -> None:
        # Header
        tk.Label(self, text="🎵 Mood-to-Music Memory",
                 font=FONT_TITLE, bg=BG, fg=TEXT_PRI).pack(pady=(30, 4))
        tk.Label(self, text="How are you feeling right now?",
                 font=FONT_BODY, bg=BG, fg=TEXT_SEC).pack(pady=(0, 24))

        # Mood buttons
        btn_frame = tk.Frame(self, bg=BG)
        btn_frame.pack()

        for i, mood in enumerate(self._app._moods):
            colour = MOOD_COLOURS.get(mood.mood_code, ACCENT)
            emoji  = MOOD_EMOJI.get(mood.mood_code, "🎵")
            btn = tk.Button(
                btn_frame,
                text=f"{emoji}  {mood.display_name}",
                font=FONT_MOOD,
                bg=colour, fg=BTN_FG,
                activebackground=colour, activeforeground=BTN_FG,
                relief="flat", bd=0,
                width=22, pady=12,
                cursor="hand2",
                command=lambda c=mood.mood_code: self._on_mood(c),
            )
            btn.grid(row=i, column=0, pady=6, padx=40)
            # hover effect
            btn.bind("<Enter>", lambda e, b=btn, c=colour: b.configure(bg=_darken(c)))
            btn.bind("<Leave>", lambda e, b=btn, c=colour: b.configure(bg=c))

        # Divider + free-text
        tk.Frame(self, bg=TEXT_SEC, height=1).pack(fill="x", padx=40, pady=(28, 16))
        tk.Label(self, text="Or describe your mood in your own words:",
                 font=FONT_SMALL, bg=BG, fg=TEXT_SEC).pack()

        self._text_var = tk.StringVar()
        entry_frame = tk.Frame(self, bg=CARD, bd=0)
        entry_frame.pack(padx=40, pady=8, fill="x")
        entry = tk.Entry(entry_frame, textvariable=self._text_var,
                         font=FONT_BODY, bg=CARD, fg=TEXT_PRI,
                         insertbackground=TEXT_PRI, relief="flat",
                         bd=8)
        entry.pack(side="left", fill="x", expand=True)
        tk.Button(entry_frame, text="→", font=FONT_BTN,
                  bg=ACCENT, fg=BTN_FG, relief="flat", bd=0,
                  cursor="hand2",
                  command=self._on_text_mood).pack(side="right", padx=(0, 4))

        entry.bind("<Return>", lambda e: self._on_text_mood())

        tk.Label(self, text="v1.0  ·  IBM Db2Hack 2026",
                 font=FONT_SMALL, bg=BG, fg=TEXT_SEC).pack(side="bottom", pady=12)

    def _on_mood(self, mood_code: str) -> None:
        self._app._show_now_playing(mood_code)

    def _on_text_mood(self) -> None:
        text = self._text_var.get().strip()
        if not text:
            return
        # Try AI interpreter, fall back to 'happy'
        def interpret():
            try:
                from src.ai.mood_interpreter import MoodInterpreter
                interp = MoodInterpreter()
                code = interp.interpret(text)
            except Exception:
                code = "happy"
            self._app.after(0, lambda: self._app._show_now_playing(code))

        threading.Thread(target=interpret, daemon=True).start()
        self._show_thinking()

    def _show_thinking(self) -> None:
        """Replace button row with a spinner-style label briefly."""
        for widget in self.winfo_children():
            if isinstance(widget, tk.Label) and "Thinking" in str(widget.cget("text")):
                return
        tk.Label(self, text="🤔  Thinking…", font=FONT_BODY,
                 bg=BG, fg=ACCENT).pack()


# ── Now Playing ─────────────────────────────────────────────────────

class NowPlayingFrame(tk.Frame):

    def __init__(self, app: MoodMusicApp, svc: PlaybackService):
        super().__init__(app, bg=BG)
        self._app = app
        self._svc = svc
        self._paused = False
        self._vol_var = tk.IntVar(value=svc._profile_volume)
        self._build()
        self.refresh()

    def _build(self) -> None:
        # Back button
        tk.Button(self, text="← Change Mood", font=FONT_SMALL,
                  bg=BG, fg=TEXT_SEC, relief="flat", bd=0, cursor="hand2",
                  command=self._change_mood).pack(anchor="nw", padx=16, pady=(14, 0))

        # Album art placeholder
        self._art_label = tk.Label(self, text="🎵", font=("Segoe UI Emoji", 64),
                                   bg=CARD, width=5, height=2)
        self._art_label.pack(pady=(10, 8))

        # Song info
        self._title_lbl = tk.Label(self, text="Loading…",
                                   font=FONT_HEADING, bg=BG, fg=TEXT_PRI,
                                   wraplength=440)
        self._title_lbl.pack()

        self._artist_lbl = tk.Label(self, text="",
                                    font=FONT_BODY, bg=BG, fg=TEXT_SEC)
        self._artist_lbl.pack(pady=(2, 0))

        self._playlist_lbl = tk.Label(self, text="",
                                      font=FONT_SMALL, bg=BG, fg=ACCENT)
        self._playlist_lbl.pack(pady=(2, 20))

        # Volume
        vol_frame = tk.Frame(self, bg=BG)
        vol_frame.pack(fill="x", padx=60, pady=(0, 16))
        tk.Label(vol_frame, text="🔈", font=FONT_BODY, bg=BG, fg=TEXT_SEC).pack(side="left")
        tk.Scale(vol_frame, from_=0, to=100, orient="horizontal",
                 variable=self._vol_var, bg=BG, fg=TEXT_PRI,
                 troughcolor=CARD, highlightthickness=0, bd=0,
                 command=self._on_volume).pack(side="left", fill="x", expand=True, padx=8)
        tk.Label(vol_frame, text="🔊", font=FONT_BODY, bg=BG, fg=TEXT_SEC).pack(side="left")

        # Controls
        ctrl = tk.Frame(self, bg=BG)
        ctrl.pack(pady=8)

        self._pause_btn = tk.Button(
            ctrl, text="⏸  Pause", font=FONT_BTN,
            bg=ACCENT, fg=BTN_FG, relief="flat", bd=0,
            padx=18, pady=10, cursor="hand2",
            command=self._toggle_pause,
        )
        self._pause_btn.grid(row=0, column=0, padx=8)

        tk.Button(ctrl, text="⏭  Skip", font=FONT_BTN,
                  bg=CARD, fg=BTN_FG, relief="flat", bd=0,
                  padx=18, pady=10, cursor="hand2",
                  command=self._skip).grid(row=0, column=1, padx=8)

        tk.Button(ctrl, text="⏹  Stop", font=FONT_BTN,
                  bg="#444", fg=BTN_FG, relief="flat", bd=0,
                  padx=18, pady=10, cursor="hand2",
                  command=self._stop).grid(row=0, column=2, padx=8)

        # Status bar
        self._status_lbl = tk.Label(self, text="",
                                    font=FONT_SMALL, bg=BG, fg=TEXT_SEC)
        self._status_lbl.pack(side="bottom", pady=12)

    # ── Controls ────────────────────────────────────────────────────

    def _toggle_pause(self) -> None:
        if self._paused:
            self._svc.resume()
            self._pause_btn.configure(text="⏸  Pause")
            self._paused = False
        else:
            self._svc.pause()
            self._pause_btn.configure(text="▶  Resume")
            self._paused = True

    def _skip(self) -> None:
        self._svc.skip()
        self._paused = False
        self._pause_btn.configure(text="⏸  Pause")
        self.refresh()

    def _stop(self) -> None:
        self._svc.stop()
        self._app._show_mood_picker()

    def _change_mood(self) -> None:
        self._svc.stop(feedback="mood_change")
        self._app._show_mood_picker()

    def _on_volume(self, val) -> None:
        self._svc.set_volume(int(val))

    # ── Refresh ─────────────────────────────────────────────────────

    def refresh(self) -> None:
        song = self._svc.current_song
        if song:
            self._title_lbl.configure(text=song.song_title)
            self._artist_lbl.configure(text=song.artist)
            self._status_lbl.configure(
                text=f"Track {self._svc._index + 1} of {len(self._svc._playlist)}"
                     f"  ·  {'▶ Playing' if self._svc.is_playing else '⏸ Paused'}"
            )
        else:
            self._title_lbl.configure(text="Playlist finished")
            self._artist_lbl.configure(text="")
            self._status_lbl.configure(text="All songs played")


# ── Helpers ─────────────────────────────────────────────────────────

def _darken(hex_colour: str, factor: float = 0.8) -> str:
    """Return a slightly darker version of a hex colour."""
    hex_colour = hex_colour.lstrip("#")
    r, g, b = (int(hex_colour[i:i+2], 16) for i in (0, 2, 4))
    return "#{:02x}{:02x}{:02x}".format(
        int(r * factor), int(g * factor), int(b * factor)
    )


# ── Entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    app = MoodMusicApp()
    app.mainloop()

