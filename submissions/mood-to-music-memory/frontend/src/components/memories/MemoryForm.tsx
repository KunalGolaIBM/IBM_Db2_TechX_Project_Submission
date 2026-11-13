import React, { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { useAppStore } from '../../store/appStore';
import { MoodMemory } from '../../types';

interface MemoryFormProps {
  onClose: () => void;
}

export const MemoryForm: React.FC<MemoryFormProps> = ({ onClose }) => {
  const { currentSong, selectedMood, addMemory } = useAppStore();

  const [title, setTitle] = useState(currentSong?.title ?? '');
  const [reflection, setReflection] = useState('');
  const MAX_CHARS = 300;

  const handleSave = () => {
    if (!title.trim()) return;
    const memory: MoodMemory = {
      id: `memory-${Date.now()}`,
      title: title.trim(),
      date: new Date().toISOString(),
      mood: selectedMood || 'happy',
      songId: currentSong?.id ?? '',
      reflection: reflection.trim(),
      artwork: currentSong?.artwork ?? 'https://picsum.photos/seed/memory/80/80',
      isBookmarked: false,
    };
    addMemory(memory);
    onClose();
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          transition={{ duration: 0.2 }}
          className="relative rounded-2xl border border-white/10 p-6 shadow-2xl"
          style={{
            width: 400,
            background: 'rgba(20,16,48,0.98)',
            backdropFilter: 'blur(24px)',
          }}
        >
          {/* Close */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1.5 rounded-lg hover:bg-white/10 transition-colors"
          >
            <X size={14} className="text-white/60" />
          </button>

          <h2 className="text-base font-semibold text-white mb-4">Save a Memory</h2>

          {/* Read-only context */}
          {currentSong && (
            <div className="flex items-center gap-3 mb-4 p-3 rounded-xl bg-white/5 border border-white/8">
              <img
                src={currentSong.artwork}
                alt={currentSong.title}
                className="w-10 h-10 rounded-lg object-cover"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{currentSong.title}</p>
                <p className="text-[11px] text-white/50 truncate">{currentSong.artist}</p>
              </div>
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 capitalize">
                {selectedMood}
              </span>
            </div>
          )}

          {/* Title field */}
          <div className="mb-3">
            <label className="block text-xs text-white/50 mb-1.5">Memory Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Give this memory a name..."
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white
                         placeholder:text-white/25 outline-none focus:border-purple-500/60 transition-colors"
            />
          </div>

          {/* Reflection textarea */}
          <div className="mb-5">
            <label className="block text-xs text-white/50 mb-1.5">Reflection</label>
            <textarea
              value={reflection}
              onChange={(e) => setReflection(e.target.value.slice(0, MAX_CHARS))}
              placeholder="What were you feeling? What does this song remind you of..."
              rows={4}
              className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white
                         placeholder:text-white/25 outline-none focus:border-purple-500/60 resize-none transition-colors"
            />
            <div className="text-right text-[10px] text-white/30 mt-1">
              {reflection.length}/{MAX_CHARS}
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="flex-1 py-2 rounded-xl border border-white/10 text-sm text-white/60
                         hover:bg-white/5 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={!title.trim()}
              className="flex-1 py-2 rounded-xl text-sm font-medium text-white transition-opacity
                         disabled:opacity-40"
              style={{
                background: 'linear-gradient(135deg, #7c3aed, #9333ea)',
              }}
            >
              Save Memory
            </button>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default MemoryForm;
