import React, { useState } from 'react';
import { Headphones, Music, List, Zap, Info } from 'lucide-react';
import { useAppStore } from '../../store/appStore';

const moodColors: Record<string, string> = {
  romantic: 'bg-pink-500/25 text-pink-300 border-pink-500/30',
  focus: 'bg-blue-500/25 text-blue-300 border-blue-500/30',
  energetic: 'bg-orange-500/25 text-orange-300 border-orange-500/30',
  calm: 'bg-teal-500/25 text-teal-300 border-teal-500/30',
  happy: 'bg-yellow-500/25 text-yellow-300 border-yellow-500/30',
  melancholic: 'bg-indigo-500/25 text-indigo-300 border-indigo-500/30',
};

function capitalize(s: string) {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatStartTime(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export const CurrentSession: React.FC = () => {
  const { currentSession, selectedMood, currentPlaylist, playbackProfile } = useAppStore();
  const [tooltipVisible, setTooltipVisible] = useState(false);

  const mood = currentSession?.mood || selectedMood;
  const moodClass = mood
    ? (moodColors[mood] ?? 'bg-purple-500/25 text-purple-300 border-purple-500/30')
    : '';

  const handleSeeDetails = () => {
    if (currentSession) {
      alert(
        `Session ID: ${currentSession.id}\nMood: ${capitalize(currentSession.mood)}\nPlaylist: ${currentPlaylist?.name ?? '—'}\nProfile: ${currentSession.playbackProfile.name}\nVolume: ${Math.round(currentSession.playbackProfile.volume * 100)}%\nFade-in: ${currentSession.playbackProfile.fadeIn}\nSpeed: ${currentSession.playbackProfile.speed}x\nStarted: ${new Date(currentSession.startedAt).toLocaleString()}`
      );
    }
  };

  return (
    <div
      className="flex flex-col rounded-2xl border border-white/10 overflow-hidden flex-1"
      style={{ background: 'rgba(20,16,50,0.90)', backdropFilter: 'blur(18px)' }}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/[0.06]">
        <Headphones size={12} className="text-purple-400 flex-shrink-0" />
        <span className="text-xs font-semibold text-white/90 tracking-wide uppercase">
          Current Session
        </span>
      </div>

      <div className="flex flex-col flex-1 px-3 py-2.5 gap-2">
        {currentSession ? (
          <>
            {/* Info rows */}
            <div className="flex flex-col gap-1.5">
              {/* Mood row */}
              <div className="flex items-center gap-2">
                <Music size={11} className="text-purple-400/70 flex-shrink-0" />
                <span className="text-[10px] text-white/40 w-12 flex-shrink-0">Mood</span>
                <span
                  className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full border ${moodClass}`}
                >
                  {capitalize(mood)}
                </span>
              </div>

              {/* Playlist row */}
              <div className="flex items-center gap-2">
                <List size={11} className="text-purple-400/70 flex-shrink-0" />
                <span className="text-[10px] text-white/40 w-12 flex-shrink-0">Playlist</span>
                <span className="text-[10px] text-white/70 truncate">
                  {currentPlaylist?.name ?? '—'}
                </span>
              </div>

              {/* Playback row */}
              <div className="flex items-center gap-2">
                <Zap size={11} className="text-purple-400/70 flex-shrink-0" />
                <span className="text-[10px] text-white/40 w-12 flex-shrink-0">Playback</span>
                <span className="text-[10px] text-white/70 truncate">
                  {playbackProfile.name} profile
                </span>
              </div>
            </div>

            {/* Started at */}
            <div className="text-[9px] text-white/25 mt-auto">
              Started at {formatStartTime(currentSession.startedAt)}
            </div>

            {/* See Details button */}
            <button
              onClick={handleSeeDetails}
              className="mt-1 w-full flex items-center justify-center gap-1 py-1.5 rounded-lg border border-white/15 text-[10px] text-white/50 hover:text-white/80 hover:border-purple-500/40 transition-all"
            >
              <Info size={10} />
              See Details
            </button>
          </>
        ) : (
          /* No active session state */
          <div className="flex flex-col items-center justify-center flex-1 gap-2 py-3">
            <div
              className="w-9 h-9 rounded-full flex items-center justify-center"
              style={{ background: 'rgba(147,51,234,0.12)' }}
            >
              <Headphones size={16} className="text-purple-400/50" />
            </div>
            <div className="text-center">
              <p className="text-[11px] text-white/35 font-medium">No active session</p>
              <p className="text-[9px] text-white/20 mt-0.5 leading-tight">
                Select a mood &amp; playlist to start
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CurrentSession;
