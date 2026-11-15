import { supabase } from '../lib/supabase';
import { localMissions } from '../lib/localStore';
import { isValidMissionDuration } from '../lib/missionDuration';
import type { Mission, MissionStatus } from '../types/database';

export interface CreateMissionInput {
  task_id?: string | null;
  title: string;
  objective?: string | null;
  next_action?: string | null;
  planned_minutes: number;
}

export interface UpdateMissionInput {
  title?: string;
  objective?: string | null;
  next_action?: string | null;
  planned_minutes?: number | null;
  status?: MissionStatus;
  started_at?: string | null;
  completed_at?: string | null;
}

async function getUser() {
  const { data } = await supabase.auth.getUser();
  return data.user ?? null;
}

export const missionService = {
  async getMissions(filter?: { status?: MissionStatus }): Promise<Mission[]> {
    const user = await getUser();
    if (!user) return Promise.resolve(localMissions.getAll(filter));

    let query = supabase.from('missions').select('*').order('created_at', { ascending: false });
    if (filter?.status) query = query.eq('status', filter.status);
    const { data, error } = await query;
    if (error) throw error;
    return (data as Mission[]) || [];
  },

  async getMission(id: string): Promise<Mission> {
    const user = await getUser();
    if (!user) return Promise.resolve(localMissions.getOne(id));

    const { data, error } = await supabase
      .from('missions').select('*').eq('id', id).single();
    if (error) throw error;
    return data as Mission;
  },

  async createMission(input: CreateMissionInput): Promise<Mission> {
    if (!isValidMissionDuration(input.planned_minutes)) {
      throw new RangeError('Planned time must be a whole number from 1 to 240 minutes.');
    }
    const user = await getUser();
    if (!user) return Promise.resolve(localMissions.create(input));

    const { data, error } = await supabase
      .from('missions')
      .insert({
        user_id:         user.id,
        task_id:         input.task_id ?? null,
        title:           input.title,
        objective:       input.objective ?? null,
        next_action:     input.next_action ?? null,
        planned_minutes: input.planned_minutes,
        status:          'planned',
      })
      .select()
      .single();
    if (error) throw error;
    return data as Mission;
  },

  async updateMission(id: string, updates: UpdateMissionInput): Promise<Mission> {
    if ('planned_minutes' in updates && !isValidMissionDuration(updates.planned_minutes)) {
      throw new RangeError('Planned time must be a whole number from 1 to 240 minutes.');
    }
    const user = await getUser();
    if (!user) return Promise.resolve(localMissions.update(id, updates));

    const { data, error } = await supabase
      .from('missions').update(updates).eq('id', id).select().single();
    if (error) throw error;
    return data as Mission;
  },

  async activateMission(id: string): Promise<Mission> {
    const mission = await missionService.getMission(id);
    return missionService.updateMission(id, {
      status: 'active',
      started_at: mission.started_at ?? new Date().toISOString(),
    });
  },

  async pauseMission(id: string): Promise<Mission> {
    return missionService.updateMission(id, { status: 'paused' });
  },

  async completeMission(id: string): Promise<Mission> {
    return missionService.updateMission(id, {
      status: 'completed',
      completed_at: new Date().toISOString(),
    });
  },

  async abandonMission(id: string): Promise<Mission> {
    return missionService.updateMission(id, { status: 'abandoned' });
  },

  async deleteMission(id: string): Promise<void> {
    const user = await getUser();
    if (!user) return Promise.resolve(localMissions.delete(id));

    const { error } = await supabase.from('missions').delete().eq('id', id);
    if (error) throw error;
  },
};
