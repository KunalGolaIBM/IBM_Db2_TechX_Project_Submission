export function toNumber(value: string | number | null | undefined): number {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0;
  const parsed = Number.parseFloat(String(value ?? ''));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function utilizationOf(
  currentLoad: string | number,
  capacity: string | number,
): number {
  const cap = toNumber(capacity);
  if (!cap) return 0;
  return (toNumber(currentLoad) / cap) * 100;
}

export type UtilizationBandKey = 'normal' | 'warning' | 'critical' | 'overcapacity';

export interface UtilizationBand {
  key: UtilizationBandKey;
  label: string;
  shortLabel: string;
  color: string;
  barClass: string;
  chipClass: string;
}

export function utilizationBand(utilization: number): UtilizationBand {
  if (utilization >= 100) {
    return {
      key: 'overcapacity',
      label: 'Overcapacity',
      shortLabel: 'OVERCAP',
      color: '#E11D48',
      barClass: 'bg-rose-600',
      chipClass: 'border-rose-500/35 bg-rose-500/10 text-rose-300',
    };
  }
  if (utilization >= 90) {
    return {
      key: 'critical',
      label: 'Critical',
      shortLabel: 'CRITICAL',
      color: '#EF4444',
      barClass: 'bg-red-500',
      chipClass: 'border-red-500/35 bg-red-500/10 text-red-300',
    };
  }
  if (utilization >= 80) {
    return {
      key: 'warning',
      label: 'Warning',
      shortLabel: 'WARNING',
      color: '#F59E0B',
      barClass: 'bg-amber-400',
      chipClass: 'border-amber-400/35 bg-amber-400/10 text-amber-200',
    };
  }
  return {
    key: 'normal',
    label: 'Normal',
    shortLabel: 'NORMAL',
    color: '#10B981',
    barClass: 'bg-emerald-400',
    chipClass: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300',
  };
}

export interface RiskStyle {
  label: string;
  color: string;
  textClass: string;
  chipClass: string;
  dotClass: string;
}

export function riskStyle(risk: string | null | undefined): RiskStyle {
  const normalized = (risk ?? '').toUpperCase();
  if (normalized === 'HIGH') {
    return {
      label: 'HIGH',
      color: '#F87171',
      textClass: 'text-red-300',
      chipClass: 'border-red-500/40 bg-red-500/10 text-red-300',
      dotClass: 'bg-red-400',
    };
  }
  if (normalized === 'MODERATE') {
    return {
      label: 'MODERATE',
      color: '#FBBF24',
      textClass: 'text-amber-200',
      chipClass: 'border-amber-400/40 bg-amber-400/10 text-amber-200',
      dotClass: 'bg-amber-300',
    };
  }
  if (normalized === 'LOW') {
    return {
      label: 'LOW',
      color: '#34D399',
      textClass: 'text-emerald-300',
      chipClass: 'border-emerald-400/40 bg-emerald-400/10 text-emerald-300',
      dotClass: 'bg-emerald-400',
    };
  }
  return {
    label: 'PENDING',
    color: '#64748B',
    textClass: 'text-slate-400',
    chipClass: 'border-slate-500/40 bg-slate-500/10 text-slate-400',
    dotClass: 'bg-slate-500',
  };
}

export function severityChip(severity: string): string {
  switch ((severity ?? '').toUpperCase()) {
    case 'CRITICAL':
      return 'border-rose-500/40 bg-rose-500/10 text-rose-300';
    case 'HIGH':
      return 'border-red-500/40 bg-red-500/10 text-red-300';
    case 'MEDIUM':
      return 'border-amber-400/40 bg-amber-400/10 text-amber-200';
    case 'LOW':
      return 'border-sky-400/40 bg-sky-400/10 text-sky-300';
    default:
      return 'border-slate-500/40 bg-slate-500/10 text-slate-400';
  }
}

export function statusChip(status: string): string {
  const normalized = (status ?? '').toUpperCase();
  if (normalized === 'ONLINE' || normalized === 'OPEN' || normalized === 'HEALTHY' || normalized === 'CONNECTED') {
    return 'border-emerald-400/35 bg-emerald-400/10 text-emerald-300';
  }
  if (normalized === 'OFFLINE' || normalized === 'CRITICAL' || normalized === 'DISCONNECTED') {
    return 'border-red-500/40 bg-red-500/10 text-red-300';
  }
  if (normalized === 'DEGRADED' || normalized === 'MAINTENANCE' || normalized === 'WARNING') {
    return 'border-amber-400/40 bg-amber-400/10 text-amber-200';
  }
  if (normalized === 'CLOSED' || normalized === 'RESOLVED' || normalized === 'ACKNOWLEDGED') {
    return 'border-slate-500/40 bg-slate-500/10 text-slate-400';
  }
  return 'border-sky-400/35 bg-sky-400/10 text-sky-300';
}

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return '—';
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

export function formatTime(value: string | Date | null | undefined): string {
  if (!value) return '—';
  const date = typeof value === 'string' ? new Date(value) : value;
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

export function formatNumber(value: number, digits = 0): string {
  return new Intl.NumberFormat(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatMw(value: string | number, digits = 0): string {
  return `${formatNumber(toNumber(value), digits)} MW`;
}

export function average(values: number[]): number {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}
