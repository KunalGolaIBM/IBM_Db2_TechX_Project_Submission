import { Playlist } from '../types';

export const mockPlaylists: Playlist[] = [
  { id: 'pl1', name: 'Love Notes', mood: 'romantic', songIds: ['1', '3', '5', '9', '10'] },
  { id: 'pl2', name: 'Sad Comfort Playlist', mood: 'sad', songIds: ['2', '6'] },
  { id: 'pl3', name: 'Feel Good Vibes', mood: 'happy', songIds: ['4'] },
  { id: 'pl4', name: 'Calm Waters', mood: 'calm', songIds: ['7'] },
  { id: 'pl5', name: 'Power Hour', mood: 'energetic', songIds: ['8'] },
];
