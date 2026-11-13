import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Clock, Music2, Heart, Bookmark, TrendingUp, BarChart2, Database, Wifi, WifiOff } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { api, ApiAnalytics } from '../api/client';

const MOOD_COLORS: Record<string, string> = {
  sad: '#60a5fa', happy: '#fbbf24', romantic: '#f472b6',
  wholesome: '#4ade80', ghazal: '#c084fc', calm: '#c084fc',
};

const container = { hidden: {}, show: { transition: { staggerChildren: 0.07 } } };
const item = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.35 } } };

// Fallback mock history for the bar chart (session-based data)
const FALLBACK_HISTORY = [
  { date: 'Mon', count: 2 },
  { date: 'Tue', count: 4 },
  { date: 'Wed', count: 1 },
  { date: 'Thu', count: 5 },
  { date: 'Fri', count: 3 },
  { date: 'Sat', count: 7 },
  { date: 'Sun', count: 4 },
];

const AnalyticsPage: React.FC = () => {
  const { memories, db2Connected } = useAppStore();
  const [analytics, setAnalytics] = useState<ApiAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.analytics()
      .then(data => { setAnalytics(data); setError(false); })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, []);

  // Build stats from real or fallback data
  const totalSessions = analytics?.totalSessions ?? 0;
  const totalMemories = analytics?.totalMemories ?? memories.length;
  const totalSongs    = analytics?.totalSongs ?? 0;
  const mostPlayedMood = analytics?.mostPlayedMood ?? 'Romantic';

  const stats = [
    { label: 'Total Sessions',    value: totalSessions.toString(), icon: <TrendingUp size={18} />, color: '#a855f7' },
    { label: 'Most Listened Mood',value: mostPlayedMood,            icon: <Heart size={18} />,      color: '#f472b6' },
    { label: 'Songs in Library',  value: totalSongs.toString(),     icon: <Music2 size={18} />,     color: '#60a5fa' },
    { label: 'Saved Memories',    value: totalMemories.toString(),  icon: <Bookmark size={18} />,   color: '#fbbf24' },
  ];

  // Bar chart: build from recent sessions (group by day) or use fallback
  const barData = (() => {
    if (!analytics?.recentSessions?.length) return FALLBACK_HISTORY;
    const dayCounts: Record<string, number> = {};
    analytics.recentSessions.forEach(s => {
      const d = new Date(s.startedAt).toLocaleDateString('en-IN', { weekday: 'short' });
      dayCounts[d] = (dayCounts[d] ?? 0) + 1;
    });
    return Object.entries(dayCounts).map(([date, count]) => ({ date, count }));
  })();
  const maxBar = Math.max(...barData.map(d => d.count), 1);

  // Mood distribution from real data
  const moodDist = analytics?.moodDistribution?.length
    ? analytics.moodDistribution
    : [
        { mood: 'romantic',  moodDisplay: 'Romantic',  count: 38 },
        { mood: 'sad',       moodDisplay: 'Sad',       count: 24 },
        { mood: 'happy',     moodDisplay: 'Happy',     count: 18 },
        { mood: 'ghazal',    moodDisplay: 'Ghazal',    count: 12 },
        { mood: 'wholesome', moodDisplay: 'Wholesome', count: 8  },
      ];
  const totalMoodCount = moodDist.reduce((s, m) => s + m.count, 0) || 1;

  const topSongs = analytics?.topSongs ?? [];

  return (
    <motion.div
      initial="hidden" animate="show" variants={container}
      style={{ paddingBottom: 28 }}
    >
      {/* Db2 status badge */}
      <motion.div variants={item} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '5px 12px', borderRadius: 20,
            background: db2Connected && !error
              ? 'rgba(74,222,128,0.12)' : 'rgba(248,113,113,0.12)',
            border: `1px solid ${db2Connected && !error ? 'rgba(74,222,128,0.30)' : 'rgba(248,113,113,0.25)'}`,
          }}
        >
          {db2Connected && !error
            ? <><Wifi size={12} style={{ color: '#4ade80' }} /><Database size={12} style={{ color: '#4ade80' }} /><span style={{ fontSize: 11, color: '#4ade80', fontWeight: 600 }}>Live Db2 Data</span></>
            : <><WifiOff size={12} style={{ color: '#f87171' }} /><span style={{ fontSize: 11, color: '#f87171', fontWeight: 600 }}>{loading ? 'Connecting to Db2…' : 'Using sample data'}</span></>
          }
        </div>
        <h2 style={{ fontSize: 20, fontWeight: 800, color: '#fff', margin: 0 }}>Analytics</h2>
      </motion.div>

      {/* Stats cards */}
      <motion.div variants={item} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(200px,1fr))', gap: 16, marginBottom: 32 }}>
        {stats.map((s, i) => (
          <div
            key={i}
            style={{
              padding: '20px 20px', borderRadius: 16,
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.08)',
              backdropFilter: 'blur(12px)',
              display: 'flex', alignItems: 'center', gap: 16,
            }}
          >
            <div
              style={{
                width: 46, height: 46, borderRadius: 12, flexShrink: 0,
                background: `${s.color}18`, border: `1px solid ${s.color}30`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: s.color,
              }}
            >
              {s.icon}
            </div>
            <div>
              <div style={{ fontSize: 22, fontWeight: 800, color: '#fff', lineHeight: 1 }}>
                {loading ? '—' : s.value}
              </div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.40)', marginTop: 4 }}>{s.label}</div>
            </div>
          </div>
        ))}
      </motion.div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 20, marginBottom: 24 }}>
        {/* Listening history bar chart */}
        <motion.div
          variants={item}
          style={{ padding: '22px 24px', borderRadius: 16, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', backdropFilter: 'blur(12px)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <TrendingUp size={16} style={{ color: '#a855f7' }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,0.80)' }}>Session Activity</span>
            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.30)', marginLeft: 'auto' }}>Sessions per day</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, height: 120 }}>
            {barData.map((d, i) => (
              <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, height: '100%', justifyContent: 'flex-end' }}>
                <motion.div
                  initial={{ height: 0 }}
                  animate={{ height: `${(d.count / maxBar) * 100}%` }}
                  transition={{ delay: i * 0.08, duration: 0.5, ease: 'easeOut' }}
                  style={{ width: '100%', borderRadius: '6px 6px 0 0', background: 'linear-gradient(to top, #6d28d9, #a855f7)', minHeight: 4 }}
                />
                <span style={{ fontSize: 9, color: 'rgba(255,255,255,0.30)', whiteSpace: 'nowrap' }}>{d.date}</span>
              </div>
            ))}
          </div>
        </motion.div>

        {/* Mood distribution */}
        <motion.div
          variants={item}
          style={{ padding: '22px 24px', borderRadius: 16, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', backdropFilter: 'blur(12px)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 20 }}>
            <BarChart2 size={16} style={{ color: '#a855f7' }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,0.80)' }}>Mood Distribution</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {moodDist.map((m, i) => {
              const c = MOOD_COLORS[m.mood] ?? '#a855f7';
              const pct = Math.round((m.count / totalMoodCount) * 100);
              return (
                <div key={i}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 5 }}>
                    <span style={{ color: 'rgba(255,255,255,0.65)', textTransform: 'capitalize' }}>{m.moodDisplay}</span>
                    <span style={{ color: 'rgba(255,255,255,0.40)' }}>{pct}%</span>
                  </div>
                  <div style={{ height: 6, borderRadius: 3, background: 'rgba(255,255,255,0.08)' }}>
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
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

      {/* Top songs / Recent sessions */}
      <motion.div
        variants={item}
        style={{ padding: '22px 24px', borderRadius: 16, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', backdropFilter: 'blur(12px)' }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 18 }}>
          <Music2 size={16} style={{ color: '#a855f7' }} />
          <span style={{ fontSize: 14, fontWeight: 700, color: 'rgba(255,255,255,0.80)' }}>
            {topSongs.length > 0 ? 'Most Played Songs' : 'Recent Sessions'}
          </span>
        </div>

        {topSongs.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {topSongs.map((song, i) => (
              <div
                key={i}
                style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '10px 12px', borderRadius: 10, cursor: 'default' }}
                onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.05)'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
              >
                <span style={{ fontSize: 13, fontWeight: 700, color: i === 0 ? '#a855f7' : 'rgba(255,255,255,0.25)', width: 20, flexShrink: 0 }}>
                  {i + 1}
                </span>
                <div style={{ width: 36, height: 36, borderRadius: 8, flexShrink: 0, background: 'linear-gradient(135deg,#4c1d95,#7c3aed)' }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{song.title}</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.40)' }}>{song.artist}</div>
                </div>
                <div style={{ flexShrink: 0, textAlign: 'right' }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'rgba(255,255,255,0.70)' }}>{song.appearances} playlists</div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          /* Show recent sessions if no top songs yet */
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {(analytics?.recentSessions ?? []).slice(0, 7).map((s, i) => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 12px', borderRadius: 8 }}>
                <div style={{ width: 10, height: 10, borderRadius: '50%', background: MOOD_COLORS[s.mood] ?? '#a855f7', flexShrink: 0 }} />
                <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.65)', textTransform: 'capitalize' }}>{s.moodDisplay}</span>
                <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.30)', marginLeft: 'auto' }}>
                  {new Date(s.startedAt).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
                </span>
              </div>
            ))}
            {(!analytics?.recentSessions?.length) && (
              <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.25)', padding: '24px 0', fontSize: 13 }}>
                No sessions recorded yet. Start a mood session to see data here.
              </div>
            )}
          </div>
        )}
      </motion.div>
    </motion.div>
  );
};

export default AnalyticsPage;
