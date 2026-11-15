import { isValidMissionDuration } from '../lib/missionDuration';
import type { Task, Mission, FocusSession, TaskStatus, TaskPriority, MissionStatus } from '../types/database';
import type { OdysseyExportData, ValidationError, ValidationResult } from '../types/portability';

const VALID_TASK_STATUSES: Set<TaskStatus> = new Set([
  'backlog',
  'todo',
  'in_progress',
  'completed',
  'archived',
]);

const VALID_TASK_PRIORITIES: Set<TaskPriority> = new Set([
  'low',
  'medium',
  'high',
  'urgent',
]);

const VALID_MISSION_STATUSES: Set<MissionStatus> = new Set([
  'planned',
  'active',
  'paused',
  'completed',
  'abandoned',
]);

function isRecord(val: unknown): val is Record<string, unknown> {
  return typeof val === 'object' && val !== null && !Array.isArray(val);
}

function isValidDateString(val: unknown): boolean {
  if (typeof val !== 'string' || !val.trim()) return false;
  const parsed = Date.parse(val);
  return !Number.isNaN(parsed);
}

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/**
 * Validates and normalizes raw JSON data against the Odyssey backup schema.
 * 
 * Supports both standard packages:
 * { version: 1, app: 'odyssey', data: { tasks: [...], missions: [...], sessions: [...] } }
 * and flattened objects:
 * { tasks: [...], missions: [...], sessions: [...] }
 */
