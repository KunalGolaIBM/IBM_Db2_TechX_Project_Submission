import React from 'react';
import { motion } from 'framer-motion';
import { Clock, Music2, Heart, Bookmark, TrendingUp, BarChart2 } from 'lucide-react';
import { useAppStore } from '../store/appStore';

const MOOD_COLORS: Record<string, string> = {
  sad: '#60a5fa', happy: '#fbbf24', romantic: '#f472b6',
  wholesome: '#4ade80', ghazal: '#c084fc', calm: '#c084fc',
  energetic: '#fb923c',
};

const container = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };
const item = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

// Mock analytics data
const MOCK_HISTORY = [
  { date: 'Nov 13', minutes: 72 },
  { date: 'Nov 12', minutes: 45 },
  { date: 'Nov 11', minutes: 90 },
  { date: 'Nov 10', minutes: 30 },
  { date: 'Nov 09', minutes: 110 },
  { date: 'Nov 08', minutes: 55 },
  { date: 'Nov 07', minutes: 80 },
];

const MOCK_MOOD_DIST = [
  { mood: 'Romantic', pct: 38 },
  { mood: 'Sad',      pct: 24 },
  { mood: 'Happy',    pct: 18 },
  { mood: 'Ghazal',   pct: 12 },
  { mood: 'Wholesome',pct: 8  },
];

const AnalyticsPage: React.FC = () => {
  const { songs, memories, selectedMood } = useAppStore();

  const totalMinutes = MOCK_HISTORY.reduce((s, d) => s + d.minutes, 0);
  const maxBar = Math.max(...MOCK_HISTORY.map(d => d.minutes));

  const stats = [
    { label: 'Total Listening Time', value: `${Math.floor(totalMinutes / 60)}h ${totalMinutes % 60}m`, icon: <Clock size={18} />, color: '#a855f7' },
    { label: 'Most Listened Mood',   value: 'Romantic',       icon: <Heart size={18} />,   color: '#f472b6' },
    { label: 'Songs Played',         value: `${songs.length * 3}`,      icon: <Music2 size={18} />,  color: '#60a5fa' },
    { label: 'Saved Memories',       value: `${memories.length}`,      icon: <Bookmark size={18} />, color: '#fbbf24' },
  ];

  const topSongs = songs.slice(0, 5).map((s, i) => ({
    ...s,
    plays: 32 - i * 5,
  }));

  return (
    <motion.div
      initial="hidden" animate="show" variants={container}
      style={{ paddingBottom: 28 }}
    >
      {/* Stats cards */}
      <motion.div variants={item} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 16, marginBottom: 32 }}>
        {stats.map((s, i) => (
          <div
            key={i}
            style={{
              padding: '20px 20px',
              borderRadius: 16,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              backdropFilter: 'blur(12px)',
              display: 'flex',
              alignItems: 'center',
              gap: 16,
            }}
          >
            <div
              style={{
                width: 46, height: 46, borderRadius: 12, flexShrink: 0,
                background: `${s.color}18`,
                border: `1px solid ${s.color}30`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: s.color,
              }}
            >
              {s.icon}
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#fff', lineHeight: 1 }}>{s.value}</div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.40)', marginTop: 4 }}>{s.label}</div>
            </div>
          </div>
        ))}
      </motion.div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20, marginBottom: 24 }}>
        {/* Listening history bar chart */}
        <motion.div
          variants={item}
          style={{
            padding: '22px 24px',
            borderRadius: 16,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
            backdropFilter: 'blur(12px)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <TrendingUp size={16} style={{ color: '#a855f7' }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,0.80)' }}>Listening History</span>
            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.30)', marginLeft: 'auto' }}>Last 7 days</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, height: 120 }}>
            {MOCK_HISTORY.map((d, i) => (
              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, height: '100%', justifyContent: 'flex-end' }}>
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: `${(d.minutes / maxBar) * 100}%` }}
                  transition={{ delay: i * 0.08, duration: 0.5, ease: 'easeOut' }}
                  style={{
                    width: '100%',
                    borderRadius: '6px 6px 0 0',
                    background: 'linear-gradient(to top, #6d28d9, #a855f7)',
                    minHeight: 4,
                  }}
                />
                <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.30)', whiteSpace: 'nowrap' }}>{d.date}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Mood distribution */}
        <motion.div
          variants={item}
          style={{
            padding: '22px 24px',
            borderRadius: 16,
            background: 'rgba(255,255,255,0.04)',
            border: '1px solid rgba(255,255,255,0.08)',
            backdropFilter: 'blur(12px)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <BarChart2 size={16} style={{ color: '#a855f7' }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,0.80)' }}>Mood Distribution</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {MOCK_MOOD_DIST.map((m, i) => {
              const c = MOOD_COLORS[m.mood.toLowerCase()] ?? '#a855f7';
              return (
                <div key={i}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 5 }}>
                    <span style={{ color: 'rgba(255,255,255,0.65)', textTransform: 'capitalize' }}>{m.mood}</span>
                    <span style={{ color: 'rgba(255,255,255,0.40)' }}>{m.pct}%</span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.08)' }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${m.pct}%` }}
                      transition={{ delay: i * 0.1 + 0.3, duration: 0.6, ease: 'easeOut' }}
                      style={{ height: '100%', borderRadius: 3, background: c }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>
      </div>

      {/* Top songs */}
      <motion.div
        variants={item}
        style={{
          padding: '22px 24px',
          borderRadius: 16,
          background: 'rgba(255,255,255,0.04)',
          border: '1px solid rgba(255,255,255,0.08)',
          backdropFilter: 'blur(12px)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
          <Music2 size={16} style={{ color: '#a855f7' }} />
          <span style={{ fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,0.80)' }}>Most Played Songs</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {topSongs.map((song, i) => {
            const mc = MOOD_COLORS[song.mood?.toLowerCase()] ?? '#a855f7';
            return (
              <div
                key={song.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 14,
                  padding: '10px 12px', borderRadius: 10,
                  transition: 'background 0.12s',
                  cursor: 'pointer',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.05)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
              >
                <span style={{ fontSize: 13, fontWeight: 700, color: i === 0 ? '#a855f7' : 'rgba(255,255,255,0.25)', width: 20, flexShrink: 0 }}>
                  {i + 1}
                </span>
                <div style={{ width: 36, height: 36, borderRadius: 8, overflow: 'hidden', flexShrink: 0, background: 'linear-gradient(135deg,#4c1d95,#7c3aed)' }}>
                  {song.artwork && <img src={song.artwork} alt={song.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{song.title}</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.40)' }}>{song.artist}</div>
                </div>
                <div style={{ flexShrink: 0, textAlign: 'right' }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.70)' }}>{song.plays} plays</div>
                  <div style={{ fontSize: 10, color: mc, textTransform: 'capitalize', marginTop: 2 }}>{song.mood}</div>
                </div>
              </div>
            );
          })}
        </div>
      </motion.div>
    </motion.div>
  );
};

export default AnalyticsPage;

