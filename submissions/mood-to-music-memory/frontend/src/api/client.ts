/**
 * src/api/client.ts
 * -----------------
 * Thin fetch wrapper for the FastAPI / Db2 backend.
 * Falls back to mock data gracefully when the backend is offline.
 */

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Typed helpers ─────────────────────────────────────────────────────────

export interface ApiSong {
  id: string;
  title: string;
  artist: string;
  album: string;
  duration: string;
  durationSeconds: number | null;
  mood: string;
  moodDisplay: string;
  playlist: string;
  localFilePath: string;
  audioUrl: string | null;
}

export interface ApiPlaylist {
  id: string;
  name: string;
  description: string;
  mood: string;
  moodDisplay: string;
  songCount: number;
  volume: number;
}

export interface ApiMemory {
  id: string;
  text: string;
  songTitle: string;
  artist: string;
  moodTag: string;
  savedAt: string;
  createdAt: string;
}

export interface ApiAnalytics {
  totalSessions: number;
  totalMemories: number;
  totalSongs: number;
  mostPlayedMood: string;
  moodDistribution: { mood: string; moodDisplay: string; count: number }[];
  recentSessions: {
    sessionId: number;
    mood: string;
    moodDisplay: string;
    startedAt: string;
    endedAt: string;
    feedback: string;
  }[];
  topSongs: { title: string; artist: string; appearances: number }[];
}

// ── API calls ──────────────────────────────────────────────────────────────

export const api = {
  health: () => apiFetch<{ status: string }>('/api/health'),

  songs: (mood?: string) =>
    apiFetch<ApiSong[]>(`/api/songs${mood ? `?mood=${encodeURIComponent(mood)}` : ''}`),

  playlists: () => apiFetch<ApiPlaylist[]>('/api/playlists'),

  playlistSongs: (id: string | number) =>
    apiFetch<ApiSong[]>(`/api/playlists/${id}/songs`),

  memories: (mood?: string) =>
    apiFetch<ApiMemory[]>(`/api/memories${mood ? `?mood=${encodeURIComponent(mood)}` : ''}`),

  createMemory: (body: {
    memory_text: string;
    song_title: string;
    artist: string;
    mood_tag: string;
    saved_at?: string;
  }) => apiFetch<ApiMemory>('/api/memories', { method: 'POST', body: JSON.stringify(body) }),

  updateMemory: (id: string, body: { memory_text?: string; mood_tag?: string }) =>
    apiFetch<{ ok: boolean }>(`/api/memories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deleteMemory: (id: string) =>
    apiFetch<{ ok: boolean }>(`/api/memories/${id}`, { method: 'DELETE' }),

  similarMemories: (id: string, k = 3) =>
    apiFetch<ApiMemory[]>(`/api/memories/${id}/similar?k=${k}`),

  detectMood: (text: string) =>
    apiFetch<{ mood_code: string; source: string }>('/api/detect-mood', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),

  sessionStart: (mood_code: string) =>
    apiFetch<{ session_id: number; mood_id: number; playlist_id: number }>(
      '/api/session/start',
      { method: 'POST', body: JSON.stringify({ mood_code }) }
    ),

  sessionEnd: (session_id: number, feedback?: string) =>
    apiFetch<{ ok: boolean }>('/api/session/end', {
      method: 'POST',
      body: JSON.stringify({ session_id, feedback }),
    }),

  analytics: () => apiFetch<ApiAnalytics>('/api/analytics'),

  importSong: (body: {
    song_title: string;
    artist: string;
    album?: string;
    local_file_path: string;
    duration_seconds?: number;
    mood_code: string;
  }) =>
    apiFetch<{ song_id: number; title: string; artist: string }>('/api/songs/import', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

