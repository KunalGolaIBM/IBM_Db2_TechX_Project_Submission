import { create } from 'zustand';
import { AppState, Song, Playlist, MoodMemory, PlaybackProfile } from '../types';
import { mockSongs } from '../data/mockSongs';
import { mockPlaylists } from '../data/mockPlaylists';
import { mockMemories } from '../data/mockMemories';

const defaultProfile: PlaybackProfile = {
  name: 'Gentle',
  volume: 0.7,
  fadeIn: '2s',
  speed: 1.0,
};

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
}

type StoreState = AppState & AppActions;

export const useAppStore = create<StoreState>((set, get) => ({
  // Initial state
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

  // Actions
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
    // Set the first song of the playlist
    const { songs } = get();
    const firstSongId = playlist.songIds[0];
    const firstSong = songs.find((s) => s.id === firstSongId) || null;
    if (firstSong) {
      set({ currentSong: firstSong, currentTime: 0 });
    }
  },

  endSession: () => set({ currentSession: null, isPlaying: false }),

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
    const playlistSongs = songs.filter((s) =>
      currentPlaylist.songIds.includes(s.id)
    );
    if (playlistSongs.length === 0) return;
    if (shuffleEnabled) {
      const randomIndex = Math.floor(Math.random() * playlistSongs.length);
      set({ currentSong: playlistSongs[randomIndex], currentTime: 0 });
    } else {
      const currentIndex = playlistSongs.findIndex((s) => s.id === currentSong.id);
      const nextIndex = (currentIndex + 1) % playlistSongs.length;
      set({ currentSong: playlistSongs[nextIndex], currentTime: 0 });
    }
  },

  prevSong: () => {
    const { currentSong, currentPlaylist, songs, currentTime } = get();
    if (!currentPlaylist || !currentSong) return;
    // If more than 3s played, restart; otherwise go to previous
    if (currentTime > 3) {
      set({ currentTime: 0 });
      return;
    }
    const playlistSongs = songs.filter((s) =>
      currentPlaylist.songIds.includes(s.id)
    );
    if (playlistSongs.length === 0) return;
    const currentIndex = playlistSongs.findIndex((s) => s.id === currentSong.id);
    const prevIndex = (currentIndex - 1 + playlistSongs.length) % playlistSongs.length;
    set({ currentSong: playlistSongs[prevIndex], currentTime: 0 });
  },

  addSong: (song) =>
    set((state) => ({ songs: [...state.songs, song] })),
}));
