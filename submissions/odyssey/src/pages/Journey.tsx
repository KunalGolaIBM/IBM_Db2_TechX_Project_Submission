import { useEffect, useMemo, useState } from 'react';
import { taskService } from '../services/taskService';
import { missionService } from '../services/missionService';
import { focusService } from '../services/focusService';
import type { Task, Mission, FocusSession } from '../types/database';
import ExpeditionTrail from '../components/ExpeditionTrail';
import { formatMinutes } from '../lib/expeditionTrail';

// Rank and checkpoint thresholds. These only feed the rank badge and the
// checkpoint list in the Mission Log; the map itself is built from real missions.
interface Checkpoint {
  id: string;
  label: string;
  sublabel: string;
  requiredMissions: number;
  requiredXp: number;
  status?: 'reached' | 'next' | 'ahead';
}

const CHECKPOINTS: Checkpoint[] = [
  { id: 'departure',   label: 'Departure',      sublabel: 'City of Origin',   requiredMissions: 0,  requiredXp: 0 },
  { id: 'first_orbit', label: 'First Ascent',   sublabel: 'Mountain Gate',    requiredMissions: 1,  requiredXp: 200 },
  { id: 'atmosphere',  label: 'Horizon Break',  sublabel: 'Atmosphere Edge',  requiredMissions: 3,  requiredXp: 600 },
  { id: 'orbital_ring', label: 'Deep Space',    sublabel: 'Orbital Arc',      requiredMissions: 6,  requiredXp: 1400 },
  { id: 'nebula',      label: 'Final Horizon',  sublabel: 'Stellar Passage',  requiredMissions: 10, requiredXp: 3000 },
];

