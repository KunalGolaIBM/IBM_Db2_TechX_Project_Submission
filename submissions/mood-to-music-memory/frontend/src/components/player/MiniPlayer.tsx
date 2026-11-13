import React from 'react';
import {
  Shuffle,
  SkipBack,
  Play,
  Pause,
  SkipForward,
  Repeat,
  Heart,
  Maximize2,
} from 'lucide-react';
import { useAppStore } from '../../store/appStore';

export const MiniPlayer: React.FC = () => {
  const {
    currentSong,
    isPlaying,
    currentTime,
    shuffleEnabled,
    repeatEnabled,
    togglePlay,
    nextSong,
    prevSong,
    toggleShuffle,
    toggleRepeat,
  } = useAppStore();

  const duration = currentSong?.duration ?? 1;
  const progress = Math.min((currentTime / duration) * 100, 100);

  const moodColors: Record<string, string> = {
    romantic: 'bg-pink-500/30 text-pink-300',
    focus: 'bg-blue-500/30 text-blue-300',
    energetic: 'bg-orange-500/30 text-orange-300',
    calm: 'bg-teal-500/30 text-teal-300',
    happy: 'bg-yellow-500/30 text-yellow-300',
    melancholic: 'bg-indigo-500/30 text-indigo-300',
  };
  const moodClass = currentSong?.mood
    ? (moodColors[currentSong.mood] ?? 'bg-purple-500/30 text-purple-300')
    : 'bg-purple-500/30 text-purple-300';

  return (
    <div
      className="flex flex-col rounded-2xl border border-white/10 overflow-hidden"
      style={{ background: 'rgba(20,16,50,0.90)', backdropFilter: 'blur(18px)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.06]">
        <span className="text-xs font-semibold text-white/70 tracking-wide uppercase">
          Mini Player
        </span>
        <button className="text-white/30 hover:text-white/70 transition-colors">
          <Maximize2 size={12} />
        </button>
      </div>

      <div className="flex flex-col px-3 pt-3 pb-2 gap-2">
        {/* Song info row */}
        <div className="flex items-center gap-2">
          {/* Artwork */}
          <div className="flex-shrink-0 w-11 h-11 rounded-lg overflow-hidden bg-white/10">
            {currentSong?.artwork ? (
              <img
                src={currentSong.artwork}
                alt={currentSong.title}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-white/20 text-lg">
                ♪
              </div>
            )}
          </div>

          {/* Title / artist / mood */}
          <div className="flex flex-col flex-1 min-w-0">
            <span className="text-xs font-semibold text-white/90 truncate leading-tight">
              {currentSong?.title ?? 'No song selected'}
            </span>
            <span className="text-[10px] text-white/40 truncate leading-tight mt-0.5">
              {currentSong?.artist ?? '—'}
            </span>
            {currentSong?.mood && (
              <span
                className={`mt-1 self-start text-[9px] font-medium px-1.5 py-0.5 rounded-full ${moodClass}`}
              >
                {currentSong.mood.charAt(0).toUpperCase() + currentSong.mood.slice(1)}
              </span>
            )}
          </div>

          {/* Heart */}
          <button className="flex-shrink-0 text-white/30 hover:text-pink-400 transition-colors">
            <Heart size={14} />
          </button>
        </div>

        {/* Progress bar */}
        <div className="w-full bg-white/10 rounded-full overflow-hidden" style={{ height: 3 }}>
          <div
            className="h-full rounded-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Time labels */}
        <div className="flex justify-between text-[9px] text-white/30 -mt-1">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>

        {/* Controls */}
        <div className="flex items-center justify-between px-1">
          {/* Shuffle */}
          <button
            onClick={toggleShuffle}
            className={`transition-colors ${
              shuffleEnabled ? 'text-purple-400' : 'text-white/30 hover:text-white/60'
            }`}
          >
            <Shuffle size={13} />
          </button>

          {/* Prev */}
          <button
            onClick={prevSong}
            className="text-white/60 hover:text-white transition-colors"
          >
            <SkipBack size={14} />
          </button>

          {/* Play/Pause */}
          <button
            onClick={togglePlay}
            className="relative flex items-center justify-center w-8 h-8 rounded-full bg-purple-600/80 hover:bg-purple-500 transition-all shadow-[0_0_12px_rgba(147,51,234,0.5)]"
          >
            {isPlaying ? (
              <Pause size={14} className="text-white" />
            ) : (
              <Play size={14} className="text-white ml-0.5" />
            )}
          </button>

          {/* Next */}
          <button
            onClick={nextSong}
            className="text-white/60 hover:text-white transition-colors"
          >
            <SkipForward size={14} />
          </button>

          {/* Repeat */}
          <button
            onClick={toggleRepeat}
            className={`transition-colors ${
              repeatEnabled ? 'text-purple-400' : 'text-white/30 hover:text-white/60'
            }`}
          >
            <Repeat size={13} />
          </button>
        </div>
      </div>
    </div>
  );
};

function formatTime(seconds: number): string {
  const s = Math.floor(seconds);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem.toString().padStart(2, '0')}`;
}

export default MiniPlayer;
