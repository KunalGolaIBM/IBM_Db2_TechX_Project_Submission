import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { Task, Mission, FocusSession } from '../types/database';

// Safe localStorage mock for headless / node test environments
const mockStore = new Map<string, string>();
const localStorageMock = {
  getItem: vi.fn((key: string) => mockStore.get(key) ?? null),
  setItem: vi.fn((key: string, value: string) => {
    mockStore.set(key, String(value));
  }),
  removeItem: vi.fn((key: string) => {
    mockStore.delete(key);
  }),
  clear: vi.fn(() => {
    mockStore.clear();
  }),
  key: vi.fn((index: number) => Array.from(mockStore.keys())[index] ?? null),
  get length() {
    return mockStore.size;
  },
};

if (typeof globalThis.localStorage === 'undefined') {
  Object.defineProperty(globalThis, 'localStorage', {
    value: localStorageMock,
    writable: true,
  });
}

// Supabase mock supporting both anonymous and authenticated sessions
let mockUser: { id: string; email?: string } | null = null;
const mockFrom = vi.fn();

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getUser: vi.fn(async () => ({ data: { user: mockUser } })),
    },
    from: (table: string) => mockFrom(table),
  },
}));

import { portabilityService } from './portabilityService';
import { localStore } from '../lib/localStore';

