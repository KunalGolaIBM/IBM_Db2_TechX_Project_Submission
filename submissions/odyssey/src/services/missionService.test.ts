import { describe, expect, it, vi } from 'vitest';

vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getUser: vi.fn().mockResolvedValue({ data: { user: null } }),
    },
    from: vi.fn(),
  },
}));

import { missionService } from './missionService';
import type { CreateMissionInput } from './missionService';

describe('missionService duration validation', () => {
  it.each([null, 0, -1, 1.5, 241, NaN, Infinity])
    ('rejects invalid duration %s before creating a mission', async value => {
      await expect(missionService.createMission({ title: 'Test', planned_minutes: value as number }))
        .rejects.toThrow(RangeError);
    });

  it('rejects an invalid duration update before persistence', async () => {
    await expect(missionService.updateMission('mission-id', { planned_minutes: 0 }))
      .rejects.toThrow(RangeError);
  });

  it('rejects omitted duration at runtime for older callers', async () => {
    await expect(missionService.createMission({ title: 'Test' } as CreateMissionInput))
      .rejects.toThrow(RangeError);
  });
});
