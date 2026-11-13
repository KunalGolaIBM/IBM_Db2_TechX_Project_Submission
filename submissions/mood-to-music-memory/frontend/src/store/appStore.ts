import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AppState, Song, Playlist, MoodMemory, PlaybackProfile } from '../types';
import { mockSongs } from '../data/mockSongs';
import { mockPlaylists } from '../data/mockPlaylists';
import { mockMemories } from '../data/mockMemories';
import { api, ApiSong, ApiMemory, ApiPlaylist } from '../api/client';

const defaultProfile: PlaybackProfile = {
  name: 'Gentle',
  volume: 0.7,
  fadeIn: '2s',
  speed: 1.0,
};

// ── Converters: API types → internal types ──────────────────────────────────

function apiSongToSong(s: ApiSong): Song {
  return {
    id: s.id,
    title: s.title,
    artist: s.artist,
    duration: s.durationSeconds ?? 180,
    artwork: '',
    mood: s.mood,
    playlistId: '',
    audioUrl: s.audioUrl ?? undefined,
    album: s.album,
  };
}

function apiPlaylistToPlaylist(p: ApiPlaylist): Playlist {
  return {
    id: p.id,
    name: p.name,
    description: p.description,
    mood: p.mood,
    songIds: [],
    coverArt: '',
    songCount: p.songCount,
  };
}

function apiMemoryToMoodMemory(m: ApiMemory): MoodMemory {
  return {
    id: m.id,
    title: m.text,
    date: m.savedAt || m.createdAt,
    mood: m.moodTag,
    songId: '',
    reflection: m.text,
    artwork: '',
    isBookmarked: false,
    songTitle: m.songTitle,
    artist: m.artist,
  };
}

// ── Store ───────────────────────────────────────────────────────────────────

interface AppActions {
  setSelectedMood: (mood: string | null) => void;
  setCustomMood: (text: string) => void;
  setCurrentSong: (song: Song | null) => void;
  setCurrentPlaylist: (playlist: Playlist | null) => void;
  togglePlay: () => void;
  setCurrentTime: (time: number) => void;
  setVolume: (volume: number) => void;
  toggleShuffle: () => void;
  toggleRepeat: () => void;
  setPlaybackProfile: (profile: PlaybackProfile) => void;
  startSession: (mood: string, playlist: Playlist) => void;
  endSession: () => void;
  addMemory: (memory: MoodMemory) => void;
  toggleBookmark: (id: string) => void;
  deleteMemory: (id: string) => void;
  nextSong: () => void;
  prevSong: () => void;
  addSong: (song: Song) => void;
  // DB2 loaders & actions
  loadSongsFromDb2: () => Promise<void>;
  loadPlaylistsFromDb2: () => Promise<void>;
  loadMemoriesFromDb2: () => Promise<void>;
  saveMemoryToDb2: (text: string, songTitle: string, artist: string, moodTag: string) => Promise<MoodMemory | null>;
  updateMemoryInDb2: (id: string, text: string, moodTag: string) => Promise<void>;
  deleteMemoryFromDb2: (id: string) => Promise<void>;
  // State flags
  db2Connected: boolean;
  db2Loading: boolean;
}

type StoreState = AppState & AppActions;

