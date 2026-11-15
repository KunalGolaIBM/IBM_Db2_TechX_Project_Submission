/** A mission may run from one minute through four hours. */
export const MIN_MISSION_MINUTES = 1;
export const MAX_MISSION_MINUTES = 240;
export const DEFAULT_MISSION_MINUTES = 25;

export function isValidMissionDuration(value: unknown): value is number {
  return typeof value === 'number' && Number.isInteger(value) &&
    value >= MIN_MISSION_MINUTES && value <= MAX_MISSION_MINUTES;
}

export function parseMissionDuration(value: string): number | null {
  if (!/^\d+$/.test(value.trim())) return null;
  const minutes = Number(value.trim());
  return isValidMissionDuration(minutes) ? minutes : null;
}

/** Existing malformed rows use the normal 25-minute target when displayed. */
export function safeMissionDuration(value: unknown): number {
  return isValidMissionDuration(value) ? value : DEFAULT_MISSION_MINUTES;
}
