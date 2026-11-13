import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Bookmark, MoreHorizontal, Sparkles, Play, X, Trash2, Edit3 } from 'lucide-react';
import { useAppStore } from '../store/appStore';
import { MoodMemory } from '../types';

const MOOD_COLORS: Record<string, { text: string; bg: string; border: string }> = {
  sad:       { text: '#93c5fd', bg: 'rgba(59,130,246,0.15)',  border: 'rgba(59,130,246,0.30)'  },
  happy:     { text: '#fde047', bg: 'rgba(234,179,8,0.15)',   border: 'rgba(234,179,8,0.30)'   },
  romantic:  { text: '#f9a8d4', bg: 'rgba(236,72,153,0.15)',  border: 'rgba(236,72,153,0.30)'  },
  wholesome: { text: '#86efac', bg: 'rgba(34,197,94,0.15)',   border: 'rgba(34,197,94,0.30)'   },
  ghazal:    { text: '#d8b4fe', bg: 'rgba(168,85,247,0.15)',  border: 'rgba(168,85,247,0.30)'  },
};

function moodStyle(mood: string) {
  return MOOD_COLORS[mood?.toLowerCase()] ?? { text: '#9ca3af', bg: 'rgba(107,114,128,0.15)', border: 'rgba(107,114,128,0.30)' };
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

// ── Memory Form Modal ──────────────────────────────────────────────────────────
const MemoryFormModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { currentSong, selectedMood, addMemory } = useAppStore();
  const [title, setTitle] = useState(currentSong?.title ?? '');
  const [reflection, setReflection] = useState('');
  const MAX = 300;

  const save = () => {
    if (!title.trim()) return;
    const mem: MoodMemory = {
      id: `mem-${Date.now()}`,
      title: title.trim(),
      date: new Date().toISOString(),
      mood: selectedMood || 'happy',
      songId: currentSong?.id ?? '',
      reflection: reflection.trim(),
      artwork: currentSong?.artwork ?? `https://picsum.photos/seed/mem${Date.now()}/80/80`,
      isBookmarked: false,
    };
    addMemory(mem);
    onClose();
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        position: 'fixed', inset: 0, zIndex: 200,
        background: 'rgba(0,0,0,0.65)', backdropFilter: 'blur(8px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.92, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.92, opacity: 0 }}
        transition={{ duration: 0.2 }}
        onClick={e => e.stopPropagation()}
        style={{
          width: 440, borderRadius: 20,
          background: 'rgba(14,10,36,0.98)',
          border: '1px solid rgba(255,255,255,0.12)',
          padding: '28px',
          boxShadow: '0 24px 60px rgba(0,0,0,0.6)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: '#fff', margin: 0 }}>Save a Memory</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'rgba(255,255,255,0.45)', padding: 4 }}>
            <X size={16} />
          </button>
        </div>

        {/* Song context */}
        {currentSong && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', borderRadius: 12, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)', marginBottom: 20 }}>
            <div style={{ width: 40, height: 40, borderRadius: 8, overflow: 'hidden', background: 'linear-gradient(135deg,#4c1d95,#7c3aed)', flexShrink: 0 }}>
              {currentSong.artwork && <img src={currentSong.artwork} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{currentSong.title}</div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)' }}>{currentSong.artist}</div>
            </div>
            {selectedMood && (
              <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 20, background: 'rgba(168,85,247,0.20)', color: '#c084fc', textTransform: 'capitalize', flexShrink: 0 }}>
                {selectedMood}
              </span>
            )}
          </div>
        )}

        {/* Title */}
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', display: 'block', marginBottom: 6 }}>Memory Title</label>
          <input
            value={title}
            onChange={e => setTitle(e.target.value)}
            placeholder="Name this memory…"
            style={{
              width: '100%', boxSizing: 'border-box',
              padding: '10px 12px', borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.10)',
              background: 'rgba(255,255,255,0.05)',
              color: '#fff', fontSize: 13, outline: 'none',
            }}
          />
        </div>

        {/* Reflection */}
        <div style={{ marginBottom: 24 }}>
          <label style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', display: 'block', marginBottom: 6 }}>Reflection</label>
          <textarea
            value={reflection}
            onChange={e => setReflection(e.target.value.slice(0, MAX))}
            placeholder="What were you feeling? What does this song remind you of…"
            rows={4}
            style={{
              width: '100%', boxSizing: 'border-box',
              padding: '10px 12px', borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.10)',
              background: 'rgba(255,255,255,0.05)',
              color: '#fff', fontSize: 13, outline: 'none',
              resize: 'none',
            }}
          />
          <div style={{ textAlign: 'right', fontSize: 10, color: 'rgba(255,255,255,0.28)', marginTop: 4 }}>
            {reflection.length}/{MAX}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={onClose} style={{ flex: 1, padding: '10px 0', borderRadius: 10, border: '1px solid rgba(255,255,255,0.12)', background: 'transparent', color: 'rgba(255,255,255,0.60)', fontSize: 13, fontWeight: 600, cursor: 'pointer' }}>
            Cancel
          </button>
          <button
            onClick={save}
            disabled={!title.trim()}
            style={{
              flex: 1, padding: '10px 0', borderRadius: 10, border: 'none',
              background: title.trim() ? 'linear-gradient(135deg,#6d28d9,#a855f7)' : 'rgba(255,255,255,0.08)',
              color: title.trim() ? '#fff' : 'rgba(255,255,255,0.28)',
              fontSize: 13, fontWeight: 700, cursor: title.trim() ? 'pointer' : 'not-allowed',
              boxShadow: title.trim() ? '0 4px 14px rgba(109,40,217,0.4)' : 'none',
            }}
          >
            Save Memory
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
};