export function validateOdysseyBackup(raw: unknown): ValidationResult {
  const errors: ValidationError[] = [];

  if (!isRecord(raw)) {
    return {
      valid: false,
      errors: [{ path: 'root', message: 'The uploaded file must be a JSON object.' }],
    };
  }

  // Extract nested data payload if formatted as OdysseyExportPackage
  let payload: Record<string, unknown>;
  let version = 1;
  let exported_at: string | undefined;

  if (isRecord(raw.data)) {
    payload = raw.data;
    if (typeof raw.version === 'number') version = raw.version;
    if (typeof raw.exported_at === 'string') exported_at = raw.exported_at;
  } else {
    payload = raw;
    if (typeof raw.exported_at === 'string') exported_at = raw.exported_at;
  }

  // Handle key aliases (e.g., focus_sessions or session_logs)
  const rawTasks = payload.tasks ?? [];
  const rawMissions = payload.missions ?? [];
  const rawSessions = payload.sessions ?? payload.focus_sessions ?? payload.session_logs ?? [];

  // Validate tasks array
  if (!Array.isArray(rawTasks)) {
    errors.push({ path: 'tasks', message: "'tasks' property must be an array." });
  }

  // Validate missions array
  if (!Array.isArray(rawMissions)) {
    errors.push({ path: 'missions', message: "'missions' property must be an array." });
  }

  // Validate sessions array
  if (!Array.isArray(rawSessions)) {
    errors.push({ path: 'sessions', message: "'sessions' property must be an array." });
  }

  // If top-level arrays are completely invalid, return early
  if (errors.length > 0) {
    return { valid: false, errors };
  }

  // Check if entire payload is completely empty (no recognizable keys)
  const hasKnownKeys = 'tasks' in payload || 'missions' in payload || 'sessions' in payload || 'focus_sessions' in payload;
  if (!hasKnownKeys && Object.keys(payload).length > 0) {
    errors.push({
      path: 'root',
      message: 'Unrecognized backup format. Expected "tasks", "missions", or "sessions" collections.',
    });
    return { valid: false, errors };
  }

  const validatedTasks: Task[] = [];
  const validatedMissions: Mission[] = [];
  const validatedSessions: FocusSession[] = [];

  const tasksList: unknown[] = Array.isArray(rawTasks) ? rawTasks : [];
  const missionsList: unknown[] = Array.isArray(rawMissions) ? rawMissions : [];
  const sessionsList: unknown[] = Array.isArray(rawSessions) ? rawSessions : [];

  // Validate individual tasks
  for (let i = 0; i < tasksList.length; i++) {
    const item = tasksList[i];
    const path = `tasks[${i}]`;

    if (!isRecord(item)) {
      errors.push({ path, message: `Task at index ${i} must be an object.` });
      continue;
    }

    if (typeof item.title !== 'string' || item.title.trim() === '') {
      errors.push({ path: `${path}.title`, message: `Task #${i + 1} is missing a non-empty 'title'.` });
    }

    if (item.status !== undefined && item.status !== null) {
      if (typeof item.status !== 'string' || !VALID_TASK_STATUSES.has(item.status as TaskStatus)) {
        errors.push({
          path: `${path}.status`,
          message: `Task #${i + 1} has invalid status '${String(item.status)}'. Allowed: ${Array.from(VALID_TASK_STATUSES).join(', ')}.`,
        });
      }
    }

    if (item.priority !== undefined && item.priority !== null) {
      if (typeof item.priority !== 'string' || !VALID_TASK_PRIORITIES.has(item.priority as TaskPriority)) {
        errors.push({
          path: `${path}.priority`,
          message: `Task #${i + 1} has invalid priority '${String(item.priority)}'. Allowed: ${Array.from(VALID_TASK_PRIORITIES).join(', ')}.`,
        });
      }
    }

    if (item.estimated_minutes !== undefined && item.estimated_minutes !== null) {
      if (typeof item.estimated_minutes !== 'number' || item.estimated_minutes < 0 || !Number.isFinite(item.estimated_minutes)) {
        errors.push({
          path: `${path}.estimated_minutes`,
          message: `Task #${i + 1} estimated_minutes must be a non-negative number.`,
        });
      }
    }

    if (item.deadline && !isValidDateString(item.deadline)) {
      errors.push({ path: `${path}.deadline`, message: `Task #${i + 1} has an invalid deadline date format.` });
    }

    // Build normalized task object if no fatal field errors
    const nowIso = new Date().toISOString();
    validatedTasks.push({
      id: typeof item.id === 'string' && item.id.trim() ? item.id.trim() : generateUUID(),
      user_id: typeof item.user_id === 'string' ? item.user_id : 'local-anon',
      title: typeof item.title === 'string' ? item.title.trim() : '',
      description: typeof item.description === 'string' ? item.description : null,
      status: (item.status && VALID_TASK_STATUSES.has(item.status as TaskStatus)) ? (item.status as TaskStatus) : 'todo',
      priority: (item.priority && VALID_TASK_PRIORITIES.has(item.priority as TaskPriority)) ? (item.priority as TaskPriority) : 'medium',
      deadline: isValidDateString(item.deadline) ? String(item.deadline) : null,
      estimated_minutes: typeof item.estimated_minutes === 'number' ? Math.round(item.estimated_minutes) : null,
      source: typeof item.source === 'string' ? item.source : null,
      source_id: typeof item.source_id === 'string' ? item.source_id : null,
      created_at: isValidDateString(item.created_at) ? String(item.created_at) : nowIso,
      updated_at: isValidDateString(item.updated_at) ? String(item.updated_at) : nowIso,
      completed_at: isValidDateString(item.completed_at) ? String(item.completed_at) : null,
    });
  }

  // Validate individual missions
  for (let i = 0; i < missionsList.length; i++) {
    const item = missionsList[i];
    const path = `missions[${i}]`;

    if (!isRecord(item)) {
      errors.push({ path, message: `Mission at index ${i} must be an object.` });
      continue;
    }

    if (typeof item.title !== 'string' || item.title.trim() === '') {
      errors.push({ path: `${path}.title`, message: `Mission #${i + 1} is missing a non-empty 'title'.` });
    }

    if (item.planned_minutes === undefined || item.planned_minutes === null || !isValidMissionDuration(item.planned_minutes as number)) {
      errors.push({
        path: `${path}.planned_minutes`,
        message: `Mission #${i + 1} planned_minutes must be an integer between 1 and 240 minutes.`,
      });
    }

    if (item.status !== undefined && item.status !== null) {
      if (typeof item.status !== 'string' || !VALID_MISSION_STATUSES.has(item.status as MissionStatus)) {
        errors.push({
          path: `${path}.status`,
          message: `Mission #${i + 1} has invalid status '${String(item.status)}'. Allowed: ${Array.from(VALID_MISSION_STATUSES).join(', ')}.`,
        });
      }
    }

    const nowIso = new Date().toISOString();
    validatedMissions.push({
      id: typeof item.id === 'string' && item.id.trim() ? item.id.trim() : generateUUID(),
      user_id: typeof item.user_id === 'string' ? item.user_id : 'local-anon',
      task_id: typeof item.task_id === 'string' && item.task_id.trim() ? item.task_id.trim() : null,
      title: typeof item.title === 'string' ? item.title.trim() : '',
      objective: typeof item.objective === 'string' ? item.objective : null,
      next_action: typeof item.next_action === 'string' ? item.next_action : null,
      planned_minutes: typeof item.planned_minutes === 'number' && isValidMissionDuration(item.planned_minutes) ? item.planned_minutes : 25,
      status: (item.status && VALID_MISSION_STATUSES.has(item.status as MissionStatus)) ? (item.status as MissionStatus) : 'planned',
      started_at: isValidDateString(item.started_at) ? String(item.started_at) : null,
      completed_at: isValidDateString(item.completed_at) ? String(item.completed_at) : null,
      created_at: isValidDateString(item.created_at) ? String(item.created_at) : nowIso,
    });
  }

  // Validate individual focus sessions
  for (let i = 0; i < sessionsList.length; i++) {
    const item = sessionsList[i];
    const path = `sessions[${i}]`;

    if (!isRecord(item)) {
      errors.push({ path, message: `Focus session at index ${i} must be an object.` });
      continue;
    }

    if (!isValidDateString(item.started_at)) {
      errors.push({
        path: `${path}.started_at`,
        message: `Focus session #${i + 1} is missing a valid 'started_at' timestamp.`,
      });
    }

    if (item.ended_at !== undefined && item.ended_at !== null && !isValidDateString(item.ended_at)) {
      errors.push({
        path: `${path}.ended_at`,
        message: `Focus session #${i + 1} has an invalid 'ended_at' date format.`,
      });
    }

    if (item.duration_minutes !== undefined && item.duration_minutes !== null) {
      if (typeof item.duration_minutes !== 'number' || item.duration_minutes < 0 || !Number.isFinite(item.duration_minutes)) {
        errors.push({
          path: `${path}.duration_minutes`,
          message: `Focus session #${i + 1} duration_minutes must be a non-negative number.`,
        });
      }
    }

    if (item.completed !== undefined && item.completed !== null && typeof item.completed !== 'boolean') {
      errors.push({
        path: `${path}.completed`,
        message: `Focus session #${i + 1} 'completed' flag must be true or false.`,
      });
    }

    const nowIso = new Date().toISOString();
    validatedSessions.push({
      id: typeof item.id === 'string' && item.id.trim() ? item.id.trim() : generateUUID(),
      user_id: typeof item.user_id === 'string' ? item.user_id : 'local-anon',
      mission_id: typeof item.mission_id === 'string' && item.mission_id.trim() ? item.mission_id.trim() : null,
      started_at: isValidDateString(item.started_at) ? String(item.started_at) : nowIso,
      ended_at: isValidDateString(item.ended_at) ? String(item.ended_at) : null,
      duration_minutes: typeof item.duration_minutes === 'number' ? Math.round(item.duration_minutes) : null,
      completed: typeof item.completed === 'boolean' ? item.completed : false,
      created_at: isValidDateString(item.created_at) ? String(item.created_at) : nowIso,
    });
  }

  if (errors.length > 0) {
    return { valid: false, errors };
  }

  const exportData: OdysseyExportData = {
    tasks: validatedTasks,
    missions: validatedMissions,
    sessions: validatedSessions,
  };

  return {
    valid: true,
    errors: [],
    data: exportData,
    summary: {
      task_count: validatedTasks.length,
      mission_count: validatedMissions.length,
      session_count: validatedSessions.length,
    },
    exported_at,
    version,
  };
}
