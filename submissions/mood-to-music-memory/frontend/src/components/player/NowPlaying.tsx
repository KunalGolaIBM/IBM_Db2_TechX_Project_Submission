import React from 'react';
import { Heart, MoreHorizontal } from 'lucide-react';
import { useAppStore } from '../../store/appStore';
import { usePlayback } from '../../hooks/usePlayback';
import WindowHeader from '../layout/WindowHeader';
import Sidebar from '../layout/Sidebar';
import ProgressBar from './ProgressBar';
import PlaybackControls from './PlaybackControls';
import VolumeControl from './VolumeControl';
import { MoodMemory } from '../../types';

const MOOD_COLORS: Record<string, string> = {
  sad: '#60a5fa',
  happy: '#fbbf24',
  romantic: '#f472b6',
  wholesome: '#4ade80',
  ghazal: '#c084fc',
};

export default function NowPlaying() {
  usePlayback();

  const {
    currentSong,
    currentPlaylist,
    selectedMood,
    playbackProfile,
    addMemory,
    setSelectedMood,
  } = useAppStore();

  const moodColor = MOOD_COLORS[selectedMood?.toLowerCase()] ?? '#a855f7';

  const handleSaveMoment = () => {
    if (!currentSong) return;
    const memory: MoodMemory = {
      id: `memory-${Date.now()}`,
      title: currentSong.title,
      date: new Date().toISOString(),
      mood: selectedMood,
      songId: currentSong.id,
      reflection: 'Saved from Now Playing',
      artwork: currentSong.artwork,
      isBookmarked: false,
    };
    addMemory(memory);
  };

  return (
    <div
      className="glass-panel"
      style={{
        background: 'rgba(14,12,38,0.90)',
        backdropFilter: 'blur(24px)',
        display: 'flex',
        flexDirection: 'column',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <WindowHeader title="Mood-to-Music Memory" />

      {/* Body */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar */}
        <Sidebar activeItem="nowplaying" onSelect={() => {}} />

        {/* Main content */}
        <div
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            padding: '16px 20px',
            overflowY: 'auto',
            gap: '10px',
          }}
        >
          {/* Album + song info row */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
            {/* Album artwork */}
            <div
              style={{
                width: '160px',
                height: '160px',
                borderRadius: '16px',
                border: '1px solid rgba(255,255,255,0.15)',
                overflow: 'hidden',
                flexShrink: 0,
                background: currentSong?.artwork
                  ? undefined
                  : 'linear-gradient(135deg, #7c3aed 0%, #a855f7 50%, #ec4899 100%)',
              }}
            >
              {currentSong?.artwork ? (
                <img
                  src={currentSong.artwork}
                  alt={currentSong.title}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).style.display = 'none';
                  }}
                />
              ) : null}
            </div>

            {/* Info */}
            <div style={{ flex: 1, paddingTop: '4px' }}>
              {/* Song title */}
              <div
                style={{
                  fontSize: '18px',
                  fontWeight: 700,
                  color: '#fff',
                  lineHeight: 1.3,
                  marginBottom: '4px',
                }}
              >
                {currentSong?.title ?? 'No song selected'}
              </div>

              {/* Artist */}
              <div
                style={{
                  fontSize: '13px',
                  color: 'rgba(255,255,255,0.6)',
                  marginBottom: '10px',
                }}
              >
                {currentSong?.artist ?? '—'}
              </div>

              {/* Mood badge + playlist */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <span
                  style={{
                    fontSize: '11px',
                    fontWeight: 600,
                    color: moodColor,
                    background: `${moodColor}22`,
                    border: `1px solid ${moodColor}44`,
                    borderRadius: '20px',
                    padding: '2px 10px',
                    textTransform: 'capitalize',
                  }}
                >
                  {selectedMood || 'Unknown'}
                </span>
              </div>

              {/* Playlist info */}
              <div
                style={{
                  fontSize: '11px',
                  color: 'rgba(255,255,255,0.4)',
                  marginBottom: '10px',
                }}
              >
                {currentPlaylist?.name ?? 'No playlist'}
              </div>

              {/* Heart + More buttons */}
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'rgba(255,255,255,0.4)',
                    padding: '4px',
                    borderRadius: '6px',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                  title="Like"
                >
                  <Heart size={16} />
                </button>
                <button
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    color: 'rgba(255,255,255,0.4)',
                    padding: '4px',
                    borderRadius: '6px',
                    display: 'flex',
                    alignItems: 'center',
                  }}
                  title="More options"
                >
                  <MoreHorizontal size={16} />
                </button>
              </div>
            </div>
          </div>

          {/* Playback profile button */}
          <div>
            <button
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: '10px',
                padding: '6px 12px',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.7)', fontWeight: 600 }}>
                {playbackProfile?.name ?? 'Gentle'} profile
              </div>
              <div style={{ fontSize: '10px', color: 'rgba(255,255,255,0.35)', marginTop: '1px' }}>
                Vol {Math.round((playbackProfile?.volume ?? 0.7) * 100)}% · {playbackProfile?.fadeIn ?? '2s'} fade
              </div>
            </button>
          </div>

          {/* Progress bar */}
          <ProgressBar />

          {/* Playback controls */}
          <PlaybackControls />

          {/* Volume control */}
          <VolumeControl />

          {/* Spacer */}
          <div style={{ flex: 1 }} />

          {/* Bottom buttons */}
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              onClick={() => setSelectedMood('')}
              style={{
                flex: 1,
                padding: '9px 0',
                borderRadius: '10px',
                border: '1px solid rgba(255,255,255,0.18)',
                background: 'transparent',
                color: 'rgba(255,255,255,0.7)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Change Mood
            </button>
            <button
              onClick={handleSaveMoment}
              style={{
                flex: 1,
                padding: '9px 0',
                borderRadius: '10px',
                border: 'none',
                background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
                color: '#fff',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 4px 14px rgba(168,85,247,0.35)',
              }}
            >
              Save this moment
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