// ── Main Page ──────────────────────────────────────────────────────────────────
const MemoriesPage: React.FC = () => {
  const { memories, songs, toggleBookmark, deleteMemory } = useAppStore();
  const [showForm, setShowForm] = useState(false);
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{ paddingBottom: 28 }}
    >
      {/* Modal */}
      <AnimatePresence>
        {showForm && <MemoryFormModal onClose={() => setShowForm(false)} />}
      </AnimatePresence>

      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 800, color: '#fff', margin: 0 }}>My Mood Memories</h2>
          <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.40)', marginTop: 4 }}>
            {memories.length} saved moment{memories.length !== 1 ? 's' : ''}
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
          onClick={() => setShowForm(true)}
          style={{
            display: 'flex', alignItems: 'center', gap: 7,
            padding: '9px 16px', borderRadius: 10, border: 'none',
            background: 'linear-gradient(135deg,#6d28d9,#a855f7)',
            color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
            boxShadow: '0 4px 16px rgba(109,40,217,0.4)',
          }}
        >
          <Plus size={15} /> Save a Memory
        </motion.button>
      </div>

      <div style={{ display: 'flex', gap: 24, alignItems: 'flex-start' }}>
        {/* Memory cards */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <AnimatePresence initial={false}>
            {memories.map(mem => {
              const song = songs.find(s => s.id === mem.songId);
              const ms = moodStyle(mem.mood);
              return (
                <motion.div
                  key={mem.id}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, x: -20, height: 0, marginBottom: 0 }}
                  transition={{ duration: 0.25 }}
                  style={{
                    display: 'flex', alignItems: 'flex-start', gap: 16,
                    padding: '16px 18px',
                    borderRadius: 14,
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    backdropFilter: 'blur(12px)',
                    position: 'relative',
                  }}
                >
                  {/* Artwork */}
                  <div style={{ width: 60, height: 60, borderRadius: 12, overflow: 'hidden', flexShrink: 0, background: 'linear-gradient(135deg,#4c1d95,#7c3aed)' }}>
                    {mem.artwork && <img src={mem.artwork} alt={mem.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={e => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }} />}
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                      <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>{fmtDate(mem.date)}</span>
                      <span style={{ fontSize: 10, fontWeight: 600, padding: '2px 9px', borderRadius: 20, background: ms.bg, color: ms.text, border: `1px solid ${ms.border}`, textTransform: 'capitalize' }}>
                        {mem.mood}
                      </span>
                    </div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#fff', marginBottom: 3 }}>{mem.title}</div>
                    {song && <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.50)', marginBottom: 8 }}>{song.title} · {song.artist}</div>}
                    {mem.reflection && (
                      <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.45)', lineHeight: 1.6, margin: 0, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        "{mem.reflection}"
                      </p>
                    )}
                  </div>

                  {/* Actions */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                    <button
                      onClick={() => toggleBookmark(mem.id)}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center' }}
                    >
                      <Bookmark
                        size={16}
                        style={{ color: mem.isBookmarked ? '#fbbf24' : 'rgba(255,255,255,0.30)', fill: mem.isBookmarked ? '#fbbf24' : 'none' }}
                      />
                    </button>

                    <div style={{ position: 'relative' }}>
                      <button
                        onClick={() => setOpenMenu(openMenu === mem.id ? null : mem.id)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4, display: 'flex', alignItems: 'center', color: 'rgba(255,255,255,0.35)' }}
                      >
                        <MoreHorizontal size={16} />
                      </button>
                      {openMenu === mem.id && (
                        <div
                          style={{
                            position: 'absolute', right: 0, top: '100%', zIndex: 50,
                            background: 'rgba(18,14,42,0.98)',
                            border: '1px solid rgba(255,255,255,0.12)',
                            borderRadius: 10, overflow: 'hidden',
                            boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
                            minWidth: 130,
                          }}
                          onMouseLeave={() => setOpenMenu(null)}
                        >
                          <button
                            style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '10px 14px', border: 'none', background: 'none', color: 'rgba(255,255,255,0.70)', fontSize: 12, cursor: 'pointer', textAlign: 'left' }}
                            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.07)'; }}
                            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'none'; }}
                            onClick={() => setOpenMenu(null)}
                          >
                            <Edit3 size={12} /> Edit
                          </button>
                          <button
                            style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '10px 14px', border: 'none', background: 'none', color: '#f87171', fontSize: 12, cursor: 'pointer', textAlign: 'left' }}
                            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'rgba(248,113,113,0.08)'; }}
                            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'none'; }}
                            onClick={() => { deleteMemory(mem.id); setOpenMenu(null); }}
                          >
                            <Trash2 size={12} /> Delete
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>

          {memories.length === 0 && (
            <div style={{ padding: '60px 0', textAlign: 'center', color: 'rgba(255,255,255,0.25)', fontSize: 13 }}>
              <Bookmark size={36} style={{ marginBottom: 12, opacity: 0.2 }} />
              <div>No memories yet.</div>
              <div style={{ marginTop: 6, fontSize: 12 }}>Save a moment to see it here.</div>
            </div>
          )}
        </div>

        {/* Similar memory sidebar */}
        <div
          style={{
            width: 180,
            flexShrink: 0,
            borderRadius: 16,
            background: 'rgba(168,85,247,0.07)',
            border: '1px solid rgba(168,85,247,0.18)',
            padding: '16px',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, alignSelf: 'flex-start' }}>
            <Sparkles size={12} style={{ color: '#c084fc' }} />
            <span style={{ fontSize: 11, color: '#c084fc', fontWeight: 600 }}>Similar Memory</span>
          </div>
          <div style={{ width: 100, height: 100, borderRadius: 14, overflow: 'hidden', background: 'linear-gradient(135deg,#4c1d95,#7c3aed)' }}>
            <img src="https://picsum.photos/seed/ghazal-night/100/100" alt="Raat ki Khamoshi" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#fff' }}>Raat ki Khamoshi</div>
            <div style={{ fontSize: 11, color: '#c084fc', marginTop: 2 }}>(Ghazal)</div>
            <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.40)', marginTop: 6, lineHeight: 1.5 }}>
              You might like revisiting this memory.
            </div>
          </div>
          <button
            style={{
              width: 40, height: 40, borderRadius: '50%',
              background: 'rgba(168,85,247,0.55)',
              border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 4px 14px rgba(168,85,247,0.4)',
            }}
          >
            <Play size={16} color="#fff" style={{ marginLeft: 2 }} />
          </button>
        </div>
      </div>
    </motion.div>
  );
};

export default MemoriesPage;

