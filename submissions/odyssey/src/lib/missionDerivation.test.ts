import { describe, expect, it } from 'vitest';
import { deriveMissionFromTask } from './missionDerivation';

describe('task-derived mission duration', () => {
  it.each([0, -5, 241, 1.5, NaN, Infinity])
    ('uses a valid target when the task estimate is %s', estimate => {
      expect(deriveMissionFromTask({ title: 'Read notes', estimated_minutes: estimate }).planned_minutes).toBe(25);
    });

  it('keeps a valid estimate', () => {
    expect(deriveMissionFromTask({ title: 'Read notes', estimated_minutes: 90 }).planned_minutes).toBe(90);
  });
});
