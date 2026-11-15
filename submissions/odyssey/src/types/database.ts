export type TaskStatus = 'backlog' | 'todo' | 'in_progress' | 'completed' | 'archived';
export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent';

export interface Profile {
  id: string;
  user_id: string;
  display_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface Task {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  deadline: string | null;
  estimated_minutes: number | null;
  source: string | null;
  source_id: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

export type MissionStatus = 'planned' | 'active' | 'paused' | 'completed' | 'abandoned';

export interface Mission {
  id: string;
  user_id: string;
  task_id: string | null;
  title: string;
  objective: string | null;
  next_action: string | null;
  planned_minutes: number | null;
  status: MissionStatus;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface FocusSession {
  id: string;
  user_id: string;
  mission_id: string | null;
  started_at: string;
  ended_at: string | null;
  duration_minutes: number | null;
  completed: boolean;
  created_at: string;
}

/* Helper types for CRUD inputs */
export interface CreateTaskInput {
  title: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  deadline?: string | null;
  estimated_minutes?: number | null;
  source?: string | null;
  source_id?: string | null;
}

export interface UpdateTaskInput {
  title?: string;
  description?: string | null;
  status?: TaskStatus;
  priority?: TaskPriority;
  deadline?: string | null;
  estimated_minutes?: number | null;
  source?: string | null;
  source_id?: string | null;
  completed_at?: string | null;
}
