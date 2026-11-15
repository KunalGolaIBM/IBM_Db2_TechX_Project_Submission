import { useEffect, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { taskService } from '../services/taskService';
import { missionService } from '../services/missionService';
import { focusService } from '../services/focusService';
import DataPortabilitySection from '../components/DataPortabilitySection';
import type { Task, Mission, FocusSession } from '../types/database';

// ─── Achievement definitions ─────────────────────────────────────────────────

interface Achievement {
  id: string;
  title: string;
  description: string;
  icon: string;
  unlocked: boolean;
  progress?: number;     // 0–100
  progressLabel?: string;
}

function buildAchievements(
  tasks: Task[],
  missions: Mission[],
  sessions: FocusSession[],
): Achievement[] {
  const completedTasks = tasks.filter((t) => t.status === 'completed').length;
  const completedMissions = missions.filter((m) => m.status === 'completed').length;
  const completedSessions = sessions.filter((s) => s.completed).length;
  const totalFocusMinutes = sessions.reduce((a, s) => a + (s.duration_minutes ?? 0), 0);

  // Unique days with a completed session
  const activeDays = new Set(
    sessions
      .filter((s) => s.completed)
      .map((s) => new Date(s.started_at).toDateString())
  ).size;

  const milestones: Array<{ id: string; title: string; description: string; icon: string; threshold: number; value: number }> = [
    { id: 'first_task', title: 'First Step', description: 'Complete your first task', icon: '✓', threshold: 1, value: completedTasks },
    { id: 'task_10', title: 'Task Master', description: 'Complete 10 tasks', icon: '📋', threshold: 10, value: completedTasks },
    { id: 'task_25', title: 'Productive', description: 'Complete 25 tasks', icon: '⚡', threshold: 25, value: completedTasks },
    { id: 'first_mission', title: 'Initiated', description: 'Complete your first mission', icon: '🚀', threshold: 1, value: completedMissions },
    { id: 'mission_5', title: 'Relentless', description: 'Complete 5 missions', icon: '🎯', threshold: 5, value: completedMissions },
    { id: 'mission_20', title: 'Commander', description: 'Complete 20 missions', icon: '🏅', threshold: 20, value: completedMissions },
    { id: 'focus_1', title: 'First Focus', description: 'Log your first focus session', icon: '⏱', threshold: 1, value: completedSessions },
    { id: 'focus_10', title: 'Deep Work', description: 'Log 10 focus sessions', icon: '🧠', threshold: 10, value: completedSessions },
    { id: 'focus_50', title: 'Flow State', description: 'Log 50 focus sessions', icon: '🌊', threshold: 50, value: completedSessions },
    { id: 'time_60', title: 'Hour Logged', description: 'Accumulate 1 hour of focused work', icon: '⌛', threshold: 60, value: totalFocusMinutes },
    { id: 'time_600', title: 'Ten Hours', description: 'Accumulate 10 hours of focused work', icon: '🕐', threshold: 600, value: totalFocusMinutes },
    { id: 'streak_3', title: 'Consistent', description: 'Focus on 3 different days', icon: '🔥', threshold: 3, value: activeDays },
    { id: 'streak_7', title: 'Dedicated', description: 'Focus on 7 different days', icon: '💎', threshold: 7, value: activeDays },
    { id: 'streak_30', title: 'Obsessed', description: 'Focus on 30 different days', icon: '👑', threshold: 30, value: activeDays },
  ];

  return milestones.map(({ id, title, description, icon, threshold, value }) => ({
    id,
    title,
    description,
    icon,
    unlocked: value >= threshold,
    progress: Math.min(Math.round((value / threshold) * 100), 100),
    progressLabel: `${Math.min(value, threshold)} / ${threshold}`,
  }));
}

// ─── Components ───────────────────────────────────────────────────────────────

function AchievementBadge({ achievement }: { achievement: Achievement }) {
  return (
    <div
      className={`rounded-xl p-4 flex flex-col items-center text-center gap-2 transition-all${achievement.unlocked ? '' : ' app-dimmed'}`}
      style={{
        backgroundColor: achievement.unlocked ? 'var(--color-app-surface)' : 'var(--color-app-bg)',
        border: `1px solid ${achievement.unlocked ? 'color-mix(in srgb, var(--color-app-gold) 35%, transparent)' : 'var(--color-app-border-subtle)'}`,
      }}
    >
      <span
        className="text-2xl w-12 h-12 flex items-center justify-center rounded-full"
        style={{
          backgroundColor: achievement.unlocked ? 'color-mix(in srgb, var(--color-app-gold) 12%, transparent)' : 'var(--color-app-surface-raised)',
          filter: achievement.unlocked ? 'none' : 'grayscale(1)',
        }}
      >
        {achievement.icon}
      </span>
      <div>
        <p className="text-sm font-semibold" style={{ color: achievement.unlocked ? 'var(--color-app-gold)' : 'var(--color-app-text-dim)' }}>
          {achievement.title}
        </p>
        <p className="text-xs mt-0.5" style={{ color: 'var(--color-app-text-dim)' }}>
          {achievement.description}
        </p>
      </div>
      {!achievement.unlocked && achievement.progress !== undefined && (
        <div className="w-full mt-1">
          <div className="w-full h-1 rounded-full overflow-hidden" style={{ backgroundColor: 'var(--color-app-surface-overlay)' }}>
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${achievement.progress}%`,
                backgroundColor: 'var(--color-app-text-dim)',
              }}
            />
          </div>
          <p className="text-[0.55rem] mt-1" style={{ color: 'var(--color-app-text-dim)' }}>
            {achievement.progressLabel}
          </p>
        </div>
      )}
      {achievement.unlocked && (
        <span
          className="text-[0.6rem] font-bold uppercase tracking-wider px-2 py-0.5 rounded"
          style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-gold) 12%, transparent)', color: 'var(--color-app-gold)', border: '1px solid color-mix(in srgb, var(--color-app-gold) 25%, transparent)' }}
        >
          Unlocked
        </span>
      )}
    </div>
  );
}

// ─── Main Odyssey page ────────────────────────────────────────────────────────

export default function Odyssey() {
  const { user } = useAuth();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [missions, setMissions] = useState<Mission[]>([]);
  const [sessions, setSessions] = useState<FocusSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { load(); }, []);

  const load = async (showLoadingSpinner = true) => {
    if (showLoadingSpinner) {
      setLoading(true);
    }
    setError(null);
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
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      if (showLoadingSpinner) {
        setLoading(false);
      }
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh]">
        <div className="w-8 h-8 border-2 rounded-full animate-spin mb-3"
          style={{ borderColor: 'var(--color-app-gold)', borderTopColor: 'transparent' }} />
        <span className="text-sm" style={{ color: 'var(--color-app-text-muted)' }}>Loading passport...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-xl mx-auto mt-16 rounded-xl p-6 text-center"
        style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-danger) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-app-danger) 20%, transparent)' }}>
        <p className="text-sm mb-3" style={{ color: 'var(--color-status-urgent)' }}>{error}</p>
        <button onClick={() => load()} className="px-4 py-1.5 rounded-lg text-xs font-medium cursor-pointer border-none"
          style={{ backgroundColor: 'color-mix(in srgb, var(--color-app-danger) 20%, transparent)', color: 'var(--color-status-urgent)' }}>Retry</button>
      </div>
    );
  }

  const achievements = buildAchievements(tasks, missions, sessions);
  const unlockedCount = achievements.filter((a) => a.unlocked).length;

  const completedTasks = tasks.filter((t) => t.status === 'completed').length;
  const completedMissions = missions.filter((m) => m.status === 'completed').length;
  const totalFocusMinutes = sessions.reduce((a, s) => a + (s.duration_minutes ?? 0), 0);

  const displayName = user?.email?.split('@')[0] ?? 'Explorer';

  return (
    <div className="max-w-3xl mx-auto">
      {/* Passport header */}
      <div
        className="rounded-xl p-6 mb-8 flex flex-col sm:flex-row sm:items-center gap-5"
        style={{
          background: 'linear-gradient(135deg, color-mix(in srgb, var(--color-app-gold) 8%, transparent) 0%, color-mix(in srgb, var(--color-app-mission) 6%, transparent) 100%)',
          border: '1px solid color-mix(in srgb, var(--color-app-gold) 20%, transparent)',
        }}
      >
        {/* Avatar */}
        <div
          className="w-16 h-16 rounded-full flex items-center justify-center text-xl font-display font-bold flex-shrink-0"
          style={{
            backgroundColor: 'color-mix(in srgb, var(--color-app-gold) 12%, transparent)',
            border: '2px solid color-mix(in srgb, var(--color-app-gold) 30%, transparent)',
            color: 'var(--color-app-gold)',
          }}
        >
          {displayName[0]?.toUpperCase()}
        </div>

        <div className="flex-1">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] mb-1" style={{ color: 'var(--color-app-gold)' }}>
            Odyssey Passport
          </p>
          <h1 className="font-display text-2xl" style={{ color: 'var(--color-app-text)' }}>
            {displayName}
          </h1>
          <p className="text-sm mt-0.5" style={{ color: 'var(--color-app-text-muted)' }}>
            {user?.email}
          </p>
        </div>

        <div className="flex flex-row sm:flex-col items-center gap-1 text-right">
          <span className="text-3xl font-display font-bold" style={{ color: 'var(--color-app-gold)' }}>
            {unlockedCount}
          </span>
          <span className="text-xs" style={{ color: 'var(--color-app-text-dim)' }}>
            / {achievements.length} achievements
          </span>
        </div>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-3 mb-8">
        {[
          { label: 'Tasks Completed', value: completedTasks },
          { label: 'Missions Completed', value: completedMissions },
          { label: 'Focus Minutes', value: totalFocusMinutes },
        ].map(({ label, value }) => (
          <div
            key={label}
            className="rounded-xl p-4 text-center"
            style={{ backgroundColor: 'var(--color-app-surface)', border: '1px solid var(--color-app-border)' }}
          >
            <p className="text-2xl font-display font-medium" style={{ color: 'var(--color-app-text)' }}>{value}</p>
            <p className="text-[0.65rem] mt-0.5 font-semibold uppercase tracking-wider" style={{ color: 'var(--color-app-text-dim)' }}>{label}</p>
          </div>
        ))}
      </div>

      {/* Account Data & Portability */}
      <DataPortabilitySection
        taskCount={tasks.length}
        missionCount={missions.length}
        sessionCount={sessions.length}
        onDataRestored={() => load(false)}
      />

      {/* Section label */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--color-app-text-muted)' }}>
          Achievements
        </p>
        <p className="text-xs" style={{ color: 'var(--color-app-text-dim)' }}>
          {unlockedCount} unlocked
        </p>
      </div>

      {/* Achievement grid */}
      {achievements.length === 0 ? (
        <div className="rounded-xl p-12 text-center"
          style={{ backgroundColor: 'var(--color-app-surface)', border: '1px solid var(--color-app-border)' }}>
          <p className="text-sm" style={{ color: 'var(--color-app-text-dim)' }}>
            No achievements defined yet.
          </p>
        </div>
      ) : (
        <>
          {/* Unlocked first */}
          {achievements.filter((a) => a.unlocked).length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
              {achievements.filter((a) => a.unlocked).map((a) => (
                <AchievementBadge key={a.id} achievement={a} />
              ))}
            </div>
          )}

          {/* Locked */}
          {achievements.filter((a) => !a.unlocked).length > 0 && (
            <details className="group">
              <summary className="text-xs font-semibold uppercase tracking-wider cursor-pointer mb-3 flex items-center gap-2 select-none list-none"
                style={{ color: 'var(--color-app-text-dim)' }}>
                <svg className="w-3.5 h-3.5 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
                </svg>
                Locked ({achievements.filter((a) => !a.unlocked).length})
              </summary>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-3">
                {achievements.filter((a) => !a.unlocked).map((a) => (
                  <AchievementBadge key={a.id} achievement={a} />
                ))}
              </div>
            </details>
          )}
        </>
      )}
    </div>
  );
}
