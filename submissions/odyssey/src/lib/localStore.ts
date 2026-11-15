/**
 * Odyssey Local Store
 *
 * localStorage-backed persistence for unauthenticated (anonymous/demo) users.
 * Mirrors the exact same async API shapes used by taskService, missionService,
 * and focusService so all page components can call the same service interface
 * regardless of whether the user is signed in.
 *
 * Storage keys:
 *   ody_tasks          — Task[]
 *   ody_missions       — Mission[]
 *   ody_focus_sessions — FocusSession[]
 */

import type {
  Task,
  TaskStatus,
  TaskPriority,
  Mission,
  MissionStatus,
  FocusSession,
  CreateTaskInput,
  UpdateTaskInput,
} from '../types/database';
import type { CreateMissionInput, UpdateMissionInput } from '../services/missionService';
import { isValidMissionDuration } from './missionDuration';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const ANON_USER_ID = 'local-anon';

function uuid(): string {
  // crypto.randomUUID is available in all modern browsers and Node 15+
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older environments
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

function now(): string {
  return new Date().toISOString();
}

// In-memory fallback for environments where localStorage is not available (e.g. SSR, restricted context, or headless tests)
const memoryStorage = new Map<string, string>();

function getLocalStorage(): Storage | null {
  try {
    if (typeof window !== 'undefined' && window.localStorage) {
      return window.localStorage;
    }
    if (typeof localStorage !== 'undefined') {
      return localStorage;
    }
  } catch (err: unknown) {
    // Blocked by security policy or storage sandbox
  }
  return null;
}

function load<T>(key: string): T[] {
  try {
    const storage = getLocalStorage();
    const raw = storage ? storage.getItem(key) : memoryStorage.get(key);
    return raw ? (JSON.parse(raw) as T[]) : [];
  } catch (err: unknown) {
    return [];
  }
}

function save<T>(key: string, items: T[]): void {
  try {
    const serialized = JSON.stringify(items);
    const storage = getLocalStorage();
    if (storage) {
      storage.setItem(key, serialized);
      return;
    }
    memoryStorage.set(key, serialized);
  } catch (err: unknown) {
    console.warn(`[localStore] Failed to persist "${key}" to localStorage:`, err);
    memoryStorage.set(key, JSON.stringify(items));
    if (err instanceof Error && (err.name === 'QuotaExceededError' || err.name === 'NS_ERROR_DOM_QUOTA_REACHED')) {
      throw new Error(`Storage quota exceeded while saving ${key}.`);
    }
    throw err;
  }
}

// Storage key constants
const KEYS = {
  tasks:    'ody_tasks',
  missions: 'ody_missions',
  sessions: 'ody_focus_sessions',
} as const;

// ─── Task operations ──────────────────────────────────────────────────────────

export const localTasks = {
  getAll(filter?: { status?: TaskStatus }): Task[] {
    const tasks = load<Task>(KEYS.tasks);
    if (filter?.status) return tasks.filter(t => t.status === filter.status);
    return tasks.sort((a, b) => b.created_at.localeCompare(a.created_at));
  },

  create(input: CreateTaskInput): Task {
    const task: Task = {
      id:                uuid(),
      user_id:           ANON_USER_ID,
      title:             input.title,
      description:       input.description ?? null,
      status:            (input.status ?? 'todo') as TaskStatus,
      priority:          (input.priority ?? 'medium') as TaskPriority,
      deadline:          input.deadline ?? null,
      estimated_minutes: input.estimated_minutes ?? null,
      source:            input.source ?? null,
      source_id:         input.source_id ?? null,
      created_at:        now(),
      updated_at:        now(),
      completed_at:      null,
    };
    const tasks = load<Task>(KEYS.tasks);
    tasks.unshift(task);
    save(KEYS.tasks, tasks);
    return task;
  },

  update(id: string, updates: UpdateTaskInput): Task {
    const tasks = load<Task>(KEYS.tasks);
    const idx = tasks.findIndex(t => t.id === id);
    if (idx === -1) throw new Error(`Task ${id} not found`);
    const updated: Task = { ...tasks[idx], ...updates, updated_at: now() };
    tasks[idx] = updated;
    save(KEYS.tasks, tasks);
    return updated;
  },

  complete(id: string): Task {
    return localTasks.update(id, {
      status: 'completed',
      completed_at: now(),
    });
  },

  delete(id: string): void {
    const tasks = load<Task>(KEYS.tasks).filter(t => t.id !== id);
    save(KEYS.tasks, tasks);
  },

  replaceAll(tasks: Task[]): void {
    save(KEYS.tasks, tasks);
  },

  merge(tasks: Task[]): void {
    const existing = load<Task>(KEYS.tasks);
    const map = new Map(existing.map(t => [t.id, t]));
    for (const t of tasks) {
      map.set(t.id, t);
    }
    const merged = Array.from(map.values()).sort((a, b) => b.created_at.localeCompare(a.created_at));
    save(KEYS.tasks, merged);
  },
};

// ─── Mission operations ───────────────────────────────────────────────────────

export const localMissions = {
  getAll(filter?: { status?: MissionStatus }): Mission[] {
    const missions = load<Mission>(KEYS.missions);
    const sorted = missions.sort((a, b) => b.created_at.localeCompare(a.created_at));
    if (filter?.status) return sorted.filter(m => m.status === filter.status);
    return sorted;
  },

  getOne(id: string): Mission {
    const mission = load<Mission>(KEYS.missions).find(m => m.id === id);
    if (!mission) throw new Error(`Mission ${id} not found`);
    return mission;
  },

  create(input: CreateMissionInput): Mission {
    if (!isValidMissionDuration(input.planned_minutes)) {
      throw new RangeError('Planned time must be a whole number from 1 to 240 minutes.');
    }
    const mission: Mission = {
      id:              uuid(),
      user_id:         ANON_USER_ID,
      task_id:         input.task_id ?? null,
      title:           input.title,
      objective:       input.objective ?? null,
      next_action:     input.next_action ?? null,
      planned_minutes: input.planned_minutes,
      status:          'planned',
      started_at:      null,
      completed_at:    null,
      created_at:      now(),
    };
    const missions = load<Mission>(KEYS.missions);
    missions.unshift(mission);
    save(KEYS.missions, missions);
    return mission;
  },

  update(id: string, updates: UpdateMissionInput): Mission {
    if ('planned_minutes' in updates && !isValidMissionDuration(updates.planned_minutes)) {
      throw new RangeError('Planned time must be a whole number from 1 to 240 minutes.');
    }
    const missions = load<Mission>(KEYS.missions);
    const idx = missions.findIndex(m => m.id === id);
    if (idx === -1) throw new Error(`Mission ${id} not found`);
    const updated: Mission = { ...missions[idx], ...updates };
    missions[idx] = updated;
    save(KEYS.missions, missions);
    return updated;
  },

  delete(id: string): void {
    const missions = load<Mission>(KEYS.missions).filter(m => m.id !== id);
    save(KEYS.missions, missions);
  },

  replaceAll(missions: Mission[]): void {
    save(KEYS.missions, missions);
  },

  merge(missions: Mission[]): void {
    const existing = load<Mission>(KEYS.missions);
    const map = new Map(existing.map(m => [m.id, m]));
    for (const m of missions) {
      map.set(m.id, m);
    }
    const merged = Array.from(map.values()).sort((a, b) => b.created_at.localeCompare(a.created_at));
    save(KEYS.missions, merged);
  },
};

// ─── Focus session operations ──────────────────────────────────────────────────

export const localSessions = {
  getAll(): FocusSession[] {
    return load<FocusSession>(KEYS.sessions)
      .sort((a, b) => b.started_at.localeCompare(a.started_at));
  },

  getForMission(missionId: string): FocusSession[] {
    return load<FocusSession>(KEYS.sessions)
      .filter(s => s.mission_id === missionId)
      .sort((a, b) => b.started_at.localeCompare(a.started_at));
  },

  start(missionId: string): FocusSession {
    const sessions = load<FocusSession>(KEYS.sessions);
    const existing = sessions.find(s => s.mission_id === missionId && !s.ended_at);
    if (existing) return existing;

    const session: FocusSession = {
      id:               uuid(),
      user_id:          ANON_USER_ID,
      mission_id:       missionId,
      started_at:       now(),
      ended_at:         null,
      duration_minutes: null,
      completed:        false,
      created_at:       now(),
    };
    sessions.unshift(session);
    save(KEYS.sessions, sessions);
    return session;
  },

  end(id: string, completed: boolean): FocusSession {
    const sessions = load<FocusSession>(KEYS.sessions);
    const idx = sessions.findIndex(s => s.id === id);
    if (idx === -1) throw new Error(`Session ${id} not found`);
    const endedAt = now();
    const startedAt = new Date(sessions[idx].started_at).getTime();
    const durationMinutes = Math.round((new Date(endedAt).getTime() - startedAt) / 60000);
    const updated: FocusSession = {
      ...sessions[idx],
      ended_at: endedAt,
      duration_minutes: durationMinutes,
      completed,
    };
    sessions[idx] = updated;
    save(KEYS.sessions, sessions);
    return updated;
  },

  reopen(id: string): FocusSession {
    const sessions = load<FocusSession>(KEYS.sessions);
    const idx = sessions.findIndex(s => s.id === id);
    if (idx === -1) throw new Error(`Session ${id} not found`);
    const updated: FocusSession = {
      ...sessions[idx],
      ended_at: null,
      duration_minutes: null,
      completed: false,
    };
    sessions[idx] = updated;
    save(KEYS.sessions, sessions);
    return updated;
  },

  replaceAll(sessions: FocusSession[]): void {
    save(KEYS.sessions, sessions);
  },

  merge(sessions: FocusSession[]): void {
    const existing = load<FocusSession>(KEYS.sessions);
    const map = new Map(existing.map(s => [s.id, s]));
    for (const s of sessions) {
      map.set(s.id, s);
    }
    const merged = Array.from(map.values()).sort((a, b) => b.started_at.localeCompare(a.started_at));
    save(KEYS.sessions, merged);
  },
};

// ─── Utility: clear all local data (useful for "sign in to save" flow) ────────

export function clearLocalStore(): void {
  try {
    const storage = getLocalStorage();
    if (storage) {
      storage.removeItem(KEYS.tasks);
      storage.removeItem(KEYS.missions);
      storage.removeItem(KEYS.sessions);
    }
  } catch (err: unknown) {
    console.warn('[localStore] Failed to clear localStorage:', err);
  }
  memoryStorage.delete(KEYS.tasks);
  memoryStorage.delete(KEYS.missions);
  memoryStorage.delete(KEYS.sessions);


}

/**
 * Returns a snapshot of all local data — used when offering to migrate
 * anonymous data to a newly authenticated account (future feature).
 */
export function exportLocalStore() {
  return {
    tasks:    localTasks.getAll(),
    missions: localMissions.getAll(),
    sessions: localSessions.getAll(),
  };
}

export const localStore = {
  replaceAll(data: { tasks: Task[]; missions: Mission[]; sessions: FocusSession[] }): void {
    localTasks.replaceAll(data.tasks);
    localMissions.replaceAll(data.missions);
    localSessions.replaceAll(data.sessions);
  },
  mergeAll(data: { tasks: Task[]; missions: Mission[]; sessions: FocusSession[] }): void {
    localTasks.merge(data.tasks);
    localMissions.merge(data.missions);
    localSessions.merge(data.sessions);
  },
  exportAll() {
    return exportLocalStore();
  },
  clearAll() {
    clearLocalStore();
  },
};

