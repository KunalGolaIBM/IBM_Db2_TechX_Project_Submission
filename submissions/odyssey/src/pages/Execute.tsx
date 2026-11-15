import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { missionService } from '../services/missionService';
import { taskService } from '../services/taskService';
import { formatDuration } from '../components/FocusTimer';
import { useMissionTimer } from '../hooks/useMissionTimer';
import { safeMissionDuration } from '../lib/missionDuration';
import type { Mission, Task } from '../types/database';

// XP values mirror Journey.tsx — single source of truth concept
const XP_PER_MISSION = 250;
const XP_PER_TASK    = 50;

export default function Execute() {
  const location = useLocation();
  const navigate  = useNavigate();

  const initialMission = (location.state as { mission?: Mission; linkedTask?: Task } | null)?.mission ?? null;
  const linkedTask      = (location.state as { mission?: Mission; linkedTask?: Task } | null)?.linkedTask ?? null;

  const [mission, setMission] = useState<Mission | null>(initialMission);

  useEffect(() => {
    if (initialMission) return;
    (async () => {
      try {
        const missions = await missionService.getMissions();
        const resumable = missions.find(item => item.status === 'active' || item.status === 'paused');
        if (resumable) setMission(resumable);
      } catch (error) {
        console.error('Failed to restore active mission:', error);
      }
    })();
  }, [initialMission]);

  const timer = useMissionTimer(mission, updatedMission => setMission(updatedMission));
  const { elapsed, running, ending } = timer;

  // Next recommendation state for post-completion flow
  const [nextRecommendation, setNextRecommendation] = useState<{
    type: 'mission' | 'task';
    mission?: Mission;
    task?: Task;
  } | null>(null);
  const [loadedNext, setLoadedNext] = useState(false);

  const plannedSeconds = safeMissionDuration(mission?.planned_minutes) * 60;
  const progress       = Math.min(elapsed / plannedSeconds, 1);
  const remaining      = Math.max(0, plannedSeconds - elapsed);

  // ── Helper to find next move after completion ──────────────────────────────────
  const loadNextMove = async (completedMissionId: string, completedTaskId?: string) => {
    try {
      const [allTasks, allMissions] = await Promise.all([
        taskService.getTasks(),
        missionService.getMissions(),
      ]);

      const otherActiveMissions = allMissions.filter(
        m => m.id !== completedMissionId && (m.status === 'planned' || m.status === 'active' || m.status === 'paused')
      );

      if (otherActiveMissions.length > 0) {
        const nextM = otherActiveMissions.find(m => m.status === 'active' || m.status === 'paused') || otherActiveMissions[0];
        setNextRecommendation({ type: 'mission', mission: nextM });
        setLoadedNext(true);
        return;
      }

      const activeTasks = allTasks.filter(
        t => t.id !== completedTaskId && t.status !== 'completed' && t.status !== 'archived'
      );

      if (activeTasks.length > 0) {
        const priorityOrder: Record<string, number> = { urgent: 4, high: 3, medium: 2, low: 1 };
        const sorted = [...activeTasks].sort((a, b) => {
          const pA = priorityOrder[a.priority] ?? 2;
          const pB = priorityOrder[b.priority] ?? 2;
          if (pB !== pA) return pB - pA;
          if (a.deadline && b.deadline) return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
          if (a.deadline) return -1;
          if (b.deadline) return 1;
          return 0;
        });
        setNextRecommendation({ type: 'task', task: sorted[0] });
        setLoadedNext(true);
        return;
      }

      setNextRecommendation(null);
      setLoadedNext(true);
    } catch (err) {
      console.warn('Failed to load next recommendation:', err);
      setLoadedNext(true);
    }
  };

  // ── Timer actions ──────────────────────────────────────────────────────────────
  const handleStart = async () => { try { await timer.start(); } catch (e) { console.error(e); } };
  const handlePause = async () => { try { await timer.pause(); } catch (e) { console.error(e); } };
  const handleResume = async () => { try { await timer.resume(); } catch (e) { console.error(e); } };

  const handleComplete = async () => {
    if (!mission || ending) return;
    try {
      await timer.complete();
      const m = await missionService.getMission(mission.id);
      if (linkedTask || m.task_id) {
        try {
          await taskService.completeTask((linkedTask?.id || m.task_id)!);
        } catch (taskErr) {
          console.warn('Could not mark linked task completed:', taskErr);
        }
      }
      await loadNextMove(m.id, linkedTask?.id || m.task_id || undefined);
    } catch (e) { console.error(e); }
  };

  // ── Derived display helpers ────────────────────────────────────────────────────

  const isCompleted  = mission?.status === 'completed';
  const isPaused     = mission?.status === 'paused';
  const isAbandoned  = mission?.status === 'abandoned';
  const isFinished   = isCompleted || isAbandoned;

  const xpReward = XP_PER_MISSION + (linkedTask ? XP_PER_TASK : 0);

  // circumference for SVG ring (r=88)
  const RING_R = 88;
  const CIRC   = 2 * Math.PI * RING_R;

  // ── Empty state ────────────────────────────────────────────────────────────────

  if (!mission) {
    return (
      <div className="max-w-md mx-auto mt-24 text-center px-4">
        <div
          className="rounded-2xl p-10 app-focus-surface"
          style={{
            border: '1px solid rgba(49,75,115,0.4)',
          }}
        >
          <div
            className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-5"
            style={{ background: 'color-mix(in srgb, var(--color-app-mission) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--color-app-mission) 20%, transparent)' }}
          >
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
              style={{ color: 'var(--color-app-mission)' }}>
              <path strokeLinecap="round" strokeLinejoin="round"
                d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
            </svg>
          </div>
          <h2 className="font-display text-xl mb-2" style={{ color: 'var(--color-app-text)' }}>
            No mission selected
          </h2>
          <p className="text-sm mb-7" style={{ color: 'var(--color-app-text-muted)' }}>
            Execute starts from a plan. Capture what you want to do next, or pick a mission you already planned.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              to="/home"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium"
              style={{ backgroundColor: 'var(--color-app-mission)', color: '#fff' }}
            >
              Capture your next move →
            </Link>
            <Link
              to="/mission"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium"
              style={{ color: 'var(--color-app-mission)', border: '1px solid rgba(184,122,85,0.35)' }}
            >
              Select a mission
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-0 sm:px-4">

      {/* ── Flow breadcrumb ── */}
      <nav className="flex items-center gap-2 mb-6 text-xs px-4 sm:px-0" style={{ color: 'var(--color-app-text-dim)' }}>
        <Link to="/home" className="hover:underline"
          style={{ color: 'var(--color-app-text-dim)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-app-text-muted)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-app-text-dim)')}
        >Step 1 — Capture</Link>
        <span aria-hidden="true" style={{ opacity: 0.35 }}>›</span>
        <Link to="/mission" className="hover:underline"
          style={{ color: 'var(--color-app-text-dim)' }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--color-app-text-muted)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--color-app-text-dim)')}
        >Step 2 — Plan</Link>
        <span aria-hidden="true" style={{ opacity: 0.35 }}>›</span>
        <span style={{ color: 'var(--color-app-mission)' }}>Step 3 — Execute</span>
      </nav>

      {/* ── Mission Control Console ── */}
      <div
        className="rounded-2xl overflow-hidden app-console"
        style={{
          border: running
            ? '1px solid color-mix(in srgb, var(--color-ody-gold) 40%, transparent)'
            : isCompleted
            ? '1px solid color-mix(in srgb, var(--color-app-success) 40%, transparent)'
            : '1px solid rgba(49,75,115,0.5)',
          boxShadow: running
            ? '0 0 0 1px color-mix(in srgb, var(--color-ody-gold) 8%, transparent), 0 16px 60px -12px color-mix(in srgb, var(--color-ody-gold) 20%, transparent)'
            : '0 16px 60px -12px rgba(3,6,13,0.9)',
          transition: 'border-color 0.6s ease, box-shadow 0.6s ease',
        }}
      >

        {/* ── Console header ── */}
        <div
          className="flex items-center justify-between px-5 py-3.5 border-b"
          style={{ borderColor: 'rgba(49,75,115,0.25)' }}
        >
          <div className="flex items-center gap-2.5">
            {/* Status beacon */}
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{
                backgroundColor: running ? 'var(--color-app-success)' : isCompleted ? 'var(--color-app-success)' : isPaused ? 'var(--color-app-gold)' : 'var(--color-app-mission)',
                boxShadow: running ? '0 0 8px color-mix(in srgb, var(--color-app-success) 80%, transparent)' : isCompleted ? '0 0 8px color-mix(in srgb, var(--color-app-success) 60%, transparent)' : 'none',
                animation: running ? 'pulse 2s infinite' : 'none',
              }}
            />
            <span
              className="text-[0.6rem] font-mono font-bold tracking-[0.2em] uppercase"
              style={{ color: running ? 'var(--color-app-success)' : isCompleted ? 'var(--color-app-success)' : isPaused ? 'var(--color-app-gold)' : 'var(--color-app-mission)' }}
            >
              {running ? 'MISSION IN PROGRESS' : isCompleted ? 'MISSION COMPLETE' : isPaused ? 'SYSTEMS PAUSED' : isAbandoned ? 'MISSION ABORTED' : 'READY FOR LAUNCH'}
            </span>
          </div>
          <span
            className="text-[0.6rem] font-mono"
            style={{ color: 'var(--color-app-text-dim)' }}
          >
            {Math.round(progress * 100)}% elapsed
          </span>
        </div>

        {/* ── Mission identity ── */}
        <div className="px-5 pt-5 pb-4">
          {linkedTask && (
            <p className="text-[0.65rem] font-mono mb-2" style={{ color: 'var(--color-app-text-dim)' }}>
              ↳ linked task: {linkedTask.title}
            </p>
          )}
          <h1
            className="font-display leading-tight mb-2"
            style={{ color: 'var(--color-app-text)', fontSize: 'clamp(1.25rem, 2.5vw, 1.75rem)' }}
          >
            {mission.title}
          </h1>
          {mission.objective && (
            <p className="text-sm leading-relaxed mb-3" style={{ color: 'var(--color-app-text-muted)' }}>
              {mission.objective}
            </p>
          )}
          {mission.next_action && (
            <div
              className="flex items-start gap-2.5 rounded-lg px-3.5 py-3"
              style={{
                background: 'color-mix(in srgb, var(--color-app-mission) 7%, transparent)',
                border: '1px solid color-mix(in srgb, var(--color-app-mission) 18%, transparent)',
              }}
            >
              <svg className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24"
                style={{ color: 'var(--color-app-mission)' }}>
                <path d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347c-.75.412-1.667-.13-1.667-.986V5.653z" />
              </svg>
              <div>
                <p className="text-[0.6rem] font-bold uppercase tracking-wider mb-0.5"
                  style={{ color: 'var(--color-app-mission)' }}>
                  Now doing
                </p>
                <p className="text-sm" style={{ color: 'var(--color-app-text)' }}>
                  {mission.next_action}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* ── MISSION COMPLETE celebration banner ── */}
        {isCompleted && (
          <div
            className="mx-5 mb-4 rounded-xl px-5 py-4 text-center"
            style={{
              background: 'linear-gradient(135deg, color-mix(in srgb, var(--color-app-success) 12%, transparent) 0%, color-mix(in srgb, var(--color-app-success) 6%, transparent) 100%)',
              border: '1px solid color-mix(in srgb, var(--color-app-success) 30%, transparent)',
            }}
          >
            <p className="text-base font-semibold mb-0.5" style={{ color: 'var(--color-app-success)' }}>
              ✓ Mission Accomplished
            </p>
            <p className="text-xs" style={{ color: 'var(--color-app-text-muted)' }}>
              +{xpReward} XP earned — your progress has been logged to your Journey.
            </p>
          </div>
        )}

        {/* ── Central Timer & Trajectory Indicator ── */}
        {!isFinished && (
          <div className="px-5 pb-5">
            <div
              className="rounded-xl px-5 py-6 flex flex-col items-center gap-5 app-panel-inset"
              style={{
                border: '1px solid rgba(49,75,115,0.3)',
              }}
            >

              {/* Large Countdown Ring */}
              <div className="relative" style={{ width: 200, height: 200 }}>
                <svg width="200" height="200" viewBox="0 0 200 200" className="-rotate-90">
                  <defs>
                    <linearGradient id="mcTimerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                      <stop offset="0%" style={{ stopColor: isCompleted ? 'var(--color-app-success)' : 'var(--color-app-mission)' }} />
                      <stop offset="100%" style={{ stopColor: isCompleted ? 'var(--color-app-success)' : 'var(--color-ody-gold)' }} />
                    </linearGradient>
                  </defs>

                  {/* Track */}
                  <circle cx="100" cy="100" r={RING_R}
                    fill="none"
                    stroke="rgba(30,60,100,0.3)"
                    strokeWidth="7"
                  />

                  {/* Progress arc */}
                  <circle cx="100" cy="100" r={RING_R}
                    fill="none"
                    stroke="url(#mcTimerGrad)"
                    strokeWidth="7"
                    strokeLinecap="round"
                    strokeDasharray={CIRC}
                    strokeDashoffset={CIRC * (1 - progress)}
                    style={{
                      transition: 'stroke-dashoffset 0.8s ease',
                      filter: running ? 'drop-shadow(0 0 8px color-mix(in srgb, var(--color-ody-gold) 60%, transparent))' : 'none',
                    }}
                  />

                  {/* Marker dot at progress tip */}
                  {progress > 0.02 && (
                    <circle
                      cx={100 + RING_R * Math.cos(2 * Math.PI * progress - Math.PI / 2)}
                      cy={100 + RING_R * Math.sin(2 * Math.PI * progress - Math.PI / 2)}
                      r="5"
                      style={{ fill: running ? 'var(--color-ody-gold)' : 'var(--color-app-mission)', filter: running ? 'drop-shadow(0 0 6px color-mix(in srgb, var(--color-ody-gold) 90%, transparent))' : 'none' }}
                    />
                  )}
                </svg>

                {/* Center readout */}
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span
                    className="font-mono font-bold tabular-nums"
                    style={{
                      fontSize: '2.4rem',
                      letterSpacing: '0.04em',
                      color: running ? 'var(--color-app-gold)' : 'var(--color-app-text)',
                      transition: 'color 0.4s ease',
                    }}
                  >
                    {formatDuration(elapsed)}
                  </span>
                  <span
                    className="font-mono mt-0.5"
                    style={{ fontSize: '0.7rem', color: 'var(--color-app-text-dim)' }}
                  >
                    {formatDuration(plannedSeconds)}
                  </span>
                </div>
              </div>

              {/* Horizontal mission trajectory bar */}
              <div className="w-full">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-[0.6rem] font-mono uppercase tracking-wider"
                    style={{ color: 'var(--color-app-text-dim)' }}>
                    Mission Trajectory
                  </span>
                  <span className="text-[0.6rem] font-mono"
                    style={{ color: 'var(--color-app-text-dim)' }}>
                    {formatDuration(remaining)} remaining
                  </span>
                </div>
                <div
                  className="relative h-1.5 rounded-full overflow-hidden"
                  style={{ backgroundColor: 'rgba(30,60,100,0.4)' }}
                >
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${Math.round(progress * 100)}%`,
                      background: 'linear-gradient(90deg, var(--color-app-mission) 0%, var(--color-ody-gold) 100%)',
                      boxShadow: running ? '0 0 8px color-mix(in srgb, var(--color-ody-gold) 50%, transparent)' : 'none',
                      transition: 'width 0.8s ease',
                    }}
                  />
                  {/* Moving marker */}
                  {progress > 0 && progress < 1 && (
                    <div
                      className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2"
                      style={{
                        left: `calc(${Math.round(progress * 100)}% - 6px)`,
                        backgroundColor: 'var(--color-ody-gold)',
                        borderColor: '#050817',
                        boxShadow: running ? '0 0 6px color-mix(in srgb, var(--color-ody-gold) 80%, transparent)' : 'none',
                        transition: 'left 0.8s ease',
                      }}
                    />
                  )}
                </div>
                <div className="flex justify-between mt-1.5">
                  <span className="text-[0.55rem] font-mono" style={{ color: 'var(--color-app-text-dim)' }}>
                    Launch
                  </span>
                  <span className="text-[0.55rem] font-mono" style={{ color: 'var(--color-app-text-dim)' }}>
                    Target
                  </span>
                </div>
              </div>

              {/* Telemetry row: elapsed + XP reward */}
              <div className="w-full flex items-center justify-between pt-1 border-t"
                style={{ borderColor: 'rgba(49,75,115,0.2)' }}>
                <div className="flex items-center gap-1.5">
                  <span className="text-[0.6rem] font-mono uppercase tracking-wider"
                    style={{ color: 'var(--color-app-text-dim)' }}>
                    Elapsed
                  </span>
                  <span className="text-xs font-mono font-bold"
                    style={{ color: 'var(--color-app-text-muted)' }}>
                    {formatDuration(elapsed)}
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[0.6rem] font-mono uppercase tracking-wider"
                    style={{ color: 'var(--color-app-text-dim)' }}>
                    Reward
                  </span>
                  <span className="text-xs font-mono font-bold"
                    style={{ color: 'var(--color-app-gold)' }}>
                    +{xpReward} XP
                  </span>
                </div>
              </div>

              {/* Controls */}
              <div className="flex items-center gap-3 w-full">
                {!running && !isPaused ? (
                  <button
                    onClick={handleStart}
                    className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold cursor-pointer border-none transition-all active:scale-95"
                    style={{
                      background: 'linear-gradient(135deg, var(--color-app-mission) 0%, var(--color-app-gold) 100%)',
                      color: '#050817',
                      boxShadow: '0 4px 16px color-mix(in srgb, var(--color-app-mission) 35%, transparent)',
                    }}
                  >
                    <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347c-.75.412-1.667-.13-1.667-.986V5.653z" />
                    </svg>
                    Begin Focus Session
                  </button>
                ) : isPaused ? (
                  <>
                    <button
                      onClick={handleResume}
                      className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold cursor-pointer border-none transition-all active:scale-95"
                      style={{
                        background: 'linear-gradient(135deg, var(--color-app-mission) 0%, var(--color-app-gold) 100%)',
                        color: '#050817',
                      }}
                    >
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                        <path d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 010 1.972l-11.54 6.347c-.75.412-1.667-.13-1.667-.986V5.653z" />
                      </svg>
                      Resume
                    </button>
                    <button
                      onClick={handleComplete}
                      disabled={ending}
                      className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-medium cursor-pointer border-none transition-all disabled:opacity-50"
                      style={{
                        backgroundColor: 'color-mix(in srgb, var(--color-app-success) 15%, transparent)',
                        color: 'var(--color-app-success)',
                        border: '1px solid color-mix(in srgb, var(--color-app-success) 30%, transparent)',
                      }}
                    >
                      {ending ? 'Logging…' : 'Complete'}
                    </button>
                  </>
                ) : running ? (
                  <>
                    <button
                      onClick={handlePause}
                      className="flex items-center justify-center gap-2 px-5 py-3 rounded-xl text-sm font-medium cursor-pointer border-none transition-all"
                      style={{
                        backgroundColor: 'color-mix(in srgb, var(--color-app-gold) 10%, transparent)',
                        color: 'var(--color-app-gold)',
                        border: '1px solid color-mix(in srgb, var(--color-app-gold) 25%, transparent)',
                      }}
                    >
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                        <path fillRule="evenodd" d="M6.75 5.25a.75.75 0 01.75-.75H9a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H7.5a.75.75 0 01-.75-.75V5.25zm7.5 0A.75.75 0 0115 4.5h1.5a.75.75 0 01.75.75v13.5a.75.75 0 01-.75.75H15a.75.75 0 01-.75-.75V5.25z" clipRule="evenodd" />
                      </svg>
                      Pause
                    </button>
                    <button
                      onClick={handleComplete}
                      disabled={ending}
                      className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-semibold cursor-pointer border-none transition-all disabled:opacity-50 active:scale-95"
                      style={{
                        backgroundColor: 'color-mix(in srgb, var(--color-app-success) 15%, transparent)',
                        color: 'var(--color-app-success)',
                        border: '1px solid color-mix(in srgb, var(--color-app-success) 30%, transparent)',
                      }}
                    >
                      {ending ? 'Logging…' : '✓ Complete Mission'}
                    </button>
                  </>
                ) : null}
              </div>
            </div>
          </div>
        )}

        {/* ── Post-completion Next Move Recommendation ── */}
        {isCompleted && (
          <div
            className="mx-5 mb-5 rounded-xl p-5 app-spotlight"
            style={{
              border: '1px solid color-mix(in srgb, var(--color-app-mission) 40%, transparent)',
              boxShadow: '0 8px 32px -4px rgba(3,6,13,0.6)',
            }}
          >
            {nextRecommendation ? (
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <span
                    className="text-[0.6rem] font-bold tracking-[0.16em] uppercase px-2 py-0.5 rounded"
                    style={{
                      backgroundColor: 'color-mix(in srgb, var(--color-app-mission) 15%, transparent)',
                      color: 'var(--color-app-mission)',
                      border: '1px solid color-mix(in srgb, var(--color-app-mission) 30%, transparent)',
                    }}
                  >
                    YOUR NEXT MOVE
                  </span>
                  <span className="text-xs" style={{ color: 'var(--color-app-text-dim)' }}>
                    {nextRecommendation.type === 'mission' ? 'Next planned mission' : 'Highest-priority remaining task'}
                  </span>
                </div>

                <h3 className="font-display text-lg font-semibold mb-1" style={{ color: 'var(--color-app-text)' }}>
                  {nextRecommendation.type === 'mission'
                    ? nextRecommendation.mission?.title
                    : nextRecommendation.task?.title}
                </h3>

                {nextRecommendation.type === 'mission' && nextRecommendation.mission?.objective && (
                  <p className="text-xs mb-3 line-clamp-2" style={{ color: 'var(--color-app-text-muted)' }}>
                    {nextRecommendation.mission.objective}
                  </p>
                )}

                {nextRecommendation.type === 'task' && nextRecommendation.task?.description && (
                  <p className="text-xs mb-3 line-clamp-2" style={{ color: 'var(--color-app-text-muted)' }}>
                    {nextRecommendation.task.description}
                  </p>
                )}

                <div className="flex flex-wrap items-center justify-between gap-3 mt-4 pt-3 border-t"
                  style={{ borderColor: 'rgba(49,75,115,0.25)' }}>
                  <div className="flex gap-2">
                    <button
                      onClick={() => navigate('/journey')}
                      className="px-3.5 py-2 rounded-lg text-xs font-medium cursor-pointer border transition-all"
                      style={{ color: 'var(--color-app-text-muted)', backgroundColor: 'transparent', borderColor: 'var(--color-app-border)' }}
                    >
                      View Journey
                    </button>
                    <button
                      onClick={() => navigate('/mission')}
                      className="px-3.5 py-2 rounded-lg text-xs font-medium cursor-pointer border transition-all"
                      style={{ color: 'var(--color-app-text-muted)', backgroundColor: 'transparent', borderColor: 'var(--color-app-border)' }}
                    >
                      All Missions
                    </button>
                  </div>

                  <button
                    onClick={() => {
                      if (nextRecommendation.type === 'mission' && nextRecommendation.mission) {
                        navigate('/execute', { state: { mission: nextRecommendation.mission } });
                        setMission(nextRecommendation.mission);
                        setLoadedNext(false);
                      } else if (nextRecommendation.type === 'task' && nextRecommendation.task) {
                        navigate('/mission', { state: { prefillTask: nextRecommendation.task } });
                      }
                    }}
                    className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-semibold cursor-pointer border-none transition-all"
                    style={{
                      background: 'linear-gradient(135deg, var(--color-app-mission) 0%, var(--color-app-gold) 100%)',
                      color: '#050817',
                      boxShadow: '0 4px 14px color-mix(in srgb, var(--color-app-mission) 30%, transparent)',
                    }}
                  >
                    <span>Start Next Mission</span>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                  </button>
                </div>
              </div>
            ) : loadedNext ? (
              <div className="text-center py-2">
                <p className="text-sm font-medium mb-1" style={{ color: 'var(--color-app-text)' }}>
                  🎉 All caught up! All current tasks and missions completed.
                </p>
                <p className="text-xs mb-4" style={{ color: 'var(--color-app-text-muted)' }}>
                  You've cleared all commitments. View your updated progress on Journey or capture what's next.
                </p>
                <div className="flex justify-center gap-3">
                  <button
                    onClick={() => navigate('/home')}
                    className="px-4 py-2 rounded-lg text-xs font-medium cursor-pointer border transition-all"
                    style={{ color: 'var(--color-app-text-muted)', backgroundColor: 'transparent', borderColor: 'var(--color-app-border)' }}
                  >
                    Capture New Thoughts
                  </button>
                  <button
                    onClick={() => navigate('/journey')}
                    className="px-5 py-2 rounded-lg text-xs font-semibold cursor-pointer border-none transition-all"
                    style={{
                      background: 'linear-gradient(135deg, var(--color-app-mission) 0%, var(--color-app-gold) 100%)',
                      color: '#050817',
                    }}
                  >
                    View My Journey →
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-xs text-center py-2" style={{ color: 'var(--color-app-text-dim)' }}>
                Finding your next move…
              </p>
            )}
          </div>
        )}

        {/* ── Post-abandonment navigation ── */}
        {isAbandoned && (
          <div
            className="mx-5 mb-5 rounded-xl px-5 py-4 flex flex-col sm:flex-row items-center justify-between gap-4"
            style={{
              background: 'color-mix(in srgb, var(--color-app-danger) 6%, transparent)',
              border: '1px solid color-mix(in srgb, var(--color-app-danger) 20%, transparent)',
            }}
          >
            <p className="text-sm" style={{ color: 'var(--color-app-text-muted)' }}>
              Mission aborted. Return to Plan to regroup and choose your next focus.
            </p>
            <button
              onClick={() => navigate('/mission')}
              className="px-4 py-2 rounded-lg text-sm font-medium cursor-pointer border transition-all"
              style={{ color: 'var(--color-app-text-muted)', backgroundColor: 'transparent', borderColor: 'var(--color-app-border)' }}
            >
              Back to Plan
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
