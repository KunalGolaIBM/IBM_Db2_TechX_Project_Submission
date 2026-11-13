import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import {
  Search, Upload, Play, MoreHorizontal, Music2,
  CheckCircle, X, List, Clock,
} from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { Song } from '../types';

type Tab = 'songs' | 'playlists';

const MOOD_COLORS: Record<string, { text: string; bg: string }> = {
  sad:       { text: '#93c5fd', bg: 'rgba(59,130,246,0.15)'  },
  happy:     { text: '#fde047', bg: 'rgba(234,179,8,0.15)'   },
  romantic:  { text: '#f9a8d4', bg: 'rgba(236,72,153,0.15)'  },
  wholesome: { text: '#86efac', bg: 'rgba(34,197,94,0.15)'   },
  ghazal:    { text: '#d8b4fe', bg: 'rgba(168,85,247,0.15)'  },
  calm:      { text: '#d8b4fe', bg: 'rgba(168,85,247,0.15)'  },
};

function moodStyle(mood: string) {
  return MOOD_COLORS[mood?.toLowerCase()] ?? { text: '#9ca3af', bg: 'rgba(107,114,128,0.15)' };
}

function fmt(s: number) {
  const sec = Math.floor(s);
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
}

const LibraryPage: React.FC = () => {
  const navigate = useNavigate();
  const { songs, playlists, addSong, setCurrentSong, startSession } = useAppStore();
  const [tab, setTab] = useState<Tab>('songs');
  const [search, setSearch] = useState('');
  const [toast, setToast] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const filtered = songs.filter(s =>
    s.title.toLowerCase().includes(search.toLowerCase()) ||
    s.artist.toLowerCase().includes(search.toLowerCase())
  );

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;
    files.forEach((f, i) => {
      const song: Song = {
        id: `imp-${Date.now()}-${i}`,
        title: f.name.replace(/\.[^.]+$/, ''),
        artist: 'Unknown Artist',
        duration: 180 + Math.floor(Math.random() * 180),
        artwork: '',
        mood: 'happy',
        playlistId: 'pl3',
      };
      addSong(song);
    });
    setToast(`${files.length} song${files.length > 1 ? 's' : ''} added to your library.`);
    setTimeout(() => setToast(null), 4000);
    e.target.value = '';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{ paddingBottom: 28 }}
    >
      {/* Import toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: -20, x: '50%' }}
            animate={{ opacity: 1, y: 0, x: '50%' }}
            exit={{ opacity: 0, y: -20, x: '50%' }}
            style={{
              position: 'fixed', top: 80, right: '50%',
              transform: 'translateX(50%)',
              zIndex: 100,
              background: 'rgba(20,38,24,0.95)',
              border: '1px solid rgba(74,222,128,0.35)',
              borderRadius: 12,
              padding: '12px 18px',
              display: 'flex', alignItems: 'center', gap: 10,
              backdropFilter: 'blur(20px)',
              boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
            }}
          >
            <CheckCircle size={16} style={{ color: '#4ade80', flexShrink: 0 }} />
            <div>
              <div style={{ fontSize: 12, fontWeight: 700, color: '#4ade80' }}>Import complete</div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.60)' }}>{toast}</div>
            </div>
            <button
              onClick={() => setToast(null)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.40)', padding: 2, marginLeft: 4 }}
            >
              <X size={12} />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24, gap: 16, flexWrap: 'wrap' }}>
        {/* Tabs */}
        <div style={{ display: 'flex', background: 'rgba(255,255,255,0.05)', borderRadius: 10, padding: 4, gap: 2 }}>
          {(['songs', 'playlists'] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              style={{
                padding: '7px 18px', borderRadius: 7, border: 'none',
                background: tab === t ? 'rgba(168,85,247,0.70)' : 'transparent',
                color: tab === t ? '#fff' : 'rgba(255,255,255,0.45)',
                fontSize: 13, fontWeight: tab === t ? 600 : 400,
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >
              {t === 'songs' ? 'My Songs' : 'Playlists'}
            </button>
          ))}
        </div>

        {/* Search + Import */}
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,0.35)', pointerEvents: 'none' }} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search songs…"
              style={{
                padding: '8px 12px 8px 32px', borderRadius: 9,
                border: '1px solid rgba(255,255,255,0.10)',
                background: 'rgba(255,255,255,0.05)',
                color: '#fff', fontSize: 13, outline: 'none', width: 200,
              }}
            />
          </div>
          <input ref={fileRef} type="file" accept="audio/*" multiple style={{ display: 'none' }} onChange={handleImport} />
          <button
            onClick={() => fileRef.current?.click()}
            style={{
              display: 'flex', alignItems: 'center', gap: 7,
              padding: '8px 14px', borderRadius: 9, border: 'none',
              background: 'linear-gradient(135deg, #6d28d9, #a855f7)',
              color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(109,40,217,0.4)',
            }}
          >
            <Upload size={14} /> Import Music
          </button>
        </div>
      </div>

      {/* Content */}
      {tab === 'songs' ? (
        <div>
          {/* Table header */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: '36px 1fr 160px 80px 100px 36px',
            gap: 12, padding: '6px 14px 10px',
            borderBottom: '1px solid rgba(255,255,255,0.07)',
            fontSize: 11, fontWeight: 600, color: 'rgba(255,255,255,0.30)',
            textTransform: 'uppercase', letterSpacing: '0.07em',
          }}>
            <span>#</span>
            <span>Title</span>
            <span>Artist</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Clock size={11} /> Duration</span>
            <span>Mood</span>
            <span />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, marginTop: 4 }}>
            {filtered.map((song, idx) => {
              const ms = moodStyle(song.mood);
              return (
                <motion.div
                  key={song.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: idx * 0.03 }}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '36px 1fr 160px 80px 100px 36px',
                    gap: 12, padding: '10px 14px',
                    borderRadius: 10,
                    cursor: 'pointer',
                    alignItems: 'center',
                    transition: 'background 0.12s',
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLDivElement).style.background = 'rgba(255,255,255,0.05)'; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
                  onClick={() => { setCurrentSong(song); navigate('/now-playing'); }}
                >
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.30)' }}>{idx + 1}</span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                    <div style={{ width: 36, height: 36, borderRadius: 8, overflow: 'hidden', flexShrink: 0, background: 'linear-gradient(135deg,#4c1d95,#7c3aed)' }}>
                      {song.artwork && (
                        <img src={song.artwork} alt={song.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          onError={e2 => { (e2.currentTarget as HTMLImageElement).style.display = 'none'; }} />
                      )}
                    </div>
                    <span style={{ fontSize: 13, fontWeight: 500, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{song.title}</span>
                  </div>
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.50)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{song.artist}</span>
                  <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)' }}>{fmt(song.duration)}</span>
                  <span style={{ fontSize: 11, fontWeight: 500, padding: '3px 10px', borderRadius: 20, background: ms.bg, color: ms.text, textTransform: 'capitalize', display: 'inline-block', textAlign: 'center' }}>
                    {song.mood}
                  </span>
                  <button onClick={e => e.stopPropagation()} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.35)', padding: 4, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <MoreHorizontal size={15} />
                  </button>
                </motion.div>
              );
            })}
            {filtered.length === 0 && (
              <div style={{ padding: '40px 0', textAlign: 'center', color: 'rgba(255,255,255,0.25)', fontSize: 13 }}>
                <Music2 size={32} style={{ marginBottom: 10, opacity: 0.3 }} />
                <div>No songs found</div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16 }}>
          {playlists.map(pl => {
            const count = pl.songIds.length;
            const ms = moodStyle(pl.mood);
            return (
              <motion.div
                key={pl.id}
                whileHover={{ scale: 1.02, y: -3 }}
                style={{
                  borderRadius: 16,
                  border: '1px solid rgba(255,255,255,0.08)',
                  background: 'rgba(255,255,255,0.04)',
                  overflow: 'hidden',
                  cursor: 'pointer',
                  backdropFilter: 'blur(12px)',
                }}
                onClick={() => startSession(pl.mood, pl)}
              >
                {/* Artwork placeholder */}
                <div style={{
                  height: 140,
                  background: `linear-gradient(135deg, ${ms.bg.replace('0.15', '0.4')}, rgba(109,40,217,0.4))`,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  position: 'relative',
                }}>
                  <List size={36} style={{ color: ms.text, opacity: 0.6 }} />
                  <button
                    onClick={e => { e.stopPropagation(); startSession(pl.mood, pl); navigate('/now-playing'); }}
                    style={{
                      position: 'absolute', bottom: 12, right: 12,
                      width: 36, height: 36, borderRadius: '50%',
                      background: 'linear-gradient(135deg,#6d28d9,#a855f7)',
                      border: 'none', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      boxShadow: '0 4px 12px rgba(109,40,217,0.5)',
                    }}
                  >
                    <Play size={16} color="#fff" style={{ marginLeft: 2 }} />
                  </button>
                </div>
                <div style={{ padding: '12px 14px' }}>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#fff', marginBottom: 4 }}>{pl.name}</div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.40)' }}>{count} song{count !== 1 ? 's' : ''}</span>
                    <span style={{ fontSize: 10, fontWeight: 500, padding: '2px 8px', borderRadius: 20, background: ms.bg, color: ms.text, textTransform: 'capitalize' }}>{pl.mood}</span>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
};

export default LibraryPage;

