import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Bookmark, MoreHorizontal } from 'lucide-react';
import { MoodMemory, Song } from '../../types';
import { useAppStore } from '../../store/appStore';

interface MemoryCardProps {
  memory: MoodMemory;
  songs: Song[];
}

const moodBadgeColors: Record<string, string> = {
  sad: 'bg-blue-500/20 text-blue-300',
  happy: 'bg-yellow-500/20 text-yellow-300',
  romantic: 'bg-pink-500/20 text-pink-300',
  wholesome: 'bg-green-500/20 text-green-300',
  ghazal: 'bg-purple-500/20 text-purple-300',
};

export const MemoryCard: React.FC<MemoryCardProps> = ({ memory, songs }) => {
  const { toggleBookmark, deleteMemory } = useAppStore();
  const [showDropdown, setShowDropdown] = useState(false);

  const song = songs.find((s) => s.id === memory.songId);
  const badgeClass = moodBadgeColors[memory.mood] ?? 'bg-white/10 text-white/60';

  const formattedDate = new Date(memory.date).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.25 }}
      className="relative flex items-center gap-3 rounded-xl border border-white/[0.08] bg-white/5 px-3 py-3
                 hover:bg-white/[0.08] transition-colors cursor-pointer"
    >
      {/* Artwork */}
      <img
        src={memory.artwork}
        alt={memory.title}
        className="w-12 h-12 rounded-lg object-cover flex-shrink-0"
      />

      {/* Middle content */}
      <div className="flex-1 min-w-0">
        <span className="text-[10px] text-white/40">{formattedDate}</span>
        <div className="flex items-center gap-1.5 mt-0.5 mb-0.5">
          <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full capitalize ${badgeClass}`}>
            {memory.mood}
          </span>
        </div>
        <p className="text-sm font-medium text-white leading-tight truncate">
          {song?.title ?? memory.title}
        </p>
        <p
          className="text-[11px] text-white/50 mt-0.5 leading-tight"
          style={{
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
          }}
        >
          {memory.reflection}
        </p>
      </div>

      {/* Right controls */}
      <div className="flex flex-col items-center gap-2 flex-shrink-0">
        <button
          onClick={(e) => {
            e.stopPropagation();
            toggleBookmark(memory.id);
          }}
          className="p-1 rounded-md hover:bg-white/10 transition-colors"
        >
          <Bookmark
            size={14}
            className={memory.isBookmarked ? 'fill-yellow-400 text-yellow-400' : 'text-white/40'}
          />
        </button>

        <div className="relative">
          <button
            onClick={(e) => {
              e.stopPropagation();
              setShowDropdown((v) => !v);
            }}
            className="p-1 rounded-md hover:bg-white/10 transition-colors"
          >
            <MoreHorizontal size={14} className="text-white/40" />
          </button>

          {showDropdown && (
            <div
              className="absolute right-0 top-full mt-1 z-30 rounded-lg bg-[#1e1a3a] border border-white/10
                         shadow-xl overflow-hidden text-xs"
              onMouseLeave={() => setShowDropdown(false)}
            >
              <button
                className="block w-full px-4 py-2 text-left text-white/70 hover:bg-white/10 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowDropdown(false);
                }}
              >
                Edit
              </button>
              <button
                className="block w-full px-4 py-2 text-left text-red-400 hover:bg-red-500/10 transition-colors"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowDropdown(false);
                  deleteMemory(memory.id);
                }}
              >
                Delete
              </button>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};

export default MemoryCard;
