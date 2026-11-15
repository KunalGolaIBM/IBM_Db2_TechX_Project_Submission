import { supabase } from '../lib/supabase';
import { localStore } from '../lib/localStore';
import { taskService } from './taskService';
import { missionService } from './missionService';
import { focusService } from './focusService';
import { validateOdysseyBackup } from './schemaValidation';
import type { Task, Mission, FocusSession } from '../types/database';
import type {
  OdysseyExportData,
  OdysseyExportPackage,
  ValidationResult,
  RestoreStrategy,
  RestoreResult,
} from '../types/portability';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

async function getAuthUser() {
  const { data } = await supabase.auth.getUser();
  return data?.user ?? null;
}

/**
 * Normalizes IDs, foreign keys, and ownership to current user context.
 */
function prepareDataForImport(
  raw: OdysseyExportData,
  targetUserId: string,
): OdysseyExportData {
  const taskIdMap = new Map<string, string>();
  const missionIdMap = new Map<string, string>();

  // 1. Prepare Tasks
  const tasks: Task[] = raw.tasks.map((t) => {
    const validId = UUID_REGEX.test(t.id) ? t.id : generateUUID();
    if (validId !== t.id) {
      taskIdMap.set(t.id, validId);
    }
    return {
      ...t,
      id: validId,
      user_id: targetUserId,
    };
  });

  const validTaskIds = new Set(tasks.map((t) => t.id));

  // 2. Prepare Missions
  const missions: Mission[] = raw.missions.map((m) => {
    const validId = UUID_REGEX.test(m.id) ? m.id : generateUUID();
    if (validId !== m.id) {
      missionIdMap.set(m.id, validId);
    }

    // Remap task_id if remapped, or nullify if invalid/missing
    let mappedTaskId: string | null = null;
    if (m.task_id) {
      const remapped = taskIdMap.get(m.task_id) ?? m.task_id;
      if (validTaskIds.has(remapped)) {
        mappedTaskId = remapped;
      }
    }

    return {
      ...m,
      id: validId,
      user_id: targetUserId,
      task_id: mappedTaskId,
    };
  });

  const validMissionIds = new Set(missions.map((m) => m.id));

  // 3. Prepare Sessions
  const sessions: FocusSession[] = raw.sessions.map((s) => {
    const validId = UUID_REGEX.test(s.id) ? s.id : generateUUID();

    let mappedMissionId: string | null = null;
    if (s.mission_id) {
      const remapped = missionIdMap.get(s.mission_id) ?? s.mission_id;
      if (validMissionIds.has(remapped)) {
        mappedMissionId = remapped;
      }
    }

    return {
      ...s,
      id: validId,
      user_id: targetUserId,
      mission_id: mappedMissionId,
    };
  });

  return { tasks, missions, sessions };
}

