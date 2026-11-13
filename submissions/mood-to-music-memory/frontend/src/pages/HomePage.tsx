import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Cloud, Sun, Heart, Leaf, Music2, Play, Clock, Flame, Loader2 } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import CustomMoodInput from '../components/mood/CustomMoodInput';
import { api } from '../api/client';

const MOODS = [
  { id: 'sad', label: 'Sad', desc: 'For when things feel heavy', icon: <Cloud size={22} />, color: '#60a5fa', glow: 'rgba(96,165,250,0.35)' },
  { id: 'happy', label: 'Happy', desc: 'Uplift your energy', icon: <Sun size={22} />, color: '#fbbf24', glow: 'rgba(251,191,36,0.35)' },
  { id: 'romantic', label: 'Romantic', desc: 'For the heartfelt moments', icon: <Heart size={22} />, color: '#f472b6', glow: 'rgba(244,114,182,0.35)' },
  { id: 'wholesome', label: 'Wholesome', desc: 'Calm, cozy and positive', icon: <Leaf size={22} />, color: '#4ade80', glow: 'rgba(74,222,128,0.35)' },
  { id: 'ghazal', label: 'Ghazal', desc: 'Soulful, poetic and deep', icon: <Music2 size={22} />, color: '#c084fc', glow: 'rgba(192,132,252,0.35)' },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.07 } },
};
const item = {
  hidden: { opacity: 0, y: 24 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35 } },
};

