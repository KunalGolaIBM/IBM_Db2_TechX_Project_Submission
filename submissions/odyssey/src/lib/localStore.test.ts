import { describe, expect, it } from 'vitest';
import { localMissions } from './localStore';
import type { CreateMissionInput } from '../services/missionService';

describe('local mission persistence duration guard', () => {
  it.each([undefined, null, 0, -1, 1.5, 241, NaN, Infinity])
    ('rejects invalid duration %s before creating a mission', value => {
      expect(() => localMissions.create({ title: 'Test', planned_minutes: value } as CreateMissionInput))
        .toThrow(RangeError);
    });

  it('rejects an invalid duration update before loading stored data', () => {
    expect(() => localMissions.update('mission-id', { planned_minutes: 0 })).toThrow(RangeError);
  });
});
