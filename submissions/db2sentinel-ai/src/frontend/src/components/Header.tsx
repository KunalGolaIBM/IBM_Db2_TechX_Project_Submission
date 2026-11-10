import React, { useState } from 'react';
import { Play, Sparkles, RotateCcw, Database } from 'lucide-react';
import { SentinelApi } from '../services/api';

interface Props {
  db2Connected?: boolean;
  isDemoMode?: boolean;
  onRefresh?: () => void;
}

export const Header: React.FC<Props> = ({ db2Connected = true, isDemoMode = true, onRefresh }) => {
  const [loading, setLoading] = useState(false);

  const handleGenerateDemo = async () => {
    setLoading(true);
    try {
      await SentinelApi.generateDemoEvents();
      await SentinelApi.runDemoDetection();
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    setLoading(true);
    try {
      await SentinelApi.resetDemo();
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <header className="h-16 border-b border-[#1E3A5F] bg-[#0D182E]/90 backdrop-blur px-8 flex items-center justify-between sticky top-0 z-40">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-[#132238] border border-[#1E3A5F]">
          <Database className="w-4 h-4 text-cyan-400" />
          <span className="text-xs text-slate-300 font-medium">IBM Db2 Database:</span>
          {db2Connected ? (
            <span className="inline-flex items-center gap-1.5 text-xs text-emerald-400 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              {isDemoMode ? 'Connected (Demo Store)' : 'Connected (Live Db2)'}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 text-xs text-rose-400 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-400"></span>
              Offline
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleGenerateDemo}
          disabled={loading}
          className="flex items-center gap-2 px-3.5 py-1.5 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-cyan-500/10 transition-all disabled:opacity-50"
        >
          <Sparkles className="w-3.5 h-3.5" />
          {loading ? 'Simulating...' : 'Generate Security Demo'}
        </button>

        <button
          onClick={handleReset}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[#132238] hover:bg-[#1C2E4A] text-slate-300 hover:text-white rounded-lg text-xs font-medium border border-[#1E3A5F] transition-all"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Reset Demo
        </button>
      </div>
    </header>
  );
};
