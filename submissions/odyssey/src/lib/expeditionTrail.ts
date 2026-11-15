/**
 * Expedition trail helpers
 *
 * Pure functions behind the Journey page trail: turning completed missions and
 * focus sessions into waypoints, and laying those waypoints out on an SVG path
 * that gets longer as more missions are completed.
 */

import type { FocusSession, Mission } from '../types/database';

export interface Waypoint {
  mission: Mission;
  /** 1-based position on the trail, oldest completion first. */
  index: number;
  /** ISO timestamp used for sorting and for the displayed date, or null if the mission has none. */
  completedAt: string | null;
  focusMinutes: number;
  sessionCount: number;
}

export function formatMinutes(mins: number): string {
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

function toTime(value: string | null | undefined): number | null {
  if (!value) return null;
  const t = Date.parse(value);
  return Number.isNaN(t) ? null : t;
}

/** Sum duration_minutes per mission_id and count completed sessions. Sessions without a mission are ignored. */
export function focusByMission(sessions: FocusSession[]): Map<string, { minutes: number; sessions: number }> {
  const totals = new Map<string, { minutes: number; sessions: number }>();
  for (const s of sessions) {
    if (!s.mission_id) continue;
    const entry = totals.get(s.mission_id) ?? { minutes: 0, sessions: 0 };
    const mins = s.duration_minutes;
    if (typeof mins === 'number' && Number.isFinite(mins) && mins > 0) entry.minutes += mins;
    // only finished sessions count towards the session total; paused or
    // incomplete ones still add their minutes above
    if (s.completed) entry.sessions += 1;
    totals.set(s.mission_id, entry);
  }
  return totals;
}

/**
 * One waypoint per completed mission, sorted by completed_at (oldest first).
 * A completed mission with no usable completed_at still gets a waypoint; it is
 * sorted by created_at so it does not disappear from the trail.
 */
export function buildWaypoints(missions: Mission[], sessions: FocusSession[]): Waypoint[] {
  const totals = focusByMission(sessions);
  return missions
    .filter(m => m.status === 'completed')
    .map(m => ({
      mission: m,
      completedAt: toTime(m.completed_at) !== null ? (m.completed_at as string) : null,
      sortKey: toTime(m.completed_at) ?? toTime(m.created_at) ?? 0,
    }))
    .sort((a, b) => a.sortKey - b.sortKey || a.mission.id.localeCompare(b.mission.id))
    .map(({ mission, completedAt }, i) => {
      const focus = totals.get(mission.id);
      return {
        mission,
        index: i + 1,
        completedAt,
        focusMinutes: focus?.minutes ?? 0,
        sessionCount: focus?.sessions ?? 0,
      };
    });
}

// ─── Layout ──────────────────────────────────────────────────────────────────

export const TRAIL_WIDTH = 1000;
export const TRAIL_PER_ROW = 4;
export const TRAIL_ROW_HEIGHT = 220;
const TRAIL_TOP = 70;
const TRAIL_BOTTOM = 120;
const TRAIL_MARGIN_X = 125;

export interface TrailPoint {
  x: number;
  y: number;
}

export interface TrailLayout {
  /** Base Camp first, then one point per waypoint, then the "next waypoint" marker. */
  points: TrailPoint[];
  /** segments[i] is the path piece from points[i] to points[i + 1] (a "C ..." command). */
  segments: string[];
  height: number;
}

/**
 * Lay out `stops` points on a switchback path: rows of `perRow` points that
 * alternate left-to-right and right-to-left, joined by U-turns at the edges.
 * The height grows by one row for every `perRow` stops.
 */
export function layoutTrail(stops: number, perRow = TRAIL_PER_ROW): TrailLayout {
  const count = Math.max(stops, 1);
  const step = perRow > 1 ? (TRAIL_WIDTH - 2 * TRAIL_MARGIN_X) / (perRow - 1) : 0;
  const rows = Math.ceil(count / perRow);

  const points: TrailPoint[] = [];
  for (let i = 0; i < count; i++) {
    const row = Math.floor(i / perRow);
    const col = i % perRow;
    const ltr = row % 2 === 0;
    points.push({
      x: Math.round(TRAIL_MARGIN_X + (ltr ? col : perRow - 1 - col) * step),
      y: TRAIL_TOP + row * TRAIL_ROW_HEIGHT,
    });
  }

  const segments: string[] = [];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i];
    const b = points[i + 1];
    if (a.y === b.y) {
      // Same row: a gentle wave so the trail does not look ruled.
      const dx = (b.x - a.x) / 3;
      const wave = i % 2 === 0 ? 22 : -22;
      segments.push(`C ${a.x + dx} ${a.y + wave}, ${b.x - dx} ${b.y - wave}, ${b.x} ${b.y}`);
    } else {
      // Row change: U-turn bulging out past the edge the row ended on.
      const out = a.x >= TRAIL_WIDTH / 2 ? 80 : -80;
      segments.push(`C ${a.x + out} ${a.y}, ${b.x + out} ${b.y}, ${b.x} ${b.y}`);
    }
  }

  return { points, segments, height: TRAIL_TOP + (rows - 1) * TRAIL_ROW_HEIGHT + TRAIL_BOTTOM };
}

/** SVG path data for segments `from` (inclusive) to `to` (exclusive), or an empty string if there are none. */
export function pathThrough(layout: TrailLayout, from: number, to: number): string {
  const segs = layout.segments.slice(from, to);
  if (segs.length === 0) return '';
  const start = layout.points[from];
  return `M ${start.x} ${start.y} ${segs.join(' ')}`;
}
