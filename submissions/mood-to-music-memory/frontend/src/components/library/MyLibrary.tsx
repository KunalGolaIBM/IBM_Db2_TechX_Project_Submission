import React, { useState } from 'react';
import { FolderOpen, Play } from 'lucide-react';
import WindowHeader from '../layout/WindowHeader';
import { useAppStore } from '../../store/appStore';
import { Song, Playlist } from '../../types';
import ImportMusic from './ImportMusic';
import SongsTable from './SongsTable';

type Tab = 'songs' | 'playlists';

const moodBadgeColor = (mood: string): { bg: string; color: string } => {
  switch (mood.toLowerCase()) {
    case 'sad':
      return { bg: 'rgba(59,130,246,0.18)', color: '#93c5fd' };
    case 'happy':
      return { bg: 'rgba(234,179,8,0.18)', color: '#fde047' };
    case 'romantic':
      return { bg: 'rgba(236,72,153,0.18)', color: '#f9a8d4' };
    case 'wholesome':
      return { bg: 'rgba(34,197,94,0.18)', color: '#86efac' };
    case 'ghazal':
    case 'calm':
      return { bg: 'rgba(168,85,247,0.18)', color: '#d8b4fe' };
    default:
      return { bg: 'rgba(107,114,128,0.18)', color: '#9ca3af' };
  }
};

const MyLibrary: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('songs');
  const { addSong, playlists, songs } = useAppStore();

  const handleImport = (fileNames: string[]) => {
    fileNames.forEach((name, i) => {
      const fakeSong: Song = {
        id: `imported-${Date.now()}-${i}`,
        title: name.replace(/\.[^.]+$/, ''), // strip extension
        artist: 'Unknown Artist',
        duration: 200 + Math.floor(Math.random() * 180),
        artwork: '',
        mood: 'happy',
        playlistId: 'pl3',
      };
      addSong(fakeSong);
    });
  };

  return (
    <div
      className="glass-panel"
      style={{
        background: 'rgba(16,13,42,0.88)',
        backdropFilter: 'blur(20px)',
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Panel header */}
      <WindowHeader title="My Library" icon={<FolderOpen size={14} />} />

      {/* Body */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          overflow: 'hidden',
          padding: '12px 16px',
        }}
      >
        {/* Tabs row + import button */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: 10,
            gap: 8,
          }}
        >
          {/* Tabs */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 4,
              background: 'rgba(255,255,255,0.05)',
              borderRadius: 10,
              padding: 3,
            }}
          >
            {(['songs', 'playlists'] as Tab[]).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                style={{
                  padding: '4px 12px',
                  borderRadius: 7,
                  border: 'none',
                  background:
                    activeTab === tab
                      ? 'rgba(168,85,247,0.75)'
                      : 'transparent',
                  color:
                    activeTab === tab
                      ? '#fff'
                      : 'rgba(255,255,255,0.45)',
                  fontSize: 12,
                  fontWeight: activeTab === tab ? 600 : 400,
                  cursor: 'pointer',
                  transition: 'background 0.15s, color 0.15s',
                  whiteSpace: 'nowrap',
                }}
              >
                {tab === 'songs' ? 'My Songs' : 'Playlists'}
              </button>
            ))}
          </div>

          {/* Import button */}
          <ImportMusic onImport={handleImport} />
        </div>

        {/* Content area */}
        {activeTab === 'songs' ? (
          <SongsTable />
        ) : (
          <PlaylistsView playlists={playlists} songs={songs} />
        )}
      </div>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/*  Playlists sub-view                                                   */
/* ------------------------------------------------------------------ */
interface PlaylistsViewProps {
  playlists: Playlist[];
  songs: Song[];
}

const PlaylistsView: React.FC<PlaylistsViewProps> = ({ playlists, songs }) => {
  const [hovered, setHovered] = useState<string | null>(null);
  const { startSession } = useAppStore();

  const handlePlay = (pl: Playlist) => {
    startSession(pl.mood, pl);
  };

  return (
    <div
      style={{
        flex: 1,
        overflowY: 'auto',
        scrollbarWidth: 'thin',
        scrollbarColor: 'rgba(255,255,255,0.12) transparent',
      }}
    >
      {playlists.map((pl) => {
        const count = pl.songIds.length;
        const { bg, color } = moodBadgeColor(pl.mood);
        const isHov = hovered === pl.id;
        return (
          <div
            key={pl.id}
            onMouseEnter={() => setHovered(pl.id)}
            onMouseLeave={() => setHovered(null)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 8px',
              borderRadius: 8,
              background: isHov ? 'rgba(255,255,255,0.05)' : 'transparent',
              cursor: 'pointer',
              transition: 'background 0.12s',
              marginBottom: 2,
            }}
          >
            {/* Play icon (shows on hover) */}
            <button
              onClick={() => handlePlay(pl)}
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                border: 'none',
                background: isHov
                  ? 'rgba(168,85,247,0.70)'
                  : 'rgba(255,255,255,0.07)',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                flexShrink: 0,
                transition: 'background 0.15s',
              }}
            >
              <Play size={11} fill="#fff" />
            </button>

            {/* Name + count */}
            <div style={{ flex: 1, overflow: 'hidden' }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: 'rgba(255,255,255,0.88)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {pl.name}
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: 'rgba(255,255,255,0.35)',
                  marginTop: 1,
                }}
              >
                {count} song{count !== 1 ? 's' : ''}
              </div>
            </div>

            {/* Mood badge */}
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: '2px 7px',
                borderRadius: 10,
                background: bg,
                color,
                textTransform: 'capitalize',
                whiteSpace: 'nowrap',
              }}
            >
              {pl.mood}
            </span>
          </div>
        );
      })}
    </div>
  );
};

export default MyLibrary;
