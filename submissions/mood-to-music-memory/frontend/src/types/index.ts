export interface Song {
  id: string;
  title: string;
  artist: string;
  duration: number;
  artwork: string;
  mood: string;
  playlistId: string;
  // Extended fields from Db2
  audioUrl?: string;
  album?: string;
}

export interface Playlist {
  id: string;
  name: string;
  mood: string;
  songIds: string[];
  // Extended fields from Db2
  description?: string;
  coverArt?: string;
  songCount?: number;
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
  // Extended fields from Db2
  songTitle?: string;
  artist?: string;
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
  // Db2 connection state
  db2Connected: boolean;
  db2Loading: boolean;
}
