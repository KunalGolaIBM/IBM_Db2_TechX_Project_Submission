import { describe, expect, it } from 'vitest';
import { isValidMissionDuration, parseMissionDuration, safeMissionDuration } from './missionDuration';

describe('mission duration policy', () => {
  it('accepts whole minutes within the supported range', () => {
    expect(parseMissionDuration('1')).toBe(1);
    expect(parseMissionDuration('240')).toBe(240);
    expect(isValidMissionDuration(25)).toBe(true);
  });

  it.each(['', ' ', '0', '-1', '1.5', '241', 'Infinity', 'NaN', '1e2'])
    ('rejects invalid form input %s', value => {
      expect(parseMissionDuration(value)).toBeNull();
    });

  it.each([null, undefined, 0, -1, 1.5, 241, NaN, Infinity, '25'])
    ('uses a safe target for malformed legacy value %s', value => {
      expect(isValidMissionDuration(value)).toBe(false);
      expect(safeMissionDuration(value)).toBe(25);
    });
});
