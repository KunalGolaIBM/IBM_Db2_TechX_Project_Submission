import { supabase } from '../lib/supabase';
import { localTasks } from '../lib/localStore';
import type { Task, CreateTaskInput, UpdateTaskInput, TaskStatus } from '../types/database';

/** Returns the current authenticated user, or null if anonymous. */
async function getUser() {
  const { data } = await supabase.auth.getUser();
  return data.user ?? null;
}

export const taskService = {
  async getTasks(filter?: { status?: TaskStatus }): Promise<Task[]> {
    const user = await getUser();
    if (!user) return Promise.resolve(localTasks.getAll(filter));

    let query = supabase.from('tasks').select('*').order('created_at', { ascending: false });
    if (filter?.status) query = query.eq('status', filter.status);
    const { data, error } = await query;
    if (error) throw error;
    return (data as Task[]) || [];
  },

  async createTask(input: CreateTaskInput): Promise<Task> {
    const user = await getUser();
    if (!user) return Promise.resolve(localTasks.create(input));

    const { data, error } = await supabase
      .from('tasks')
      .insert({
        user_id:           user.id,
        title:             input.title,
        description:       input.description ?? null,
        status:            input.status ?? 'todo',
        priority:          input.priority ?? 'medium',
        deadline:          input.deadline ?? null,
        estimated_minutes: input.estimated_minutes ?? null,
        source:            input.source ?? null,
        source_id:         input.source_id ?? null,
      })
      .select()
      .single();
    if (error) throw error;
    return data as Task;
  },

  async updateTask(id: string, updates: UpdateTaskInput): Promise<Task> {
    const user = await getUser();
    if (!user) return Promise.resolve(localTasks.update(id, updates));

    const { data, error } = await supabase
      .from('tasks')
      .update({ ...updates, updated_at: new Date().toISOString() })
      .eq('id', id)
      .select()
      .single();
    if (error) throw error;
    return data as Task;
  },

  async completeTask(id: string): Promise<Task> {
    const user = await getUser();
    if (!user) return Promise.resolve(localTasks.complete(id));

    const now = new Date().toISOString();
    const { data, error } = await supabase
      .from('tasks')
      .update({ status: 'completed', completed_at: now, updated_at: now })
      .eq('id', id)
      .select()
      .single();
    if (error) throw error;
    return data as Task;
  },

  async deleteTask(id: string): Promise<void> {
    const user = await getUser();
    if (!user) return Promise.resolve(localTasks.delete(id));

    const { error } = await supabase.from('tasks').delete().eq('id', id);
    if (error) throw error;
  },
};
