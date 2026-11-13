import React from 'react';
import {
  SkipBack, Play, Pause, SkipForward,
  Shuffle, Repeat, Volume2, Maximize2, Heart,
} from 'lucide-react';
import { useAppStore } from '../../store/appStore';

interface BottomPlayerProps {
  onNavigatePlayer: () => void;
}

function fmt(s: number): string {
  const sec = Math.floor(s);
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
}

const BottomPlayer: React.FC<BottomPlayerProps> = ({ onNavigatePlayer }) => {
  const {
    currentSong, isPlaying, currentTime, volume,
    shuffleEnabled, repeatEnabled,
    togglePlay, nextSong, prevSong, toggleShuffle, toggleRepeat, setVolume, setCurrentTime,
  } = useAppStore();

  const duration = currentSong?.duration ?? 1;
  const progress = Math.min((currentTime / duration) * 100, 100);

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    setCurrentTime(Math.floor(pct * duration));
  };

  return (
    <div
      style={{
        height: 76,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        padding: '0 24px',
        background: 'rgba(8,6,22,0.92)',
        borderTop: '1px solid rgba(255,255,255,0.08)',
        backdropFilter: 'blur(28px)',
        gap: 0,
        position: 'relative',
      }}
    >
      {/* Progress bar at top of player */}
      <div
        onClick={handleSeek}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: 3,
          background: 'rgba(255,255,255,0.08)',
          cursor: 'pointer',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${progress}%`,
            background: 'linear-gradient(90deg, #7c3aed, #a855f7)',
            transition: 'width 1s linear',
          }}
        />
      </div>

      {/* LEFT — song info */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: '0 0 260px', minWidth: 0 }}>
        {/* Artwork */}
        <div
          style={{
            width: 46,
            height: 46,
            borderRadius: 10,
            overflow: 'hidden',
            flexShrink: 0,
            background: 'linear-gradient(135deg, #4c1d95, #7c3aed)',
            border: '1px solid rgba(255,255,255,0.10)',
          }}
        >
          {currentSong?.artwork && (
            <img
              src={currentSong.artwork}
              alt={currentSong.title}
              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
            />
          )}
        </div>

        {/* Title / artist */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 13,
              fontWeight: 600,
              color: '#fff',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {currentSong?.title ?? 'No song selected'}
          </div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {currentSong?.artist ?? '—'}
          </div>
        </div>

        {/* Heart */}
        <button
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'rgba(255,255,255,0.35)', padding: 4, flexShrink: 0,
            display: 'flex', alignItems: 'center',
          }}
          title="Like"
        >
          <Heart size={15} />
        </button>
      </div>

      {/* CENTER — controls */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          <button
            onClick={toggleShuffle}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: shuffleEnabled ? '#a855f7' : 'rgba(255,255,255,0.40)',
              display: 'flex', padding: 4,
            }}
            title="Shuffle"
          >
            <Shuffle size={15} />
          </button>
          <button
            onClick={prevSong}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.70)', display: 'flex', padding: 4 }}
            title="Previous"
          >
            <SkipBack size={18} />
          </button>
          <button
            onClick={togglePlay}
            style={{
              width: 40, height: 40, borderRadius: '50%',
              background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
              border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 18px rgba(168,85,247,0.50)',
              flexShrink: 0,
            }}
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isPlaying
              ? <Pause size={18} color="#fff" />
              : <Play size={18} color="#fff" style={{ marginLeft: 2 }} />}
          </button>
          <button
            onClick={nextSong}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.70)', display: 'flex', padding: 4 }}
            title="Next"
          >
            <SkipForward size={18} />
          </button>
          <button
            onClick={toggleRepeat}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: repeatEnabled ? '#a855f7' : 'rgba(255,255,255,0.40)',
              display: 'flex', padding: 4,
            }}
            title="Repeat"
          >
            <Repeat size={15} />
          </button>
        </div>

        {/* Time */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 10, color: 'rgba(255,255,255,0.30)' }}>
          <span>{fmt(currentTime)}</span>
          <span>/</span>
          <span>{fmt(duration)}</span>
        </div>
      </div>

      {/* RIGHT — volume + expand */}
      <div style={{ flex: '0 0 260px', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 12 }}>
        <Volume2 size={15} style={{ color: 'rgba(255,255,255,0.40)', flexShrink: 0 }} />
        <input
          type="range"
          min={0} max={1} step={0.01}
          value={volume}
          onChange={e => setVolume(parseFloat(e.target.value))}
          style={{ width: 90, accentColor: '#a855f7', cursor: 'pointer' }}
        />
        <button
          onClick={onNavigatePlayer}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'rgba(255,255,255,0.40)', padding: 4, display: 'flex', alignItems: 'center',
          }}
          title="Expand player"
        >
          <Maximize2 size={15} />
        </button>
      </div>
    </div>
  );
};

export default BottomPlayer;

