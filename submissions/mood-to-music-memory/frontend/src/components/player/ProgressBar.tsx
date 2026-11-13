import React, { useRef } from 'react';
import { useAppStore } from '../../store/appStore';

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function ProgressBar() {
  const { currentTime, currentSong, setCurrentTime } = useAppStore();
  const trackRef = useRef<HTMLDivElement>(null);

  const duration = currentSong?.duration ?? 0;
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;
  const remaining = duration - currentTime;

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!trackRef.current || duration === 0) return;
    const rect = trackRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, x / rect.width));
    setCurrentTime(Math.floor(ratio * duration));
  };

  return (
    <div style={{ width: '100%', userSelect: 'none' }}>
      {/* Track */}
      <div
        ref={trackRef}
        onClick={handleClick}
        style={{
          width: '100%',
          height: '4px',
          borderRadius: '2px',
          background: 'rgba(255,255,255,0.12)',
          cursor: 'pointer',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 0,
            top: 0,
            height: '100%',
            width: `${progress}%`,
            background: 'linear-gradient(90deg, #7c3aed, #a855f7)',
            borderRadius: '2px',
            transition: 'width 0.5s linear',
          }}
        />
      </div>

      {/* Time labels */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: '6px',
        }}
      >
        <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)' }}>
          {formatTime(currentTime)}
        </span>
        <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)' }}>
          -{formatTime(remaining > 0 ? remaining : 0)}
        </span>
      </div>
    </div>
  );
}
