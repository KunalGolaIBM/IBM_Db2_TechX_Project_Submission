import React from 'react';

interface Props {
  severity: string;
}

export const SeverityBadge: React.FC<Props> = ({ severity }) => {
  const s = severity?.toUpperCase() || 'LOW';
  let bg = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';

  if (s === 'CRITICAL') {
    bg = 'bg-red-500/10 text-red-400 border-red-500/30';
  } else if (s === 'HIGH') {
    bg = 'bg-rose-500/10 text-rose-400 border-rose-500/30';
  } else if (s === 'MEDIUM') {
    bg = 'bg-amber-500/10 text-amber-400 border-amber-500/30';
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${bg}`}>
      {s}
    </span>
  );
};
