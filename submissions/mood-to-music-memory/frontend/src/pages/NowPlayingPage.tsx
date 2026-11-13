import React, { useRef } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Heart, MoreHorizontal, Shuffle, SkipBack, Play, Pause, SkipForward,
  Repeat, Volume2, Bookmark, ChevronLeft,
} from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { usePlayback } from '../hooks/usePlayback';
import { MoodMemory } from '../types';

const MOOD_COLORS: Record<string, string> = {
  sad: '#60a5fa', happy: '#fbbf24', romantic: '#f472b6',
  wholesome: '#4ade80', ghazal: '#c084fc',
};

function fmt(s: number) {
  const sec = Math.floor(s);
  const m = Math.floor(sec / 60);
  const r = sec % 60;
  return `${m}:${String(r).padStart(2, '0')}`;
}

const NowPlayingPage: React.FC = () => {
  usePlayback();
  const navigate = useNavigate();
  const progressRef = useRef<HTMLDivElement>(null);

  const {
    currentSong, currentPlaylist, selectedMood, isPlaying, currentTime, volume,
    shuffleEnabled, repeatEnabled, playbackProfile,
    togglePlay, nextSong, prevSong, toggleShuffle, toggleRepeat,
    setVolume, setCurrentTime, addMemory,
  } = useAppStore();

  const duration = currentSong?.duration ?? 1;
  const progress = Math.min((currentTime / duration) * 100, 100);
  const moodColor = MOOD_COLORS[selectedMood?.toLowerCase?.()] ?? '#a855f7';

  const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setCurrentTime(Math.floor(((e.clientX - rect.left) / rect.width) * duration));
  };

  const handleSave = () => {
    if (!currentSong) return;
    const mem: MoodMemory = {
      id: `mem-${Date.now()}`,
      title: currentSong.title,
      date: new Date().toISOString(),
      mood: selectedMood || 'happy',
      songId: currentSong.id,
      reflection: 'Saved from Now Playing.',
      artwork: currentSong.artwork,
      isBookmarked: false,
    };
    addMemory(mem);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      style={{ paddingBottom: 28, maxWidth: 760, margin: '0 auto' }}
    >
      {/* Back */}
      <button
        onClick={() => navigate(-1)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: 'none', border: 'none', cursor: 'pointer',
          color: 'rgba(255,255,255,0.45)', fontSize: 13, marginBottom: 24, padding: 0,
        }}
      >
        <ChevronLeft size={16} /> Back
      </button>

      <div style={{ display: 'flex', gap: 48, alignItems: 'flex-start' }}>
        {/* LEFT — artwork */}
        <div style={{ flexShrink: 0 }}>
          <motion.div
            animate={{ boxShadow: isPlaying ? '0 0 60px rgba(168,85,247,0.4)' : '0 0 20px rgba(0,0,0,0.5)' }}
            transition={{ duration: 0.6 }}
            style={{
              width: 280,
              height: 280,
              borderRadius: 20,
              overflow: 'hidden',
              border: '1px solid rgba(255,255,255,0.12)',
              background: 'linear-gradient(135deg, #4c1d95, #7c3aed)',
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
          </motion.div>
        </div>

        {/* RIGHT — info + controls */}
        <div style={{ flex: 1, minWidth: 0, paddingTop: 8 }}>
          {/* Song info */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <h2 style={{ fontSize: 24, fontWeight: 800, color: '#fff', margin: 0, lineHeight: 1.2 }}>
                  {currentSong?.title ?? 'No song selected'}
                </h2>
                <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.55)', marginTop: 6 }}>
                  {currentSong?.artist ?? '—'}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.40)', padding: 6 }}>
                  <Heart size={18} />
                </button>
                <button style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.40)', padding: 6 }}>
                  <MoreHorizontal size={18} />
                </button>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
              {selectedMood && (
                <span style={{
                  fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 20,
                  color: moodColor, background: `${moodColor}20`, border: `1px solid ${moodColor}40`,
                  textTransform: 'capitalize',
                }}>
                  {selectedMood}
                </span>
              )}
              {currentPlaylist && (
                <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>
                  {currentPlaylist.name}
                </span>
              )}
            </div>
          </div>

          {/* Playback profile */}
          <div
            style={{
              padding: '8px 14px',
              borderRadius: 10,
              background: 'rgba(255,255,255,0.05)',
              border: '1px solid rgba(255,255,255,0.08)',
              marginBottom: 24,
              display: 'inline-block',
            }}
          >
            <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.75)' }}>
              {playbackProfile.name} Profile
            </div>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', marginTop: 2 }}>
              Vol {Math.round(playbackProfile.volume * 100)}% · {playbackProfile.fadeIn} fade · {playbackProfile.speed}x speed
            </div>
          </div>

          {/* Progress */}
          <div style={{ marginBottom: 20 }}>
            <div
              ref={progressRef}
              onClick={handleProgressClick}
              style={{
                height: 5,
                borderRadius: 3,
                background: 'rgba(255,255,255,0.12)',
                cursor: 'pointer',
                position: 'relative',
                marginBottom: 8,
              }}
            >
              <div
                style={{
                  height: '100%',
                  width: `${progress}%`,
                  borderRadius: 3,
                  background: 'linear-gradient(90deg, #7c3aed, #a855f7)',
                  transition: 'width 1s linear',
                  position: 'relative',
                }}
              >
                <div style={{
                  position: 'absolute', right: -6, top: '50%',
                  transform: 'translateY(-50%)',
                  width: 12, height: 12, borderRadius: '50%',
                  background: '#fff', boxShadow: '0 0 6px rgba(168,85,247,0.8)',
                }} />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>
              <span>{fmt(currentTime)}</span>
              <span>-{fmt(Math.max(0, duration - currentTime))}</span>
            </div>
          </div>

          {/* Controls */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 20, marginBottom: 24 }}>
            <button
              onClick={toggleShuffle}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: shuffleEnabled ? '#a855f7' : 'rgba(255,255,255,0.40)', padding: 6 }}
            >
              <Shuffle size={18} />
            </button>
            <button onClick={prevSong} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.75)', padding: 6 }}>
              <SkipBack size={22} />
            </button>
            <motion.button
              whileHover={{ scale: 1.06 }}
              whileTap={{ scale: 0.94 }}
              onClick={togglePlay}
              style={{
                width: 56, height: 56, borderRadius: '50%',
                background: 'linear-gradient(135deg, #6d28d9, #a855f7)',
                border: 'none', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                boxShadow: '0 0 24px rgba(168,85,247,0.55)',
              }}
            >
              {isPlaying ? <Pause size={24} color="#fff" /> : <Play size={24} color="#fff" style={{ marginLeft: 3 }} />}
            </motion.button>
            <button onClick={nextSong} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.75)', padding: 6 }}>
              <SkipForward size={22} />
            </button>
            <button
              onClick={toggleRepeat}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: repeatEnabled ? '#a855f7' : 'rgba(255,255,255,0.40)', padding: 6 }}
            >
              <Repeat size={18} />
            </button>
          </div>

          {/* Volume */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 28 }}>
            <Volume2 size={16} style={{ color: 'rgba(255,255,255,0.40)', flexShrink: 0 }} />
            <input
              type="range" min={0} max={1} step={0.01} value={volume}
              onChange={e => setVolume(parseFloat(e.target.value))}
              style={{ flex: 1, accentColor: '#a855f7', cursor: 'pointer' }}
            />
            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.40)', width: 32, textAlign: 'right' }}>
              {Math.round(volume * 100)}%
            </span>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={() => navigate('/home')}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 10,
                border: '1px solid rgba(255,255,255,0.15)',
                background: 'transparent', color: 'rgba(255,255,255,0.70)',
                fontSize: 13, fontWeight: 600, cursor: 'pointer',
              }}
            >
              Change Mood
            </button>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={handleSave}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 10,
                border: 'none', background: 'linear-gradient(135deg, #6d28d9, #a855f7)',
                color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                boxShadow: '0 4px 16px rgba(109,40,217,0.4)',
              }}
            >
              <Bookmark size={14} />
              Save This Moment
            </motion.button>
          </div>
        </div>
      </div>

      {/* Playlist queue */}
      {currentPlaylist && (
        <div style={{ marginTop: 48 }}>
          <h3 style={{ fontSize: 15, fontWeight: 700, color: 'rgba(255,255,255,0.75)', marginBottom: 14 }}>
            Up Next — {currentPlaylist.name}
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {useAppStore.getState().songs
              .filter(s => currentPlaylist.songIds.includes(s.id))
              .map(song => {
                const isActive = song.id === currentSong?.id;
                return (
                  <div
                    key={song.id}
                    onClick={() => { useAppStore.getState().setCurrentSong(song); if (!isPlaying) useAppStore.getState().togglePlay(); }}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 14,
                      padding: '10px 14px', borderRadius: 10,
                      background: isActive ? 'rgba(168,85,247,0.12)' : 'transparent',
                      border: isActive ? '1px solid rgba(168,85,247,0.25)' : '1px solid transparent',
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ width: 36, height: 36, borderRadius: 8, overflow: 'hidden', background: 'linear-gradient(135deg,#4c1d95,#7c3aed)', flexShrink: 0 }}>
                      {song.artwork && (
                        <img src={song.artwork} alt={song.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
                      )}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: isActive ? 700 : 400, color: isActive ? '#c084fc' : '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{song.title}</div>
                      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.40)' }}>{song.artist}</div>
                    </div>
                    <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', flexShrink: 0 }}>
                      {fmt(song.duration)}
                    </span>
                  </div>
                );
              })}
          </div>
        </div>
      )}
    </motion.div>
  );
};

export default NowPlayingPage;

