import { describe, expect, it } from 'vitest';
import { validateOdysseyBackup } from './schemaValidation';

describe('validateOdysseyBackup', () => {
  it('validates a complete standard export package successfully', () => {
    const backup = {
      version: 1,
      app: 'odyssey',
      exported_at: '2026-11-02T10:00:00.000Z',
      data: {
        tasks: [
          {
            id: 'd1985478-f9b2-4d2b-a8d8-7b9c9f28a6f1',
            title: 'Complete project documentation',
            status: 'todo',
            priority: 'high',
            estimated_minutes: 45,
          },
        ],
        missions: [
          {
            id: 'a1985478-f9b2-4d2b-a8d8-7b9c9f28a6f2',
            title: 'Draft architecture section',
            planned_minutes: 30,
            status: 'planned',
          },
        ],
        sessions: [
          {
            id: 'b1985478-f9b2-4d2b-a8d8-7b9c9f28a6f3',
            started_at: '2026-11-02T10:00:00.000Z',
            completed: true,
            duration_minutes: 25,
          },
        ],
      },
    };

    const result = validateOdysseyBackup(backup);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
    expect(result.data?.tasks).toHaveLength(1);
    expect(result.data?.missions).toHaveLength(1);
    expect(result.data?.sessions).toHaveLength(1);
    expect(result.summary?.task_count).toBe(1);
    expect(result.summary?.mission_count).toBe(1);
    expect(result.summary?.session_count).toBe(1);
  });

  it('validates flat collections and focus_sessions alias', () => {
    const flat = {
      tasks: [{ title: 'Quick task' }],
      missions: [{ title: 'Quick mission', planned_minutes: 25 }],
      focus_sessions: [{ started_at: '2026-11-02T11:00:00.000Z' }],
    };

    const result = validateOdysseyBackup(flat);
    expect(result.valid).toBe(true);
    expect(result.data?.tasks[0].title).toBe('Quick task');
    expect(result.data?.tasks[0].status).toBe('todo');
    expect(result.data?.missions[0].planned_minutes).toBe(25);
    expect(result.data?.sessions).toHaveLength(1);
  });

  it('rejects non-object root', () => {
    expect(validateOdysseyBackup(null).valid).toBe(false);
    expect(validateOdysseyBackup([]).valid).toBe(false);
    expect(validateOdysseyBackup('string').valid).toBe(false);
  });

  it('rejects unrecognized format when no recognizable keys exist', () => {
    const result = validateOdysseyBackup({ foo: 'bar', baz: 123 });
    expect(result.valid).toBe(false);
    expect(result.errors[0].message).toContain('Unrecognized backup format');
  });

  it('flags tasks with empty titles or invalid statuses', () => {
    const invalidTasks = {
      tasks: [
        { title: '', status: 'invalid_status' },
      ],
      missions: [],
      sessions: [],
    };

    const result = validateOdysseyBackup(invalidTasks);
    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.path === 'tasks[0].title')).toBe(true);
    expect(result.errors.some(e => e.path === 'tasks[0].status')).toBe(true);
  });

  it('flags missions with invalid duration (out of 1-240 or non-integer)', () => {
    const invalidMissions = {
      tasks: [],
      missions: [
        { title: 'Bad duration', planned_minutes: 0 },
        { title: 'Too long', planned_minutes: 241 },
        { title: 'Fractional', planned_minutes: 15.5 },
      ],
      sessions: [],
    };

    const result = validateOdysseyBackup(invalidMissions);
    expect(result.valid).toBe(false);
    expect(result.errors.filter(e => e.path.includes('planned_minutes'))).toHaveLength(3);
  });

  it('flags sessions with invalid started_at or negative duration', () => {
    const invalidSessions = {
      tasks: [],
      missions: [],
      sessions: [
        { started_at: 'not-a-date', duration_minutes: -10, completed: 'not-a-boolean' },
      ],
    };

    const result = validateOdysseyBackup(invalidSessions);
    expect(result.valid).toBe(false);
    expect(result.errors.some(e => e.path === 'sessions[0].started_at')).toBe(true);
    expect(result.errors.some(e => e.path === 'sessions[0].duration_minutes')).toBe(true);
    expect(result.errors.some(e => e.path === 'sessions[0].completed')).toBe(true);
  });
});
