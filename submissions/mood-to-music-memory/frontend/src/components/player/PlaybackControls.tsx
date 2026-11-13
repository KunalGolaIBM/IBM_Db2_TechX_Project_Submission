import React from 'react';
import { Shuffle, SkipBack, Play, Pause, SkipForward, Repeat } from 'lucide-react';
import { useAppStore } from '../../store/appStore';

export default function PlaybackControls() {
  const {
    isPlaying,
    shuffleEnabled,
    repeatEnabled,
    togglePlay,
    nextSong,
    prevSong,
    toggleShuffle,
    toggleRepeat,
  } = useAppStore();

  const iconStyle = (active?: boolean): React.CSSProperties => ({
    color: active ? '#a855f7' : 'rgba(255,255,255,0.55)',
    cursor: 'pointer',
    padding: '6px',
    borderRadius: '8px',
    background: active ? 'rgba(168,85,247,0.15)' : 'transparent',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.15s ease',
    border: 'none',
    outline: 'none',
  });

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        width: '100%',
      }}
    >
      {/* Shuffle */}
      <button
        onClick={toggleShuffle}
        style={iconStyle(shuffleEnabled)}
        title="Shuffle"
      >
        <Shuffle size={16} />
      </button>

      {/* Skip Back */}
      <button
        onClick={prevSong}
        style={iconStyle()}
        title="Previous"
      >
        <SkipBack size={20} />
      </button>

      {/* Play / Pause */}
      <button
        onClick={togglePlay}
        style={{
          width: '48px',
          height: '48px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
          boxShadow: isPlaying
            ? '0 0 20px rgba(168,85,247,0.6), 0 0 40px rgba(168,85,247,0.3)'
            : '0 4px 16px rgba(168,85,247,0.4)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer',
          border: 'none',
          outline: 'none',
          transition: 'box-shadow 0.2s ease',
          flexShrink: 0,
        }}
        title={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? (
          <Pause size={20} color="#fff" fill="#fff" />
        ) : (
          <Play size={20} color="#fff" fill="#fff" style={{ marginLeft: '2px' }} />
        )}
      </button>

      {/* Skip Forward */}
      <button
        onClick={nextSong}
        style={iconStyle()}
        title="Next"
      >
        <SkipForward size={20} />
      </button>

      {/* Repeat */}
      <button
        onClick={toggleRepeat}
        style={iconStyle(repeatEnabled)}
        title="Repeat"
      >
        <Repeat size={16} />
      </button>
    </div>
  );
}
