import React from 'react';
import { MoreHorizontal, Play } from 'lucide-react';
import { useAppStore } from '../../store/appStore';
import { Song } from '../../types';

const formatDuration = (d: number): string =>
  `${Math.floor(d / 60)}:${String(d % 60).padStart(2, '0')}`;

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

const SongsTable: React.FC = () => {
  const { songs, currentSong, isPlaying, setCurrentSong, togglePlay } =
    useAppStore();

  const handleRowClick = (song: Song) => {
    if (currentSong?.id === song.id) {
      if (!isPlaying) togglePlay();
    } else {
      setCurrentSong(song);
      if (!isPlaying) togglePlay();
    }
  };

  if (songs.length === 0) {
    return (
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'rgba(255,255,255,0.3)',
          fontSize: 13,
        }}
      >
        No songs yet — import some music!
      </div>
    );
  }

  return (
    <div
      style={{
        flex: 1,
        overflowY: 'auto',
        marginTop: 6,
        // subtle scrollbar
        scrollbarWidth: 'thin',
        scrollbarColor: 'rgba(255,255,255,0.12) transparent',
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '28px 24px 1fr 52px 70px 28px',
          gap: 6,
          padding: '0 6px 6px',
          borderBottom: '1px solid rgba(255,255,255,0.06)',
          marginBottom: 4,
        }}
      >
        {['#', '', 'Title', 'Time', 'Mood', ''].map((h, i) => (
          <span
            key={i}
            style={{
              fontSize: 10,
              fontWeight: 600,
              color: 'rgba(255,255,255,0.3)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              alignSelf: 'center',
            }}
          >
            {h}
          </span>
        ))}
      </div>

      {/* Song rows */}
      {songs.map((song, idx) => {
        const isActive = currentSong?.id === song.id;
        const { bg, color } = moodBadgeColor(song.mood);
        return (
          <div
            key={song.id}
            onClick={() => handleRowClick(song)}
            style={{
              display: 'grid',
              gridTemplateColumns: '28px 24px 1fr 52px 70px 28px',
              gap: 6,
              padding: '5px 6px',
              borderRadius: 7,
              cursor: 'pointer',
              alignItems: 'center',
              background: isActive
                ? 'rgba(168,85,247,0.10)'
                : 'transparent',
              transition: 'background 0.12s',
            }}
            onMouseEnter={(e) => {
              if (!isActive)
                (e.currentTarget as HTMLDivElement).style.background =
                  'rgba(255,255,255,0.05)';
            }}
            onMouseLeave={(e) => {
              if (!isActive)
                (e.currentTarget as HTMLDivElement).style.background =
                  'transparent';
            }}
          >
            {/* # */}
            <span
              style={{
                fontSize: 11,
                color: isActive ? '#a855f7' : 'rgba(255,255,255,0.35)',
                textAlign: 'center',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {isActive && isPlaying ? (
                <Play size={10} fill="#a855f7" color="#a855f7" />
              ) : (
                idx + 1
              )}
            </span>

            {/* Artwork */}
            <div
              style={{
                width: 20,
                height: 20,
                borderRadius: 3,
                overflow: 'hidden',
                flexShrink: 0,
                background: 'rgba(255,255,255,0.08)',
              }}
            >
              {song.artwork ? (
                <img
                  src={song.artwork}
                  alt=""
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <div
                  style={{
                    width: '100%',
                    height: '100%',
                    background:
                      'linear-gradient(135deg,rgba(168,85,247,0.4),rgba(59,130,246,0.4))',
                  }}
                />
              )}
            </div>

            {/* Title + Artist */}
            <div style={{ overflow: 'hidden' }}>
              <div
                style={{
                  fontSize: 12,
                  fontWeight: 500,
                  color: isActive ? '#d8b4fe' : 'rgba(255,255,255,0.88)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {song.title}
              </div>
              <div
                style={{
                  fontSize: 10,
                  color: 'rgba(255,255,255,0.40)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {song.artist}
              </div>
            </div>

            {/* Duration */}
            <span
              style={{
                fontSize: 11,
                color: 'rgba(255,255,255,0.40)',
                textAlign: 'right',
              }}
            >
              {formatDuration(song.duration)}
            </span>

            {/* Mood badge */}
            <span
              style={{
                fontSize: 10,
                fontWeight: 500,
                padding: '2px 6px',
                borderRadius: 10,
                background: bg,
                color,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                textTransform: 'capitalize',
              }}
            >
              {song.mood}
            </span>

            {/* ⋮ menu */}
            <button
              onClick={(e) => {
                e.stopPropagation();
              }}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'rgba(255,255,255,0.30)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: 2,
                borderRadius: 4,
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLButtonElement).style.color =
                  'rgba(255,255,255,0.70)';
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLButtonElement).style.color =
                  'rgba(255,255,255,0.30)';
              }}
            >
              <MoreHorizontal size={13} />
            </button>
          </div>
        );
      })}
    </div>
  );
};

export default SongsTable;
