# Mood-to-Music Memory

> A personal desktop music companion that connects an explicitly selected mood
> to a Db2-backed playlist and helps preserve the moments that mattered.

## Problem Statement

Music applications usually make users search for a track before they can
listen. Mood-to-Music Memory reverses that interaction: the user selects how
they feel, receives a matching playlist and playback profile, and can save the
listening moment with a personal reflection. The target audience is anyone who
wants a more intentional music-listening and journaling experience.

The application does not claim to diagnose or infer a person's mental-health
state. Mood selection remains an explicit user action.

## Solution Overview

- Select Sad, Happy, Romantic, Wholesome, or Ghazal.
- Load the matching playlist and playback profile from IBM Db2.
- Browse songs, playlists, memories, and listening analytics in a React UI.
- Save a song, mood, timestamp, and reflection as a music memory.
- Import user-authorized media with `yt-dlp`; audio stays on the local machine.
- Optionally interpret free-text mood descriptions with a local Ollama model.

The React interface currently uses local mock data for its browser-only
demonstration. The Python services and Db2 scripts provide the database-backed
integration path and are the source of truth for the data model.

## IBM Db2 Integration

- **Environment:** Db2 Community Edition locally or in Docker.
- **Driver:** Python `ibm_db`.
- **Schema:** `db/schema.sql` creates the `MOODMUSIC` schema tables for moods,
  playlists, playback profiles, songs, playlist membership, playback sessions,
  and memories.
- **Operations:** `src/db/queries.py` uses prepared statements and bound
  parameters for mood lookup, playlist/profile retrieval, ordered songs,
  session tracking, and memory persistence.
- **Storage boundary:** Db2 stores song metadata and local paths. Audio bytes
  remain on the user's computer.

## AI / LLM Architecture

The deterministic mood-to-playlist flow works without an AI model. The
optional `src/ai/mood_interpreter.py` integration uses LangChain and a local
Ollama model to map a user's free-text description to one of the supported
mood codes. The user remains in control and the model does not make clinical
inferences or silently change saved playlist membership.

## Tech Stack

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Framer Motion,
  React Router, Zustand, and Lucide.
- **Db2 services:** Python 3.11+, `ibm_db`, `python-dotenv`.
- **Optional AI:** LangChain, `langchain-ollama`, and Ollama.
- **Media import/playback utilities:** `yt-dlp` and `pygame`.

## Prerequisites

- Python 3.11 or newer.
- Node.js and pnpm.
- A reachable IBM Db2 Community Edition instance.
- Optional: Ollama with `llama3.2:3b` for free-text mood interpretation.

## Setup

From this directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with local Db2 credentials. Do not commit `.env` or real secrets.

Initialize and seed Db2:

```powershell
python db\check_db2.py
python db\setup_db2.py
python db\seed_db.py
```

Install and run the frontend:

```powershell
cd frontend
pnpm install
pnpm run dev
```

Open the Vite URL printed in the terminal, normally
`http://localhost:5173`.

## Verification

Run the Db2-backed smoke test after initializing and seeding the database:

```powershell
python smoke_test.py
```

The smoke test checks the Db2 connection, all five mood records, playlist and
playback-profile lookup, ordered songs, and the optional Ollama interpreter.
The Ollama checks require a running local model.

## Screenshots and Demo

No hosted demo or video is included yet. Screenshots can be added under
`docs/screenshots/`.

## Known Limitations and Roadmap

- The browser UI currently uses mock data and is not yet connected to a REST
  backend.
- Browser audio playback and persistent frontend storage are still planned.
- Analytics are currently demonstration data.
- Future work includes a REST bridge, real audio playback, semantic memory
  retrieval, and a native Electron or Tauri shell.

## License and Credits

This submission is provided as a personal project for the IBM Db2 TechX
Summit 2026 challenge. Third-party dependencies retain their respective
licenses. Created by [NotTushar-dotcom](https://github.com/NotTushar-dotcom).
