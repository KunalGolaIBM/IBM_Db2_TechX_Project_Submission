import type { Gate, Severity } from './api';

export const SEVERITIES: Severity[] = ['critical', 'high', 'medium', 'low'];

export const SEV_COLOR: Record<Severity, string> = {
  critical: '#ff5c66',
  high: '#ff8f3d',
  medium: '#f1c21b',
  low: '#78a9ff',
  info: '#94a1bb',
};

export const GATE_META: Record<Gate, { label: string; color: string; tone: string }> = {
  BLOCKED: { label: 'Blocked', color: '#ff5c66', tone: 'text-sev-critical bg-sev-critical/10 ring-sev-critical/30' },
  PASS_WITH_WARNINGS: { label: 'Pass · warnings', color: '#f1c21b', tone: 'text-sev-medium bg-sev-medium/10 ring-sev-medium/30' },
  PASS: { label: 'Pass', color: '#42d392', tone: 'text-ok bg-ok/10 ring-ok/30' },
};

export function timeAgo(ms: number): string {
  const s = Math.max(1, Math.round((Date.now() - ms) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ago`;
  return new Date(ms).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function dateTime(ms: number): string {
  return new Date(ms).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function duration(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

export function riskScore(c: number, h: number, m: number, l: number) {
  return c * 10 + h * 5 + m * 2 + l;
}