const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const {
    selectedMood, customMood, playlists,
    setSelectedMood, setCustomMood, startSession, songs,
  } = useAppStore();
  const [aiLoading, setAiLoading] = useState(false);

  const canStart = !!(selectedMood || customMood.trim());

  const handleStart = async () => {
    if (!canStart) return;
    let moodToUse = selectedMood || 'happy';

    // If user typed a custom mood and no button selected, detect via AI
    if (!selectedMood && customMood.trim()) {
      setAiLoading(true);
      try {
        const result = await api.detectMood(customMood.trim());
        moodToUse = result.mood_code;
        setSelectedMood(moodToUse);
      } catch {
        moodToUse = 'happy';
      } finally {
        setAiLoading(false);
      }
    }

    const playlist = playlists.find(p => p.mood === moodToUse) ?? playlists[0];
    startSession(moodToUse, playlist);
    navigate('/now-playing');
  };

  // Recently played — last 3 songs
  const recent = songs.slice(0, 3);

  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={container}
      style={{ paddingBottom: 28 }}
    >
      {/* ── Welcome ── */}
      <motion.div variants={item} style={{ marginBottom: 32 }}>
        <div style={{ fontSize: 13, color: '#c084fc', fontWeight: 500, marginBottom: 6 }}>
          Good evening, Tushar! 👋
        </div>
        <h1 style={{ fontSize: 28, fontWeight: 800, color: '#fff', margin: 0, lineHeight: 1.2 }}>
          How are you feeling today?
        </h1>
        <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.45)', marginTop: 8, maxWidth: 480 }}>
          Choose a mood or describe it in your own words, and I'll play the right music for you.
        </p>
      </motion.div>

      {/* ── Mood Cards ── */}
      <motion.div
        variants={item}
        style={{ display: 'flex', gap: 14, marginBottom: 24, flexWrap: 'wrap' }}
      >
        {MOODS.map(m => {
          const isSelected = selectedMood === m.id;
          return (
            <motion.button
              key={m.id}
              whileHover={{ scale: 1.03, y: -2 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => setSelectedMood(isSelected ? '' : m.id)}
              style={{
                flex: '1 1 140px',
                minWidth: 120,
                maxWidth: 200,
                padding: '20px 14px',
                borderRadius: 16,
                border: isSelected ? `1.5px solid ${m.color}` : '1px solid rgba(255,255,255,0.09)',
                background: isSelected ? `${m.color}14` : 'rgba(255,255,255,0.04)',
                boxShadow: isSelected ? `0 0 24px ${m.glow}` : 'none',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 10,
                backdropFilter: 'blur(12px)',
                transition: 'border 0.2s, box-shadow 0.2s, background 0.2s',
              }}
            >
              {/* Icon circle */}
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: '50%',
                  background: `${m.color}20`,
                  border: `1.5px solid ${m.color}44`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: m.color,
                }}
              >
                {m.icon}
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#fff', marginBottom: 3 }}>{m.label}</div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', lineHeight: 1.4 }}>{m.desc}</div>
              </div>
              {isSelected && (
                <div
                  style={{
                    width: 8, height: 8, borderRadius: '50%',
                    background: m.color, boxShadow: `0 0 8px ${m.glow}`,
                    marginTop: 2,
                  }}
                />
              )}
            </motion.button>
          );
        })}
      </motion.div>

      {/* ── Custom mood + Start ── */}
      <motion.div variants={item} style={{ maxWidth: 560, marginBottom: 40 }}>
        <CustomMoodInput value={customMood} onChange={setCustomMood} />
        <motion.button
          whileHover={canStart ? { scale: 1.02 } : {}}
          whileTap={canStart ? { scale: 0.98 } : {}}
          onClick={handleStart}
          disabled={!canStart}
          style={{
            marginTop: 14,
            width: '100%',
            padding: '13px 0',
            borderRadius: 12,
            border: 'none',
            background: canStart
              ? 'linear-gradient(135deg, #6d28d9 0%, #a855f7 100%)'
              : 'rgba(255,255,255,0.07)',
            color: canStart ? '#fff' : 'rgba(255,255,255,0.28)',
            fontSize: 14,
            fontWeight: 700,
            cursor: canStart ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            boxShadow: canStart ? '0 6px 24px rgba(109,40,217,0.45)' : 'none',
            transition: 'all 0.2s',
            letterSpacing: '0.02em',
          }}
        >
          <Play size={16} style={{ fill: canStart ? '#fff' : 'rgba(255,255,255,0.28)' }} />
          {aiLoading ? 'Detecting mood…' : 'Start My Session'}
          {aiLoading && <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />}
        </motion.button>
      </motion.div>

      {/* ── Recent listens ── */}
      <motion.div variants={item}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <Clock size={15} style={{ color: 'rgba(255,255,255,0.35)' }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: 'rgba(255,255,255,0.65)' }}>Recently Played</span>
        </div>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
          {recent.map(song => (
            <motion.div
              key={song.id}
              whileHover={{ scale: 1.02, y: -2 }}
              style={{
                flex: '1 1 180px',
                maxWidth: 240,
                padding: '14px',
                borderRadius: 14,
                background: 'rgba(255,255,255,0.04)',
                border: '1px solid rgba(255,255,255,0.08)',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                cursor: 'pointer',
                backdropFilter: 'blur(12px)',
              }}
              onClick={() => {
                useAppStore.getState().setCurrentSong(song);
                navigate('/now-playing');
              }}
            >
              <div
                style={{
                  width: 44, height: 44, borderRadius: 10, flexShrink: 0,
                  overflow: 'hidden', background: 'linear-gradient(135deg,#4c1d95,#7c3aed)',
                }}
              >
                {song.artwork && (
                  <img src={song.artwork} alt={song.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />
                )}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {song.title}
                </div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', marginTop: 2 }}>
                  {song.artist}
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* ── Quick stats ── */}
      <motion.div variants={item} style={{ marginTop: 32, display: 'flex', gap: 14 }}>
        {[
          { icon: <Flame size={18} />, label: 'Listening Streak', value: '7 days', color: '#f97316' },
          { icon: <Music2 size={18} />, label: 'Songs Played Today', value: '12', color: '#a855f7' },
          { icon: <Heart size={18} />, label: 'Saved Memories', value: '5', color: '#f472b6' },
        ].map((stat, i) => (
          <div
            key={i}
            style={{
              flex: 1,
              padding: '16px 18px',
              borderRadius: 14,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.07)',
              display: 'flex',
              alignItems: 'center',
              gap: 14,
              backdropFilter: 'blur(12px)',
            }}
          >
            <div
              style={{
                width: 38, height: 38, borderRadius: 10, flexShrink: 0,
                background: `${stat.color}18`,
                border: `1px solid ${stat.color}30`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: stat.color,
              }}
            >
              {stat.icon}
            </div>
            <div>
              <div style={{ fontSize: 18, fontWeight: 800, color: '#fff', lineHeight: 1 }}>{stat.value}</div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.40)', marginTop: 3 }}>{stat.label}</div>
            </div>
          </div>
        ))}
      </motion.div>
    </motion.div>
  );
};

export default HomePage;

