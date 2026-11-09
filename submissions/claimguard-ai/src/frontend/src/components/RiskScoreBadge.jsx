import React from 'react';

export default function RiskScoreBadge({ score, level }) {
  const numScore = parseFloat(score || 0);

  let bg = 'bg-emerald-50 text-emerald-800 border-emerald-300';
  let label = level || 'LOW';

  if (numScore > 75 || label === 'CRITICAL') {
    bg = 'bg-red-50 text-red-800 border-red-300';
    label = 'CRITICAL';
  } else if (numScore > 50 || label === 'HIGH') {
    bg = 'bg-orange-50 text-orange-800 border-orange-300';
    label = 'HIGH';
  } else if (numScore > 25 || label === 'MEDIUM') {
    bg = 'bg-amber-50 text-amber-800 border-amber-300';
    label = 'MEDIUM';
  } else {
    bg = 'bg-emerald-50 text-emerald-800 border-emerald-300';
    label = 'LOW';
  }

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold border ${bg}`}>
      <span>{numScore.toFixed(1)} / 100</span>
      <span className="mx-1">•</span>
      <span>{label}</span>
    </span>
  );
}
