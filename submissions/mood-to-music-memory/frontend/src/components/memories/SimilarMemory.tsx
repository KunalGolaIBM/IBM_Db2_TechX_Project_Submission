import React from 'react';
import { Sparkles, Play } from 'lucide-react';

export const SimilarMemory: React.FC = () => {
  return (
    <div
      className="flex flex-col items-center rounded-2xl p-3 h-full"
      style={{
        background: 'rgba(168,85,247,0.08)',
        border: '1px solid rgba(168,85,247,0.2)',
        width: '100%',
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-1 mb-3 w-full">
        <Sparkles size={11} className="text-purple-300 flex-shrink-0" />
        <span className="text-[10px] text-purple-300 leading-tight">
          A memory that feels similar
        </span>
      </div>

      {/* Album art */}
      <img
        src="https://picsum.photos/seed/ghazal-night/80/80"
        alt="Raat ki Khamoshi"
        className="w-20 h-20 rounded-xl object-cover mb-2"
      />

      {/* Song info */}
      <p className="text-sm font-medium text-white text-center leading-tight">
        Raat ki Khamoshi
      </p>
      <p className="text-xs text-purple-400 mt-0.5">(Ghazal)</p>
      <p className="text-[10px] text-white/50 text-center mt-1 leading-tight">
        You might like revisiting this memory.
      </p>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Play button */}
      <button
        className="w-10 h-10 rounded-full flex items-center justify-center transition-opacity hover:opacity-80"
        style={{ background: 'rgba(168,85,247,0.6)' }}
      >
        <Play size={16} className="text-white fill-white ml-0.5" />
      </button>
    </div>
  );
};

export default SimilarMemory;
