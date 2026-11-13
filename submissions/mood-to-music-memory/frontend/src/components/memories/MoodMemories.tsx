import React, { useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { BookOpen, Plus } from 'lucide-react';
import { useAppStore } from '../../store/appStore';
import WindowHeader from '../layout/WindowHeader';
import { MemoryCard } from './MemoryCard';
import { MemoryForm } from './MemoryForm';
import { SimilarMemory } from './SimilarMemory';

export const MoodMemories: React.FC = () => {
  const { memories, songs } = useAppStore();
  const [showForm, setShowForm] = useState(false);

  return (
    <div
      className="glass-panel flex flex-col h-full w-full"
      style={{
        background: 'rgba(15,12,38,0.88)',
        backdropFilter: 'blur(22px)',
      }}
    >
      {/* Header */}
      <WindowHeader
        title="My Mood Memories"
        icon={<BookOpen size={14} />}
      />

      {/* Body */}
      <div className="flex flex-row flex-1 overflow-hidden">
        {/* Left — scrollable list */}
        <div className="flex flex-col flex-1 overflow-hidden px-3 py-3 gap-2">
          {/* Add button */}
          <button
            onClick={() => setShowForm(true)}
            className="flex items-center gap-1.5 self-start px-3 py-1.5 rounded-lg border border-purple-500/40
                       text-xs text-purple-300 hover:bg-purple-500/10 transition-colors mb-1"
          >
            <Plus size={12} />
            Save a New Memory
          </button>

          {/* Memories list */}
          <div className="flex-1 overflow-y-auto space-y-2 pr-1
                          scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10">
            <AnimatePresence initial={false}>
              {memories.map((memory) => (
                <motion.div
                  key={memory.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.2 }}
                >
                  <MemoryCard memory={memory} songs={songs} />
                </motion.div>
              ))}
            </AnimatePresence>

            {memories.length === 0 && (
              <div className="flex items-center justify-center h-full pt-10">
                <p className="text-xs text-white/30">No memories yet. Save your first!</p>
              </div>
            )}
          </div>
        </div>

        {/* Right — SimilarMemory */}
        <div className="py-3 pr-3" style={{ width: 140, flexShrink: 0 }}>
          <SimilarMemory />
        </div>
      </div>

      {/* MemoryForm modal */}
      <AnimatePresence>
        {showForm && <MemoryForm onClose={() => setShowForm(false)} />}
      </AnimatePresence>
    </div>
  );
};

export default MoodMemories;
