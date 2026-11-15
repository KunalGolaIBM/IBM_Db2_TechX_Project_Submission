import type { Mission } from '../types/database';

/** The Execute link only stands out when there is a mission that is planned or already running. */
export function hasMissionToExecute(missions: Pick<Mission, 'status'>[]): boolean {
  return missions.some(m => m.status === 'planned' || m.status === 'active' || m.status === 'paused');
}
