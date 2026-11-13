# Architecture

## Product goal

When the desktop application opens, a user chooses their current mood. The
application retrieves the user's matching playlist from IBM Db2, loads local
song files, applies the playlist's playback profile, and starts playing music.
The user can pause, skip, change volume, or choose another mood.

The first release should use explicit mood buttons rather than claiming to
detect a person's mental-health state. A later text input can interpret mood
language as a convenience, but the user must remain in control.

## Db2 responsibility

Db2 is the system of record for:

- Mood categories and their playlist mappings
- Playlist metadata and ordering
- Song title, artist, duration, and local file path
- Playback profiles such as volume and playback speed
- Playback sessions and optional feedback
- The user's saved music-memory text and attached songs
- Embeddings used for optional semantic memory retrieval

Audio files themselves remain on the user's computer in the MVP. Db2 stores
their paths and metadata rather than large binary audio objects.

## Technology choices

- **Langflow with `lfx-ibm`:** the single AI/orchestration framework, used later
  for optional mood-text interpretation and memory retrieval.
- **IBM Db2 with `ibm_db`:** the system of record and database driver.
- **`yt-dlp`:** imports user-authorized media into the local music folder.
- **Desktop player:** plays local files and applies the Db2 playback profile.

`yt-dlp` is an import utility, not an AI framework. The MVP's deterministic
mood-to-playlist path does not need an AI model.

## Application flow

1. The desktop shell opens and displays mood choices.
2. The backend validates the selected mood.
3. A parameterised Db2 query finds the active playlist and playback profile.
4. The backend loads the ordered songs and checks each local path.
5. The player starts the first available song using the profile settings.
6. Playback controls update the local player; meaningful events may be saved to
   Db2.

## Media import flow

1. The user pastes a URL or chooses a local audio file.
2. The backend verifies that the import is permitted and the URL is supported.
3. `yt-dlp` downloads permitted media into the configured music folder.
4. The backend extracts title, artist, duration, and source URL.
5. Db2 stores metadata and the local path; the audio bytes stay on disk.
6. The user explicitly assigns the song to one or more mood playlists.

## Langflow and AI responsibility

Langflow is not required for the deterministic MVP path. When included, it can
orchestrate optional mood-text interpretation or semantic retrieval of a
similar saved memory. It must not autonomously change a playlist or infer a
clinical condition.

Saving a new memory, changing playlist membership, and enabling automatic
startup are explicit user actions.
