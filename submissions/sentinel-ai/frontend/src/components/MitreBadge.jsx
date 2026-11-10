import React from 'react';
import { ExternalLink, Shield } from 'lucide-react';

export default function MitreBadge({ techniqueId, name, tactic }) {
  const getBadgeStyle = (id) => {
    switch (id) {
      case 'T1110.001':
      case 'T1110':
        return 'bg-amber-950/80 text-amber-300 border-amber-800/80';
      case 'T1078.002':
      case 'T1078':
        return 'bg-rose-950/80 text-rose-300 border-rose-800/80';
      case 'T1530':
        return 'bg-purple-950/80 text-purple-300 border-purple-800/80';
      case 'T1021':
        return 'bg-blue-950/80 text-blue-300 border-blue-800/80';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  const url = `https://attack.mitre.org/techniques/${techniqueId.replace('.', '/')}/`;

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded text-xs font-mono-code border transition-all hover:scale-105 ${getBadgeStyle(techniqueId)}`}
      title={name ? `${name} (${tactic})` : `MITRE Technique ${techniqueId}`}
    >
      <Shield className="w-3 h-3" />
      <span className="font-bold">{techniqueId}</span>
      {name && <span className="opacity-90 font-sans text-[11px] truncate max-w-[120px]">{name}</span>}
      <ExternalLink className="w-2.5 h-2.5 opacity-60" />
    </a>
  );
}