export default function Journey() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [sessions, setSessions] = useState<FocusSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showLog, setShowLog] = useState(false);
  const [logTab, setLogTab] = useState<'stats' | 'activity' | 'history'>('stats');

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [t, m, s] = await Promise.all([
        taskService.getTasks(),
        missionService.getMissions(),
        focusService.getAllSessions(),
      ]);
      setTasks(t);
      setMissions(m);
      setSessions(s);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load journey data');
    } finally {
      setLoading(false);
    }
  };

  // ─── Real Progress Metrics ───────────────────────────────────────────────────

  const completedTasks = useMemo(() => tasks.filter(t => t.status === 'completed'), [tasks]);
  const completedMissions = useMemo(() => missions.filter(m => m.status === 'completed'), [missions]);
  const completedSessions = useMemo(() => sessions.filter(s => s.completed), [sessions]);
  const totalFocusMinutes = useMemo(() => sessions.reduce((a, s) => a + (s.duration_minutes ?? 0), 0), [sessions]);
  const totalXp = useMemo(
    () => completedTasks.length * 50 + completedMissions.length * 250 + totalFocusMinutes * 10,
    [completedTasks.length, completedMissions.length, totalFocusMinutes],
  );

  const rank = useMemo(() => {
    if (totalXp >= 3000) return { title: 'Odyssey Voyager', code: 'STELLAR COMMANDER' };
    if (totalXp >= 1400) return { title: 'Deep Space Navigator', code: 'ORBITAL PILOT' };
    if (totalXp >= 600)  return { title: 'Atmosphere Pilot', code: 'ASCENT SPECIALIST' };
    if (totalXp >= 200)  return { title: 'First Ascent', code: 'EXPEDITION PILOT' };
    return { title: 'Cadet', code: 'DEPARTURE PHASE' };
  }, [totalXp]);

  const checkpointsWithStatus = useMemo(() => CHECKPOINTS.map((cp, i) => {
    const reached = completedMissions.length >= cp.requiredMissions || totalXp >= cp.requiredXp;
    const isNext = !reached && (i === 0 || (completedMissions.length >= CHECKPOINTS[i - 1].requiredMissions || totalXp >= CHECKPOINTS[i - 1].requiredXp));
    return { ...cp, status: reached ? 'reached' as const : isNext ? 'next' as const : 'ahead' as const };
  }), [completedMissions.length, totalXp]);

  // ─── 14-day chart data ───────────────────────────────────────────────────────

  const dayMap: Record<string, number> = {};
  const today = new Date();
  for (let i = 13; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    dayMap[d.toDateString()] = 0;
  }
  sessions.forEach(s => {
    const d = new Date(s.started_at).toDateString();
    if (d in dayMap) dayMap[d] += s.duration_minutes ?? 0;
  });
  const days = Object.entries(dayMap);
  const maxMins = Math.max(...days.map(([, v]) => v), 1);
  const missionIndex = Object.fromEntries(missions.map(m => [m.id, m.title]));

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-8 h-8 border-2 rounded-full animate-spin"
          style={{ borderColor: 'var(--color-app-mission)', borderTopColor: 'transparent' }} />
        <p className="text-xs font-mono tracking-widest uppercase" style={{ color: 'var(--color-app-mission)' }}>
          Loading expedition chart…
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-xl mx-auto mt-16 p-6 text-center rounded-xl"
        style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-danger) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-app-danger) 20%, transparent)' }}>
        <p className="text-sm mb-3" style={{ color: 'var(--color-status-urgent)' }}>{error}</p>
        <button onClick={load} className="px-4 py-1.5 rounded text-xs cursor-pointer border-none"
          style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-danger) 20%, transparent)', color: 'var(--color-status-urgent)' }}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0" style={{ maxWidth: '1100px', margin: '0 auto' }}>

      {/* ─── Top bar: rank + controls ─────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span
              className="text-[0.6rem] font-bold tracking-[0.18em] uppercase px-2 py-0.5 rounded"
              style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-mission) 12%, transparent)', color: 'var(--color-app-mission)', border: '1px solid color-mix(in srgb, var(--color-app-mission) 25%, transparent)' }}
            >
              {rank.code}
            </span>
            <span className="text-[0.65rem] font-mono" style={{ color: 'var(--color-app-text-dim)' }}>
              {totalXp} XP
            </span>
          </div>
          <h1 className="font-display text-2xl md:text-3xl font-semibold" style={{ color: 'var(--color-app-text)' }}>
            Your Journey
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--color-app-text-muted)' }}>
            A map of how far your completed missions have taken you — not a to-do list.
          </p>
        </div>

        <button
          onClick={() => setShowLog(true)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium cursor-pointer border transition-colors"
          style={{ color: 'var(--color-app-text-muted)', backgroundColor: 'var(--color-app-surface)', borderColor: 'var(--color-app-border)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-app-text)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-app-text-muted)')}
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" />
          </svg>
          Mission Log
        </button>
      </div>

      {/* ─── Expedition milestone trail ───────────────────────────────────── */}
      <ExpeditionTrail missions={missions} sessions={sessions} />

      {/* ─── Quick Stats row beneath the map ─────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4">
        {[
          { label: 'Missions Done', value: completedMissions.length, color: 'var(--color-app-mission)' },
          { label: 'Focus Time', value: formatMinutes(totalFocusMinutes), color: 'var(--color-app-gold)' },
          { label: 'Sessions', value: completedSessions.length, color: 'var(--color-app-text)' },
          { label: 'Tasks Cleared', value: `${completedTasks.length}/${tasks.length}`, color: 'var(--color-app-success)' },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="rounded-xl p-3.5 flex flex-col gap-0.5"
            style={{ backgroundColor: 'var(--color-app-surface)', border: '1px solid var(--color-app-border)' }}
          >
            <span className="text-[0.65rem] font-semibold uppercase tracking-wider" style={{ color: 'var(--color-app-text-muted)' }}>
              {label}
            </span>
            <span className="text-xl font-bold font-mono" style={{ color }}>
              {value}
            </span>
          </div>
        ))}
      </div>

      {/* ─── Mission Log Side Drawer ───────────────────────────────────────── */}
      {showLog && (
        <div
          className="fixed inset-0 z-50 flex justify-end"
          style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-bg) 75%, transparent)', backdropFilter: 'blur(4px)' }}
          onClick={e => { if (e.target === e.currentTarget) setShowLog(false); }}
        >
          <div
            className="w-full max-w-md h-full flex flex-col overflow-hidden"
            style={{
              backgroundColor: 'var(--color-app-bg)',
              borderLeft: '1px solid var(--color-app-border)',
            }}
          >
            {/* Drawer header */}
            <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--color-app-border)' }}>
              <div>
                <h3 className="font-semibold" style={{ color: 'var(--color-app-text)' }}>Mission Log</h3>
                <p className="text-xs mt-0.5" style={{ color: 'var(--color-app-text-dim)' }}>
                  Your complete expedition record.
                </p>
              </div>
              <button
                onClick={() => setShowLog(false)}
                className="p-1.5 rounded bg-transparent border-none cursor-pointer text-lg leading-none"
                style={{ color: 'var(--color-app-text-dim)' }}
              >
                ✕
              </button>
            </div>

            {/* Tabs */}
            <div className="flex border-b px-6" style={{ borderColor: 'var(--color-app-border)' }}>
              {(['stats', 'activity', 'history'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setLogTab(tab)}
                  className="px-3 py-3 text-xs font-semibold uppercase tracking-wider bg-transparent border-none cursor-pointer capitalize"
                  style={{
                    color: logTab === tab ? 'var(--color-app-mission)' : 'var(--color-app-text-dim)',
                    borderBottom: logTab === tab ? '2px solid var(--color-app-mission)' : '2px solid transparent',
                  }}
                >
                  {tab === 'stats' ? 'Stats' : tab === 'activity' ? '14-Day' : 'Sessions'}
                </button>
              ))}
            </div>

            {/* Drawer body */}
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
              {logTab === 'stats' && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    {[
                      { label: 'Completed Missions', value: completedMissions.length, color: 'var(--color-app-mission)' },
                      { label: 'Total XP', value: totalXp, color: 'var(--color-app-gold)' },
                      { label: 'Focus Time', value: formatMinutes(totalFocusMinutes), color: 'var(--color-app-text)' },
                      { label: 'Tasks Cleared', value: completedTasks.length, color: 'var(--color-app-success)' },
                    ].map(({ label, value, color }) => (
                      <div key={label} className="p-3.5 rounded-xl"
                        style={{ backgroundColor: 'var(--color-app-surface)', border: '1px solid var(--color-app-border)' }}>
                        <p className="text-[0.65rem] font-semibold uppercase tracking-wider mb-1"
                          style={{ color: 'var(--color-app-text-muted)' }}>{label}</p>
                        <p className="text-xl font-bold font-mono" style={{ color }}>{value}</p>
                      </div>
                    ))}
                  </div>

                  {/* Checkpoint progress list */}
                  <div className="rounded-xl overflow-hidden" style={{ border: '1px solid var(--color-app-border)' }}>
                    {checkpointsWithStatus.map(cp => (
                      <div key={cp.id} className="flex items-center justify-between px-4 py-3 border-b last:border-0"
                        style={{ borderColor: 'var(--color-app-border)', opacity: cp.status === 'ahead' ? 0.5 : 1 }}>
                        <div className="flex items-center gap-3">
                          <span style={{ fontSize: '1rem' }}>
                            {cp.status === 'reached' ? '⭐' : cp.status === 'next' ? '📍' : '🔒'}
                          </span>
                          <div>
                            <p className="text-xs font-medium" style={{ color: 'var(--color-app-text)' }}>{cp.label}</p>
                            <p className="text-[0.65rem]" style={{ color: 'var(--color-app-text-dim)' }}>{cp.sublabel}</p>
                          </div>
                        </div>
                        <span className="text-[0.6rem] font-mono font-bold"
                          style={{ color: cp.status === 'reached' ? 'var(--color-app-success)' : 'var(--color-app-text-dim)' }}>
                          {cp.requiredMissions > 0 ? `${cp.requiredMissions} missions` : 'Start'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {logTab === 'activity' && (
                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-wider"
                    style={{ color: 'var(--color-app-text-muted)' }}>
                    Daily Focus — Last 14 days
                  </p>
                  <div className="flex items-end gap-1.5 h-32">
                    {days.map(([day, mins]) => {
                      const h = (mins / maxMins) * 100;
                      return (
                        <div key={day} className="flex-1 flex flex-col items-center gap-1 group"
                          title={`${new Date(day).toLocaleDateString()}: ${formatMinutes(mins)}`}>
                          <div
                            className="w-full rounded-sm transition-opacity"
                            style={{
                              height: `${Math.max(h, mins > 0 ? 10 : 3)}%`,
                              backgroundColor: mins > 0 ? 'var(--color-app-mission)' : 'var(--color-app-surface-raised)',
                              opacity: mins > 0 ? 0.9 : 0.2,
                            }}
                          />
                          <span className="text-[0.5rem] font-mono" style={{ color: 'var(--color-app-text-dim)' }}>
                            {new Date(day).getDate()}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {logTab === 'history' && (
                <div className="divide-y" style={{ borderColor: 'var(--color-app-border)' }}>
                  {sessions.length === 0 && (
                    <p className="text-sm py-6 text-center" style={{ color: 'var(--color-app-text-dim)' }}>
                      No sessions recorded yet.
                    </p>
                  )}
                  {sessions.slice(0, 20).map(s => (
                    <div key={s.id} className="py-3 flex items-center justify-between gap-4">
                      <div className="min-w-0">
                        <p className="text-xs font-medium truncate" style={{ color: 'var(--color-app-text)' }}>
                          {s.mission_id ? (missionIndex[s.mission_id] ?? 'Mission') : 'Focus Session'}
                        </p>
                        <p className="text-[0.65rem] font-mono" style={{ color: 'var(--color-app-text-dim)' }}>
                          {new Date(s.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 flex-shrink-0">
                        <span className="text-xs font-mono font-bold" style={{ color: 'var(--color-app-text-muted)' }}>
                          {s.duration_minutes ? formatMinutes(s.duration_minutes) : '—'}
                        </span>
                        <span
                          className="text-[0.6rem] font-bold px-1.5 py-0.5 rounded uppercase"
                          style={s.completed
                            ? { backgroundColor: 'color-mix(in srgb, var(--color-app-success) 10%, transparent)', color: 'var(--color-app-success)' }
                            : { backgroundColor: 'color-mix(in srgb, var(--color-status-low) 10%, transparent)', color: 'var(--color-status-low)' }
                          }
                        >
                          {s.completed ? 'done' : 'partial'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
