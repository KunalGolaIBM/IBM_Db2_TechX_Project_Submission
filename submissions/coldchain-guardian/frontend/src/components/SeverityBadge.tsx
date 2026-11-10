const colorMap: Record<string, string> = {
  CRITICAL: 'bg-red-900/40 text-red-400 border-red-700/50',
  HIGH: 'bg-orange-900/40 text-orange-400 border-orange-700/50',
  MEDIUM: 'bg-yellow-900/40 text-yellow-400 border-yellow-700/50',
  LOW: 'bg-green-900/40 text-green-400 border-green-700/50',
  OPEN: 'bg-blue-900/40 text-blue-400 border-blue-700/50',
  RESOLVED: 'bg-green-900/40 text-green-400 border-green-700/50',
  PENDING: 'bg-yellow-900/40 text-yellow-400 border-yellow-700/50',
  APPROVED: 'bg-green-900/40 text-green-400 border-green-700/50',
  REJECTED: 'bg-red-900/40 text-red-400 border-red-700/50',
  IN_TRANSIT: 'bg-blue-900/40 text-blue-400 border-blue-700/50',
  DELIVERED: 'bg-green-900/40 text-green-400 border-green-700/50',
  SUCCESS: 'bg-green-900/40 text-green-400 border-green-700/50',
  FALLBACK: 'bg-yellow-900/40 text-yellow-400 border-yellow-700/50',
  VIOLATION: 'bg-red-900/40 text-red-400 border-red-700/50',
  NORMAL: 'bg-green-900/40 text-green-400 border-green-700/50',
  AVAILABLE: 'bg-teal-900/40 text-teal-400 border-teal-700/50',
  UNAVAILABLE: 'bg-slate-800 text-slate-400 border-slate-600',
};

export default function Badge({ label }: { label: string }) {
  const cls = colorMap[label?.toUpperCase()] || 'bg-slate-800 text-slate-400 border-slate-600';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${cls}`}>
      {label}
    </span>
  );
}