export const portabilityService = {
  /**
   * Exports full user task, mission, and session history as a structured package.
   */
  async exportUserData(): Promise<OdysseyExportPackage> {
    const [tasks, missions, sessions] = await Promise.all([
      taskService.getTasks(),
      missionService.getMissions(),
      focusService.getAllSessions(),
    ]);

    const pkg: OdysseyExportPackage = {
      version: 1,
      app: 'odyssey',
      exported_at: new Date().toISOString(),
      summary: {
        task_count: tasks.length,
        mission_count: missions.length,
        session_count: sessions.length,
      },
      data: {
        tasks,
        missions,
        sessions,
      },
    };

    return pkg;
  },

  /**
   * Generates a JSON file download in the browser.
   */
  async downloadBackupFile(customPackage?: OdysseyExportPackage): Promise<{ filename: string; package: OdysseyExportPackage }> {
    const pkg = customPackage ?? (await portabilityService.exportUserData());
    const jsonStr = JSON.stringify(pkg, null, 2);

    const dateStr = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `odyssey-backup-${dateStr}.json`;

    if (typeof window !== 'undefined' && typeof document !== 'undefined') {
      const blob = new Blob([jsonStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }

    return { filename, package: pkg };
  },

  /**
   * Parses JSON string and validates it against Odyssey backup schema.
   */
  validateImport(jsonText: string): ValidationResult {
    let parsed: unknown;
    try {
      parsed = JSON.parse(jsonText);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Invalid JSON format';
      return {
        valid: false,
        errors: [{ path: 'root', message: `The uploaded file is not valid JSON: ${msg}` }],
      };
    }

    return validateOdysseyBackup(parsed);
  },

  /**
   * Restores user data either by merging with existing data or replacing it entirely.
   */
  async restoreUserData(data: OdysseyExportData, strategy: RestoreStrategy): Promise<RestoreResult> {
    const user = await getAuthUser();

    if (!user) {
      // Unauthenticated / Anonymous mode using localStore
      const prepared = prepareDataForImport(data, 'local-anon');
      const snapshot = localStore.exportAll();

      try {
        if (strategy === 'replace') {
          localStore.replaceAll(prepared);
        } else {
          localStore.mergeAll(prepared);
        }

        return {
          success: true,
          strategy,
          tasksImported: prepared.tasks.length,
          missionsImported: prepared.missions.length,
          sessionsImported: prepared.sessions.length,
        };
      } catch (err: unknown) {
        if (strategy === 'replace') {
          try {
            localStore.replaceAll(snapshot);
          } catch {
            // Ignore rollback failure
          }
        }
        const message = err instanceof Error ? err.message : 'Local storage restoration failed.';
        return {
          success: false,
          strategy,
          tasksImported: 0,
          missionsImported: 0,
          sessionsImported: 0,
          error: message,
        };
      }
    }

    // Authenticated mode using Supabase
    const prepared = prepareDataForImport(data, user.id);

    try {
      if (strategy === 'replace') {
        // 1. Snapshot existing user data before destructive deletion to safeguard against midway failure
        const [tasksSnapRes, missionsSnapRes, sessionsSnapRes] = await Promise.all([
          supabase.from('tasks').select('*').eq('user_id', user.id),
          supabase.from('missions').select('*').eq('user_id', user.id),
          supabase.from('focus_sessions').select('*').eq('user_id', user.id),
        ]);

        if (tasksSnapRes.error) throw tasksSnapRes.error;
        if (missionsSnapRes.error) throw missionsSnapRes.error;
        if (sessionsSnapRes.error) throw sessionsSnapRes.error;

        const snapshot = {
          tasks: (tasksSnapRes.data as Task[]) ?? [],
          missions: (missionsSnapRes.data as Mission[]) ?? [],
          sessions: (sessionsSnapRes.data as FocusSession[]) ?? [],
        };

        // Cache snapshot in sessionStorage if available for disaster recovery
        const snapshotKey = `ody_backup_replace_${user.id}`;
        try {
          if (typeof sessionStorage !== 'undefined') {
            sessionStorage.setItem(snapshotKey, JSON.stringify(snapshot));
          }
        } catch {
          // Ignore storage quota or access issues
        }

        try {
          // Safe delete order to prevent constraint violations
          const { error: sessionDelErr } = await supabase.from('focus_sessions').delete().eq('user_id', user.id);
          if (sessionDelErr) throw sessionDelErr;

          const { error: missionDelErr } = await supabase.from('missions').delete().eq('user_id', user.id);
          if (missionDelErr) throw missionDelErr;

          const { error: taskDelErr } = await supabase.from('tasks').delete().eq('user_id', user.id);
          if (taskDelErr) throw taskDelErr;

          // Insert in order of dependencies (tasks -> missions -> sessions)
          if (prepared.tasks.length > 0) {
            const { error } = await supabase.from('tasks').insert(prepared.tasks);
            if (error) throw error;
          }

          if (prepared.missions.length > 0) {
            const { error } = await supabase.from('missions').insert(prepared.missions);
            if (error) throw error;
          }

          if (prepared.sessions.length > 0) {
            const { error } = await supabase.from('focus_sessions').insert(prepared.sessions);
            if (error) throw error;
          }

          // Clean up emergency snapshot after successful replace
          try {
            if (typeof sessionStorage !== 'undefined') {
              sessionStorage.removeItem(snapshotKey);
            }
          } catch {
            // Ignore
          }
        } catch (replaceErr: unknown) {
          // Insertion or deletion failed midway: attempt rollback from snapshot
          console.error('[portabilityService] Replace failed, attempting snapshot rollback:', replaceErr);
          let rollbackFailed = false;

          try {
            // Clean up any partially inserted records
            await supabase.from('focus_sessions').delete().eq('user_id', user.id);
            await supabase.from('missions').delete().eq('user_id', user.id);
            await supabase.from('tasks').delete().eq('user_id', user.id);

            // Re-insert snapshotted records
            if (snapshot.tasks.length > 0) {
              const { error } = await supabase.from('tasks').insert(snapshot.tasks);
              if (error) throw error;
            }
            if (snapshot.missions.length > 0) {
              const { error } = await supabase.from('missions').insert(snapshot.missions);
              if (error) throw error;
            }
            if (snapshot.sessions.length > 0) {
              const { error } = await supabase.from('focus_sessions').insert(snapshot.sessions);
              if (error) throw error;
            }
          } catch (rollbackErr) {
            rollbackFailed = true;
            console.error('[portabilityService] Failed to complete snapshot rollback:', rollbackErr);
          }

          const cause = replaceErr instanceof Error ? replaceErr.message : 'Database error during replace.';
          if (rollbackFailed) {
            throw new Error(`Replace failed: ${cause}. Rollback also encountered an error. A local snapshot may be preserved in session storage.`);
          }
          throw new Error(`Replace failed: ${cause}. Existing data was safely rolled back and preserved.`);
        }
      } else {
        // Merge strategy (upsert records)
        if (prepared.tasks.length > 0) {
          const { error } = await supabase.from('tasks').upsert(prepared.tasks);
          if (error) throw error;
        }

        if (prepared.missions.length > 0) {
          const { error } = await supabase.from('missions').upsert(prepared.missions);
          if (error) throw error;
        }

        if (prepared.sessions.length > 0) {
          const { error } = await supabase.from('focus_sessions').upsert(prepared.sessions);
          if (error) throw error;
        }
      }

      return {
        success: true,
        strategy,
        tasksImported: prepared.tasks.length,
        missionsImported: prepared.missions.length,
        sessionsImported: prepared.sessions.length,
      };
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Database restoration failed.';
      return {
        success: false,
        strategy,
        tasksImported: 0,
        missionsImported: 0,
        sessionsImported: 0,
        error: message,
      };
    }
  },
};
