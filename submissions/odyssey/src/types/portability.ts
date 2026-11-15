import type { Task, Mission, FocusSession } from './database';

export interface OdysseyExportData {
  tasks: Task[];
  missions: Mission[];
  sessions: FocusSession[];
}

export interface OdysseyExportPackage {
  version: 1;
  app: 'odyssey';
  exported_at: string;
  summary: {
    task_count: number;
    mission_count: number;
    session_count: number;
  };
  data: OdysseyExportData;
}

export interface ValidationError {
  path: string;
  message: string;
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  data?: OdysseyExportData;
  summary?: {
    task_count: number;
    mission_count: number;
    session_count: number;
  };
  exported_at?: string;
  version?: number;
}

export type RestoreStrategy = 'merge' | 'replace';

export interface RestoreResult {
  success: boolean;
  strategy: RestoreStrategy;
  tasksImported: number;
  missionsImported: number;
  sessionsImported: number;
  error?: string;
}