describe('portabilityService', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockUser = null;
    mockStore.clear();
    mockFrom.mockReset();
    localStore.clearAll();
  });

  it('exports structured JSON package with version and counts', async () => {
    localStore.replaceAll({
      tasks: [
        {
          id: '550e8400-e29b-41d4-a716-446655440000',
          user_id: 'local-anon',
          title: 'Export Test Task',
          description: null,
          status: 'todo',
          priority: 'medium',
          deadline: null,
          estimated_minutes: null,
          source: null,
          source_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
      missions: [
        {
          id: '650e8400-e29b-41d4-a716-446655440001',
          user_id: 'local-anon',
          task_id: null,
          title: 'Export Test Mission',
          objective: null,
          next_action: null,
          planned_minutes: 25,
          status: 'planned',
          started_at: null,
          completed_at: null,
          created_at: new Date().toISOString(),
        },
      ],
      sessions: [],
    });

    const exported = await portabilityService.exportUserData();
    expect(exported.version).toBe(1);
    expect(exported.app).toBe('odyssey');
    expect(exported.summary.task_count).toBe(1);
    expect(exported.summary.mission_count).toBe(1);
    expect(exported.summary.session_count).toBe(0);
    expect(exported.data.tasks[0].title).toBe('Export Test Task');
    expect(exported.data.missions[0].title).toBe('Export Test Mission');
  });

  it('validates import strings and rejects corrupted JSON', () => {
    const corruptedResult = portabilityService.validateImport('{ bad json: ');
    expect(corruptedResult.valid).toBe(false);
    expect(corruptedResult.errors[0].message).toContain('not valid JSON');

    const validJson = JSON.stringify({
      version: 1,
      app: 'odyssey',
      data: {
        tasks: [{ title: 'Valid task' }],
        missions: [{ title: 'Valid mission', planned_minutes: 30 }],
        sessions: [],
      },
    });

    const validResult = portabilityService.validateImport(validJson);
    expect(validResult.valid).toBe(true);
    expect(validResult.data?.tasks).toHaveLength(1);
    expect(validResult.data?.missions).toHaveLength(1);
  });

  it('safely restores user data using "replace" strategy in local mode', async () => {
    localStore.replaceAll({
      tasks: [
        {
          id: '11111111-1111-4111-a111-111111111111',
          user_id: 'local-anon',
          title: 'Old Task to be replaced',
          description: null,
          status: 'todo',
          priority: 'low',
          deadline: null,
          estimated_minutes: null,
          source: null,
          source_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
      missions: [],
      sessions: [],
    });

    const newBackupData = {
      tasks: [
        {
          id: '22222222-2222-4222-a222-222222222222',
          user_id: 'other-user',
          title: 'Brand New Restored Task',
          description: null,
          status: 'completed' as const,
          priority: 'urgent' as const,
          deadline: null,
          estimated_minutes: 60,
          source: null,
          source_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
        },
      ],
      missions: [],
      sessions: [],
    };

    const result = await portabilityService.restoreUserData(newBackupData, 'replace');
    expect(result.success).toBe(true);
    expect(result.strategy).toBe('replace');
    expect(result.tasksImported).toBe(1);

    const currentTasks = localStore.exportAll().tasks;
    expect(currentTasks).toHaveLength(1);
    expect(currentTasks[0].title).toBe('Brand New Restored Task');
    expect(currentTasks[0].user_id).toBe('local-anon');
  });

  it('safely merges imported data with existing records', async () => {
    localStore.replaceAll({
      tasks: [
        {
          id: '11111111-1111-4111-a111-111111111111',
          user_id: 'local-anon',
          title: 'Existing Task 1',
          description: null,
          status: 'todo',
          priority: 'low',
          deadline: null,
          estimated_minutes: null,
          source: null,
          source_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
      missions: [],
      sessions: [],
    });

    const backupData = {
      tasks: [
        {
          id: '33333333-3333-4333-a333-333333333333',
          user_id: 'another-user',
          title: 'Merged Task 2',
          description: null,
          status: 'in_progress' as const,
          priority: 'high' as const,
          deadline: null,
          estimated_minutes: 30,
          source: null,
          source_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
      missions: [],
      sessions: [],
    };

    const result = await portabilityService.restoreUserData(backupData, 'merge');
    expect(result.success).toBe(true);
    expect(result.strategy).toBe('merge');

    const currentTasks = localStore.exportAll().tasks;
    expect(currentTasks).toHaveLength(2);
    expect(currentTasks.map(t => t.title)).toContain('Existing Task 1');
    expect(currentTasks.map(t => t.title)).toContain('Merged Task 2');
  });

  it('safely snapshots existing data and rolls back if Supabase replace fails midway', async () => {
    mockUser = { id: 'supabase-user-123' };

    const initialTasks: Task[] = [
      {
        id: '11111111-1111-4111-a111-111111111111',
        user_id: 'supabase-user-123',
        title: 'Original Existing Task',
        description: null,
        status: 'todo',
        priority: 'high',
        deadline: null,
        estimated_minutes: null,
        source: null,
        source_id: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        completed_at: null,
      },
    ];

    const initialMissions: Mission[] = [
      {
        id: '22222222-2222-4222-a222-222222222222',
        user_id: 'supabase-user-123',
        task_id: '11111111-1111-4111-a111-111111111111',
        title: 'Original Mission',
        objective: null,
        next_action: null,
        planned_minutes: 25,
        status: 'planned',
        started_at: null,
        completed_at: null,
        created_at: new Date().toISOString(),
      },
    ];

    const initialSessions: FocusSession[] = [];

    const insertedRecords: Record<string, any[]> = {
      tasks: [],
      missions: [],
      focus_sessions: [],
    };

    let missionInsertAttempts = 0;

    mockFrom.mockImplementation((table: string) => ({
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockImplementation(() => {
          if (table === 'tasks') return Promise.resolve({ data: initialTasks, error: null });
          if (table === 'missions') return Promise.resolve({ data: initialMissions, error: null });
          if (table === 'focus_sessions') return Promise.resolve({ data: initialSessions, error: null });
          return Promise.resolve({ data: [], error: null });
        }),
      }),
      delete: vi.fn().mockReturnValue({
        eq: vi.fn().mockResolvedValue({ error: null }),
      }),
      insert: vi.fn().mockImplementation((records: any[]) => {
        if (table === 'missions') {
          missionInsertAttempts++;
          if (missionInsertAttempts === 1) {
            // First attempt to insert new missions fails midway
            return Promise.resolve({ error: new Error('Foreign key violation in missions') });
          }
        }
        insertedRecords[table].push(...records);
        return Promise.resolve({ error: null });
      }),
    }));

    const incomingData = {
      tasks: [
        {
          id: '99999999-9999-4999-a999-999999999999',
          user_id: 'other-user',
          title: 'New Task That Should Fail Rollback',
          description: null,
          status: 'todo' as const,
          priority: 'low' as const,
          deadline: null,
          estimated_minutes: null,
          source: null,
          source_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
      missions: [
        {
          id: '88888888-8888-4888-a888-888888888888',
          user_id: 'other-user',
          task_id: null,
          title: 'Failing New Mission',
          objective: null,
          next_action: null,
          planned_minutes: 30,
          status: 'planned' as const,
          started_at: null,
          completed_at: null,
          created_at: new Date().toISOString(),
        },
      ],
      sessions: [],
    };

    const result = await portabilityService.restoreUserData(incomingData, 'replace');

    // Restoration should report failure and indicate data was rolled back and preserved
    expect(result.success).toBe(false);
    expect(result.error).toContain('Foreign key violation in missions');
    expect(result.error).toContain('safely rolled back and preserved');

    // Verify rollback re-inserted original snapshot task
    expect(insertedRecords.tasks).toEqual(
      expect.arrayContaining([expect.objectContaining({ title: 'Original Existing Task' })])
    );
  });

  it('successfully executes replace in Supabase authenticated mode', async () => {
    mockUser = { id: 'supabase-user-123' };

    mockFrom.mockImplementation((_table: string) => ({
      select: vi.fn().mockReturnValue({
        eq: vi.fn().mockResolvedValue({ data: [], error: null }),
      }),
      delete: vi.fn().mockReturnValue({
        eq: vi.fn().mockResolvedValue({ error: null }),
      }),
      insert: vi.fn().mockResolvedValue({ error: null }),
    }));

    const incomingData = {
      tasks: [
        {
          id: '77777777-7777-4777-a777-777777777777',
          user_id: 'other-user',
          title: 'Restored Supabase Task',
          description: null,
          status: 'todo' as const,
          priority: 'medium' as const,
          deadline: null,
          estimated_minutes: null,
          source: null,
          source_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
      missions: [],
      sessions: [],
    };

    const result = await portabilityService.restoreUserData(incomingData, 'replace');
    expect(result.success).toBe(true);
    expect(result.tasksImported).toBe(1);
    expect(result.strategy).toBe('replace');
  });

  it('successfully executes merge (upsert) in Supabase authenticated mode', async () => {
    mockUser = { id: 'supabase-user-123' };
    const upsertedTables: string[] = [];

    mockFrom.mockImplementation((table: string) => ({
      upsert: vi.fn().mockImplementation(() => {
        upsertedTables.push(table);
        return Promise.resolve({ error: null });
      }),
    }));

    const incomingData = {
      tasks: [
        {
          id: '55555555-5555-4555-a555-555555555555',
          user_id: 'other-user',
          title: 'Merged Supabase Task',
          description: null,
          status: 'todo' as const,
          priority: 'high' as const,
          deadline: null,
          estimated_minutes: null,
          source: null,
          source_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
      missions: [],
      sessions: [],
    };

    const result = await portabilityService.restoreUserData(incomingData, 'merge');
    expect(result.success).toBe(true);
    expect(result.tasksImported).toBe(1);
    expect(result.strategy).toBe('merge');
    expect(upsertedTables).toContain('tasks');
  });

  it('rolls back to original snapshot if localStore replaceAll throws', async () => {
    mockUser = null;

    localStore.replaceAll({
      tasks: [
        {
          id: '11111111-1111-4111-a111-111111111111',
          user_id: 'local-anon',
          title: 'Pre-existing Local Task',
          description: null,
          status: 'todo',
          priority: 'low',
          deadline: null,
          estimated_minutes: null,
          source: null,
          source_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
      missions: [],
      sessions: [],
    });

    let attempt = 0;
    const realReplaceAll = localStore.replaceAll;
    vi.spyOn(localStore, 'replaceAll').mockImplementation((data) => {
      attempt++;
      if (attempt === 1) {
        throw new Error('Storage quota exceeded');
      }
      return realReplaceAll(data);
    });

    const incomingData = {
      tasks: [
        {
          id: '22222222-2222-4222-a222-222222222222',
          user_id: 'other',
          title: 'New Failing Task',
          description: null,
          status: 'todo' as const,
          priority: 'medium' as const,
          deadline: null,
          estimated_minutes: null,
          source: null,
          source_id: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          completed_at: null,
        },
      ],
      missions: [],
      sessions: [],
    };

    const result = await portabilityService.restoreUserData(incomingData, 'replace');
    expect(result.success).toBe(false);
    expect(result.error).toContain('Storage quota exceeded');

    // Verify snapshot was restored
    const currentTasks = localStore.exportAll().tasks;
    expect(currentTasks).toHaveLength(1);
    expect(currentTasks[0].title).toBe('Pre-existing Local Task');
  });
});
