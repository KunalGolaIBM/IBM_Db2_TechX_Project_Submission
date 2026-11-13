export interface Song {
  id: string;
  title: string;
  artist: string;
  duration: number;
  artwork: string;
  mood: string;
  playlistId: string;
}

export interface Playlist {
  id: string;
  name: string;
  mood: string;
  songIds: string[];
}

export interface MoodMemory {
  id: string;
  title: string;
  date: string;
  mood: string;
  songId: string;
  reflection: string;
  artwork: string;
  isBookmarked: boolean;
}

export interface PlaybackProfile {
  name: string;
  volume: number;
  fadeIn: string;
  speed: number;
}

export interface MusicSession {
  id: string;
  mood: string;
  playlistId: string;
  playbackProfile: PlaybackProfile;
  startedAt: string;
}

export interface AppState {
  selectedMood: string;
  customMood: string;
  currentSong: Song | null;
  currentPlaylist: Playlist | null;
  isPlaying: boolean;
  currentTime: number;
  volume: number;
  shuffleEnabled: boolean;
  repeatEnabled: boolean;
  playbackProfile: PlaybackProfile;
  songs: Song[];
  playlists: Playlist[];
  memories: MoodMemory[];
  currentSession: MusicSession | null;
}
