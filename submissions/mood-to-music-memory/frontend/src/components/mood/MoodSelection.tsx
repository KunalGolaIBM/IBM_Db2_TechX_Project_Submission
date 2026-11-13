import React from 'react';
import { motion } from 'framer-motion';
import { Cloud, Sun, Heart, Leaf, Music2, Play } from 'lucide-react';
import { useAppStore } from '../../store/appStore';
import WindowHeader from '../layout/WindowHeader';
import MoodCard from './MoodCard';
import CustomMoodInput from './CustomMoodInput';

const MOODS = [
  {
    mood: 'sad',
    label: 'Sad',
    description: 'Melancholic & reflective',
    icon: <Cloud size={20} />,
    color: '#60a5fa',
    glowColor: 'rgba(96,165,250,0.4)',
  },
  {
    mood: 'happy',
    label: 'Happy',
    description: 'Upbeat & joyful',
    icon: <Sun size={20} />,
    color: '#fbbf24',
    glowColor: 'rgba(251,191,36,0.4)',
  },
  {
    mood: 'romantic',
    label: 'Romantic',
    description: 'Warm & intimate',
    icon: <Heart size={20} />,
    color: '#f472b6',
    glowColor: 'rgba(244,114,182,0.4)',
  },
  {
    mood: 'wholesome',
    label: 'Wholesome',
    description: 'Cozy & heartwarming',
    icon: <Leaf size={20} />,
    color: '#4ade80',
    glowColor: 'rgba(74,222,128,0.4)',
  },
  {
    mood: 'ghazal',
    label: 'Ghazal',
    description: 'Poetic & soulful',
    icon: <Music2 size={20} />,
    color: '#c084fc',
    glowColor: 'rgba(192,132,252,0.4)',
  },
];

const MoodSelection: React.FC = () => {
  const {
    selectedMood,
    customMood,
    playlists,
    startSession,
    setSelectedMood,
    setCustomMood,
  } = useAppStore();

  const canStart = !!(selectedMood || customMood.trim());

  const handleStart = () => {
    if (!canStart) return;
    const matchingPlaylist =
      playlists.find(
        (p) =>
          p.mood?.toLowerCase() === (selectedMood || 'custom').toLowerCase()
      ) ?? playlists[0];
    startSession(selectedMood || 'custom', matchingPlaylist);
  };

  return (
    <div
      className="glass-panel"
      style={{
        background: 'rgba(18,15,40,0.88)',
        backdropFilter: 'blur(22px)',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Window chrome */}
      <WindowHeader title="Mood-to-Music Memory" />

      {/* Animated inner content */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          padding: '18px 20px 16px',
          gap: 16,
          overflow: 'hidden',
        }}
      >
        {/* Welcome section */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span
            style={{
              color: '#c084fc',
              fontSize: '0.82rem',
              fontWeight: 500,
            }}
          >
            Good to see you again, Tushar! 👋
          </span>
          <h2
            style={{
              color: '#fff',
              fontSize: '1.35rem',
              fontWeight: 700,
              margin: 0,
              lineHeight: 1.2,
            }}
          >
            How are you feeling today?
          </h2>
          <span
            style={{
              color: 'rgba(255,255,255,0.5)',
              fontSize: '0.72rem',
              marginTop: 2,
            }}
          >
            Pick a mood or describe how you feel — we'll find the perfect soundtrack.
          </span>
        </div>

        {/* Mood cards row */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'row',
            justifyContent: 'space-between',
            gap: 8,
          }}
        >
          {MOODS.map((m) => (
            <MoodCard
              key={m.mood}
              mood={m.mood}
              label={m.label}
              description={m.description}
              icon={m.icon}
              color={m.color}
              glowColor={m.glowColor}
              isSelected={selectedMood === m.mood}
              onClick={() =>
                setSelectedMood(selectedMood === m.mood ? null : m.mood)
              }
            />
          ))}
        </div>

        {/* Custom mood input */}
        <CustomMoodInput value={customMood} onChange={setCustomMood} />

        {/* Start button */}
        <button
          onClick={handleStart}
          disabled={!canStart}
          style={{
            width: '100%',
            padding: '11px 0',
            borderRadius: '0.75rem',
            border: 'none',
            background: canStart
              ? 'linear-gradient(135deg, #7c3aed 0%, #a855f7 100%)'
              : 'rgba(255,255,255,0.08)',
            color: canStart ? '#fff' : 'rgba(255,255,255,0.3)',
            fontSize: '0.9rem',
            fontWeight: 600,
            cursor: canStart ? 'pointer' : 'not-allowed',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            transition: 'background 0.2s, color 0.2s',
            boxShadow: canStart
              ? '0 4px 20px rgba(124,58,237,0.4)'
              : 'none',
            letterSpacing: '0.02em',
          }}
        >
          <Play size={15} style={{ fill: canStart ? '#fff' : 'rgba(255,255,255,0.3)' }} />
          Start my session
        </button>
      </motion.div>
    </div>
  );
};

export default MoodSelection;
