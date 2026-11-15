import { describe, expect, it } from 'vitest';
import { hasMissionToExecute } from './executeHighlight';

describe('hasMissionToExecute', () => {
  it('is false with no missions', () => {
    expect(hasMissionToExecute([])).toBe(false);
  });

  it('is false when every mission is finished or dropped', () => {
    expect(hasMissionToExecute([{ status: 'completed' }, { status: 'abandoned' }] as never)).toBe(false);
  });

  it('is true for a planned, active or paused mission', () => {
    expect(hasMissionToExecute([{ status: 'planned' }] as never)).toBe(true);
    expect(hasMissionToExecute([{ status: 'active' }] as never)).toBe(true);
    expect(hasMissionToExecute([{ status: 'paused' }] as never)).toBe(true);
  });
});
