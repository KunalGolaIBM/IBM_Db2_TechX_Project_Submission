import { describe, expect, it } from 'vitest';
import type { FocusSession, Mission } from '../types/database';
import {
  TRAIL_PER_ROW,
  TRAIL_ROW_HEIGHT,
  buildWaypoints,
  focusByMission,
  formatMinutes,
  layoutTrail,
  pathThrough,
} from './expeditionTrail';

function mission(id: string, over: Partial<Mission> = {}): Mission {
  return {
    id,
    user_id: 'u1',
    task_id: null,
    title: `Mission ${id}`,
    objective: null,
    next_action: null,
    planned_minutes: 25,
    status: 'completed',
    started_at: null,
    completed_at: '2026-01-10T10:00:00.000Z',
    created_at: '2026-01-01T10:00:00.000Z',
    ...over,
  };
}

function session(id: string, missionId: string | null, minutes: number | null, completed = true): FocusSession {
  return {
    id,
    user_id: 'u1',
    mission_id: missionId,
    started_at: '2026-01-10T09:00:00.000Z',
    ended_at: null,
    duration_minutes: minutes,
    completed,
    created_at: '2026-01-10T09:00:00.000Z',
  };
}

describe('focusByMission', () => {
  it('sums duration_minutes per mission and ignores sessions without a mission', () => {
    const totals = focusByMission([
      session('s1', 'a', 25),
      session('s2', 'a', 30),
      session('s3', 'b', 10),
      session('s4', null, 99),
    ]);
    expect(totals.get('a')).toEqual({ minutes: 55, sessions: 2 });
    expect(totals.get('b')).toEqual({ minutes: 10, sessions: 1 });
    expect(totals.size).toBe(2);
  });

  it('treats missing, negative and non-finite durations as zero minutes', () => {
    const totals = focusByMission([session('s1', 'a', null), session('s2', 'a', -5), session('s3', 'a', NaN), session('s4', 'a', 20)]);
    expect(totals.get('a')).toEqual({ minutes: 20, sessions: 4 });
  });

  it('only counts completed sessions in the session total but still adds their minutes', () => {
    const totals = focusByMission([session('s1', 'a', 25), session('s2', 'a', 10, false), session('s3', 'a', 5, false)]);
    expect(totals.get('a')).toEqual({ minutes: 40, sessions: 1 });
  });
});

describe('buildWaypoints', () => {
  it('only uses completed missions and sorts them by completed_at, oldest first', () => {
    const wps = buildWaypoints(
      [
        mission('late', { completed_at: '2026-03-01T00:00:00.000Z' }),
        mission('active', { status: 'active', completed_at: null }),
        mission('early', { completed_at: '2026-01-05T00:00:00.000Z' }),
        mission('abandoned', { status: 'abandoned' }),
        mission('mid', { completed_at: '2026-02-01T00:00:00.000Z' }),
      ],
      [],
    );
    expect(wps.map(w => w.mission.id)).toEqual(['early', 'mid', 'late']);
    expect(wps.map(w => w.index)).toEqual([1, 2, 3]);
  });

  it('attaches focus minutes and session counts from matching mission_id', () => {
    const wps = buildWaypoints(
      [mission('a'), mission('b', { completed_at: '2026-01-11T00:00:00.000Z' })],
      [session('s1', 'a', 25), session('s2', 'a', 20), session('s3', 'other', 40)],
    );
    expect(wps[0]).toMatchObject({ focusMinutes: 45, sessionCount: 2 });
    expect(wps[1]).toMatchObject({ focusMinutes: 0, sessionCount: 0 });
  });

  it('keeps a completed mission with no completed_at, sorted by created_at', () => {
    const wps = buildWaypoints(
      [
        mission('dated', { completed_at: '2026-01-10T00:00:00.000Z' }),
        mission('undated', { completed_at: null, created_at: '2026-01-02T00:00:00.000Z' }),
      ],
      [],
    );
    expect(wps.map(w => w.mission.id)).toEqual(['undated', 'dated']);
    expect(wps[0].completedAt).toBeNull();
  });

  it('returns nothing when there are no completed missions', () => {
    expect(buildWaypoints([mission('a', { status: 'planned', completed_at: null })], [])).toEqual([]);
  });
});

describe('layoutTrail', () => {
  it('puts one point per stop and one segment between each pair', () => {
    const layout = layoutTrail(7);
    expect(layout.points).toHaveLength(7);
    expect(layout.segments).toHaveLength(6);
  });

  it('grows taller by one row for every full row of stops', () => {
    const one = layoutTrail(TRAIL_PER_ROW);
    const two = layoutTrail(TRAIL_PER_ROW + 1);
    const three = layoutTrail(TRAIL_PER_ROW * 2 + 1);
    expect(two.height - one.height).toBe(TRAIL_ROW_HEIGHT);
    expect(three.height - two.height).toBe(TRAIL_ROW_HEIGHT);
  });

  it('snakes: the second row runs right to left and starts under the end of the first', () => {
    const { points } = layoutTrail(TRAIL_PER_ROW * 2);
    const firstRow = points.slice(0, TRAIL_PER_ROW);
    const secondRow = points.slice(TRAIL_PER_ROW);
    expect(firstRow.map(p => p.x)).toEqual([...firstRow.map(p => p.x)].sort((a, b) => a - b));
    expect(secondRow.map(p => p.x)).toEqual([...secondRow.map(p => p.x)].sort((a, b) => b - a));
    expect(secondRow[0].x).toBe(firstRow[TRAIL_PER_ROW - 1].x);
  });

  it('builds path data for a range of segments and nothing for an empty range', () => {
    const layout = layoutTrail(4);
    const d = pathThrough(layout, 0, 2);
    expect(d.startsWith(`M ${layout.points[0].x} ${layout.points[0].y} C`)).toBe(true);
    expect(d.match(/C /g)).toHaveLength(2);
    expect(pathThrough(layout, 0, 0)).toBe('');
  });
});

describe('formatMinutes', () => {
  it.each([[0, '0m'], [45, '45m'], [60, '1h'], [75, '1h 15m']])('formats %i as %s', (mins, out) => {
    expect(formatMinutes(mins)).toBe(out);
  });
});