export const useAppStore = create<StoreState>()(
  persist(
    (set, get) => ({
      // ── Initial state ──
      selectedMood: 'romantic',
      customMood: '',
      currentSong: mockSongs[0],
      currentPlaylist: mockPlaylists[0],
      isPlaying: false,
      currentTime: 0,
      volume: 0.7,
      shuffleEnabled: false,
      repeatEnabled: false,
      playbackProfile: defaultProfile,
      songs: mockSongs,
      playlists: mockPlaylists,
      memories: mockMemories,
      currentSession: null,
      db2Connected: false,
      db2Loading: false,

      // ── Db2 loaders ──

      loadSongsFromDb2: async () => {
        try {
          set({ db2Loading: true });
          const apiSongs = await api.songs();
          if (apiSongs.length > 0) {
            const songs = apiSongs.map(apiSongToSong);
            set({ songs, currentSong: songs[0], db2Connected: true });
          }
        } catch {
          console.warn('[Db2] Songs API offline — using mock data');
        } finally {
          set({ db2Loading: false });
        }
      },

      loadPlaylistsFromDb2: async () => {
        try {
          const apiPlaylists = await api.playlists();
          if (apiPlaylists.length > 0) {
            const playlists = apiPlaylists.map(apiPlaylistToPlaylist);
            set({ playlists, currentPlaylist: playlists[0], db2Connected: true });
          }
        } catch {
          console.warn('[Db2] Playlists API offline — using mock data');
        }
      },

      loadMemoriesFromDb2: async () => {
        try {
          const apiMems = await api.memories();
          if (apiMems.length > 0) {
            set({ memories: apiMems.map(apiMemoryToMoodMemory), db2Connected: true });
          }
        } catch {
          console.warn('[Db2] Memories API offline — using mock data');
        }
      },

      saveMemoryToDb2: async (text, songTitle, artist, moodTag) => {
        try {
          const apiMem = await api.createMemory({
            memory_text: text,
            song_title: songTitle,
            artist,
            mood_tag: moodTag,
            saved_at: new Date().toISOString(),
          });
          const mem = apiMemoryToMoodMemory(apiMem);
          set(state => ({ memories: [mem, ...state.memories] }));
          return mem;
        } catch (e) {
          console.error('[Db2] Failed to save memory', e);
          return null;
        }
      },

      updateMemoryInDb2: async (id, text, moodTag) => {
        try {
          await api.updateMemory(id, { memory_text: text, mood_tag: moodTag });
          set(state => ({
            memories: state.memories.map(m =>
              m.id === id ? { ...m, reflection: text, title: text.slice(0, 50), mood: moodTag } : m
            ),
          }));
        } catch {
          // Local fallback
          set(state => ({
            memories: state.memories.map(m =>
              m.id === id ? { ...m, reflection: text, title: text.slice(0, 50), mood: moodTag } : m
            ),
          }));
        }
      },

      deleteMemoryFromDb2: async (id) => {
        try {
          await api.deleteMemory(id);
          set(state => ({ memories: state.memories.filter(m => m.id !== id) }));
        } catch {
          set(state => ({ memories: state.memories.filter(m => m.id !== id) }));
        }
      },

      // ── Playback actions ──
      setSelectedMood: (mood) => set({ selectedMood: mood ?? '' }),
      setCustomMood: (text) => set({ customMood: text }),
      setCurrentSong: (song) => set({ currentSong: song, currentTime: 0 }),
      setCurrentPlaylist: (playlist) => set({ currentPlaylist: playlist }),
      togglePlay: () => set((state) => ({ isPlaying: !state.isPlaying })),
      setCurrentTime: (time) => set({ currentTime: time }),
      setVolume: (volume) => set({ volume }),
      toggleShuffle: () => set((state) => ({ shuffleEnabled: !state.shuffleEnabled })),
      toggleRepeat: () => set((state) => ({ repeatEnabled: !state.repeatEnabled })),
      setPlaybackProfile: (profile) => set({ playbackProfile: profile }),

      startSession: (mood, playlist) => {
        const { playbackProfile } = get();
        set({
          selectedMood: mood,
          currentPlaylist: playlist,
          currentSession: {
            id: `session-${Date.now()}`,
            mood,
            playlistId: playlist.id,
            playbackProfile,
            startedAt: new Date().toISOString(),
          },
          isPlaying: true,
        });
        api.sessionStart(mood).catch(() => {});
        const { songs } = get();
        const firstSong = songs.find(s => s.mood === mood) || songs[0] || null;
        if (firstSong) set({ currentSong: firstSong, currentTime: 0 });
      },

      endSession: () => {
        const { currentSession } = get();
        if (currentSession) {
          const id = parseInt(currentSession.id.replace('session-', ''), 10);
          if (!isNaN(id)) api.sessionEnd(id).catch(() => {});
        }
        set({ currentSession: null, isPlaying: false });
      },

      addMemory: (memory) =>
        set((state) => ({ memories: [memory, ...state.memories] })),

      toggleBookmark: (id) =>
        set((state) => ({
          memories: state.memories.map((m) =>
            m.id === id ? { ...m, isBookmarked: !m.isBookmarked } : m
          ),
        })),

      deleteMemory: (id) =>
        set((state) => ({
          memories: state.memories.filter((m) => m.id !== id),
        })),

      nextSong: () => {
        const { currentSong, currentPlaylist, songs, shuffleEnabled } = get();
        if (!currentPlaylist || !currentSong) return;
        const playlistSongs = songs.filter((s) => s.mood === currentPlaylist.mood);
        if (playlistSongs.length === 0) return;
        if (shuffleEnabled) {
          set({ currentSong: playlistSongs[Math.floor(Math.random() * playlistSongs.length)], currentTime: 0 });
        } else {
          const idx = playlistSongs.findIndex((s) => s.id === currentSong.id);
          set({ currentSong: playlistSongs[(idx + 1) % playlistSongs.length], currentTime: 0 });
        }
      },

      prevSong: () => {
        const { currentSong, currentPlaylist, songs, currentTime } = get();
        if (!currentPlaylist || !currentSong) return;
        if (currentTime > 3) { set({ currentTime: 0 }); return; }
        const playlistSongs = songs.filter((s) => s.mood === currentPlaylist.mood);
        if (playlistSongs.length === 0) return;
        const idx = playlistSongs.findIndex((s) => s.id === currentSong.id);
        set({ currentSong: playlistSongs[(idx - 1 + playlistSongs.length) % playlistSongs.length], currentTime: 0 });
      },

      addSong: (song) =>
        set((state) => ({ songs: [...state.songs, song] })),
    }),
    {
      name: 'mood-to-music-storage',
      partialize: (state) => ({
        selectedMood: state.selectedMood,
        volume: state.volume,
        playbackProfile: state.playbackProfile,
        memories: state.memories,
      }),
    }
  )
);
