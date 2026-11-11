import React, { useState } from 'react';
import { ArrowLeft, Trophy, Search, Crown } from 'lucide-react';
import { LeaderboardEntry } from '../types/game';
import { LEADERBOARD_DAILY, LEADERBOARD_WEEKLY, LEADERBOARD_ALL_TIME } from '../data/leaderboardData';
import { soundEngine } from '../utils/audio';

interface LeaderboardProps {
  onBack: () => void;
}

type TabType = 'daily' | 'weekly' | 'allTime';

export const Leaderboard: React.FC<LeaderboardProps> = ({ onBack }) => {
  const [activeTab, setActiveTab] = useState<TabType>('daily');
  const [searchQuery, setSearchQuery] = useState('');

  const getEntriesForTab = (): LeaderboardEntry[] => {
    switch (activeTab) {
      case 'daily':
        return LEADERBOARD_DAILY;
      case 'weekly':
        return LEADERBOARD_WEEKLY;
      case 'allTime':
        return LEADERBOARD_ALL_TIME;
    }
  };

  const currentList = getEntriesForTab();
  const filteredList = searchQuery.trim()
    ? currentList.filter((item) =>
        item.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.characterName.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : currentList;

  const currentPlayerEntry = currentList.find((e) => e.isCurrentPlayer);

  const getRankBadge = (rank: number) => {
    if (rank === 1) {
      return (
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#F59E0B] to-[#D97706] text-black font-gaming font-black text-sm flex items-center justify-center shadow-[0_0_15px_rgba(245,158,11,0.5)]">
          <Crown className="w-4 h-4 fill-current" />
        </div>
      );
    }
    if (rank === 2) {
      return (
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#E2E8F0] to-[#94A3B8] text-black font-gaming font-black text-sm flex items-center justify-center shadow-[0_0_10px_rgba(226,232,240,0.4)]">
          2
        </div>
      );
    }
    if (rank === 3) {
      return (
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#B45309] to-[#78350F] text-white font-gaming font-black text-sm flex items-center justify-center shadow-[0_0_10px_rgba(180,83,9,0.4)]">
          3
        </div>
      );
    }
    return (
      <div className="w-8 h-8 rounded-lg bg-[#1E293B] border border-white/10 text-[#94A3B8] font-gaming font-bold text-xs flex items-center justify-center">
        #{rank}
      </div>
    );
  };

  return (
    <div className="relative w-full h-screen overflow-hidden flex flex-col p-4 sm:p-8 bg-[#080B12] select-none text-white">
      {/* Background Cyber Glow */}
      <div className="absolute inset-0 pointer-events-none opacity-20 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-[#00E5FF]/20 via-[#080B12] to-[#080B12]" />

      {/* TOP BAR: Navigation & Title */}
      <header className="relative z-10 flex items-center justify-between pb-4 border-b border-white/10">
        <button
          onClick={() => {
            soundEngine.playClick();
            onBack();
          }}
          onMouseEnter={() => soundEngine.playHover()}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-[#111827] hover:bg-[#1E293B] border border-white/15 text-[#94A3B8] hover:text-white transition-colors cursor-pointer text-xs font-mono"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>RETURN TO MENU [ESC]</span>
        </button>

        <div className="text-center">
          <div className="text-[10px] font-mono text-[#00E5FF] tracking-widest uppercase">
            GLOBAL SURVIVAL TELEMETRY
          </div>
          <h1 className="font-gaming font-bold text-xl sm:text-2xl tracking-wider text-white">
            RUNNER <span className="text-[#00E5FF]">LEADERBOARD</span>
          </h1>
        </div>

        {/* Current player rank snapshot */}
        <div className="hidden sm:flex items-center gap-2 bg-[#111827] px-3.5 py-2 rounded-lg border border-[#00E5FF]/40 shadow-sm">
          <Trophy className="w-4 h-4 text-[#00E5FF]" />
          <span className="text-xs font-mono text-[#94A3B8]">YOUR RANK:</span>
          <span className="font-gaming text-sm font-bold text-white">
            {currentPlayerEntry ? `#${currentPlayerEntry.rank}` : '#--'}
          </span>
        </div>
      </header>

      {/* CONTROLS STRIP: Time Period Tabs & Search Input */}
      <div className="relative z-10 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-5 pb-3">
        {/* Period Tabs */}
        <div className="flex items-center p-1 bg-[#111827] border border-white/10 rounded-xl">
          <button
            onClick={() => {
              soundEngine.playClick();
              setActiveTab('daily');
            }}
            className={`px-4 py-2 rounded-lg font-gaming text-xs font-bold tracking-wider transition-all cursor-pointer ${
              activeTab === 'daily'
                ? 'bg-gradient-to-r from-[#00E5FF] to-[#00B4D8] text-[#080B12] shadow-md'
                : 'text-[#94A3B8] hover:text-white'
            }`}
          >
            DAILY CYCLES
          </button>
          <button
            onClick={() => {
              soundEngine.playClick();
              setActiveTab('weekly');
            }}
            className={`px-4 py-2 rounded-lg font-gaming text-xs font-bold tracking-wider transition-all cursor-pointer ${
              activeTab === 'weekly'
                ? 'bg-gradient-to-r from-[#00E5FF] to-[#00B4D8] text-[#080B12] shadow-md'
                : 'text-[#94A3B8] hover:text-white'
            }`}
          >
            WEEKLY SPRINT
          </button>
          <button
            onClick={() => {
              soundEngine.playClick();
              setActiveTab('allTime');
            }}
            className={`px-4 py-2 rounded-lg font-gaming text-xs font-bold tracking-wider transition-all cursor-pointer ${
              activeTab === 'allTime'
                ? 'bg-gradient-to-r from-[#00E5FF] to-[#00B4D8] text-[#080B12] shadow-md'
                : 'text-[#94A3B8] hover:text-white'
            }`}
          >
            ALL-TIME HALL OF FAME
          </button>
        </div>

        {/* Search input */}
        <div className="relative min-w-[240px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-[#94A3B8]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search runner or operator..."
            className="w-full bg-[#111827] border border-white/15 focus:border-[#00E5FF] rounded-lg pl-9 pr-3 py-2 text-xs font-mono text-white placeholder-[#64748B] outline-none transition-colors"
          />
        </div>
      </div>

      {/* LEADERBOARD TABLE */}
      <div className="relative z-10 flex-1 overflow-y-auto rounded-xl border border-white/10 bg-[#111827]/70 backdrop-blur-md mb-3">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-white/10 bg-[#080B12]/80 text-[10px] font-mono text-[#94A3B8] uppercase tracking-wider sticky top-0 z-20">
              <th className="py-3 px-4 w-16">Rank</th>
              <th className="py-3 px-4">Runner Handle</th>
              <th className="py-3 px-4 hidden md:table-cell">Operator Class</th>
              <th className="py-3 px-4 text-right">Distance</th>
              <th className="py-3 px-4 text-right">Final Score</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 text-xs font-mono">
            {filteredList.map((entry) => {
              const isPlayer = entry.isCurrentPlayer;
              return (
                <tr
                  key={`${entry.rank}-${entry.username}`}
                  className={`transition-colors hover:bg-white/5 ${
                    isPlayer ? 'bg-[#00E5FF]/10 border-l-2 border-[#00E5FF]' : ''
                  }`}
                >
                  {/* Rank Badge */}
                  <td className="py-3 px-4 whitespace-nowrap">
                    {getRankBadge(entry.rank)}
                  </td>

                  {/* Username & Avatar */}
                  <td className="py-3 px-4 whitespace-nowrap">
                    <div className="flex items-center gap-3">
                      <div className={`w-7 h-7 rounded-md flex items-center justify-center font-bold text-xs ${
                        isPlayer
                          ? 'bg-[#00E5FF] text-[#080B12]'
                          : 'bg-[#1E293B] text-white border border-white/10'
                      }`}>
                        {entry.avatarLetter}
                      </div>
                      <div>
                        <div className="font-semibold text-white flex items-center gap-1.5">
                          <span>{entry.username}</span>
                          {isPlayer && (
                            <span className="px-1.5 py-0.2 rounded bg-[#00E5FF] text-[#080B12] text-[9px] font-bold">
                              YOU
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-[#94A3B8]">
                          {entry.countryCode} {entry.dateStr ? `· ${entry.dateStr}` : ''}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Character */}
                  <td className="py-3 px-4 hidden md:table-cell whitespace-nowrap">
                    <span className="text-[#CBD5E1]">{entry.characterName}</span>
                    <span className="text-[#94A3B8] text-[10px] ml-1.5">[{entry.characterRarity}]</span>
                  </td>

                  {/* Distance */}
                  <td className="py-3 px-4 text-right whitespace-nowrap tabular-nums text-[#94A3B8]">
                    {entry.distance.toLocaleString()} m
                  </td>

                  {/* Score */}
                  <td className="py-3 px-4 text-right whitespace-nowrap tabular-nums">
                    <span className="font-gaming font-bold text-sm text-[#00E5FF]">
                      {entry.score.toLocaleString()}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {filteredList.length === 0 && (
          <div className="p-8 text-center text-[#94A3B8] font-mono text-xs">
            No runners match query "{searchQuery}".
          </div>
        )}
      </div>

      {/* FOOTER: Player Sticky Standing */}
      {currentPlayerEntry && (
        <footer className="relative z-10 bg-[#111827] border border-[#00E5FF]/40 rounded-xl p-3 flex items-center justify-between shadow-lg">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#00E5FF] text-[#080B12] font-gaming font-black text-xs flex items-center justify-center">
              #{currentPlayerEntry.rank}
            </div>
            <div>
              <div className="text-xs font-semibold text-white flex items-center gap-2">
                <span>{currentPlayerEntry.username}</span>
                <span className="text-[#94A3B8] font-mono text-[10px]">(Active Profile)</span>
              </div>
              <div className="text-[10px] font-mono text-[#94A3B8]">
                Best Distance: {currentPlayerEntry.distance.toLocaleString()} m
              </div>
            </div>
          </div>

          <div className="text-right">
            <div className="text-[10px] font-mono text-[#94A3B8] uppercase">Best Score</div>
            <div className="font-gaming font-bold text-base text-[#00E5FF] tabular-nums">
              {currentPlayerEntry.score.toLocaleString()} PTS
            </div>
          </div>
        </footer>
      )}
    </div>
  );
};
