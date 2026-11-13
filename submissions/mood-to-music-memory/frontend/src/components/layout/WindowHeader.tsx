import React from 'react';
import { Music, Minus, X } from 'lucide-react';

interface WindowHeaderProps {
  title: string;
  icon?: React.ReactNode;
  onMinimize?: () => void;
  onClose?: () => void;
}

const WindowHeader: React.FC<WindowHeaderProps> = ({ title, icon, onMinimize, onClose }) => {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '10px 16px',
        background: 'rgba(255,255,255,0.03)',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        flexShrink: 0,
      }}
    >
      {/* Left: icon + title */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ color: '#a855f7', display: 'flex', alignItems: 'center' }}>
          {icon ?? <Music size={15} />}
        </span>
        <span
          style={{
            fontSize: 13,
            fontWeight: 500,
            color: 'rgba(255,255,255,0.90)',
            letterSpacing: '0.01em',
          }}
        >
          {title}
        </span>
      </div>

      {/* Right: minimize + close */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        {onMinimize && (
          <button
            onClick={onMinimize}
            aria-label="Minimize"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 22,
              height: 22,
              borderRadius: 4,
              border: 'none',
              background: 'transparent',
              color: 'rgba(255,255,255,0.45)',
              cursor: 'pointer',
              transition: 'background 0.15s, color 0.15s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.08)';
              (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.85)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
              (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.45)';
            }}
          >
            <Minus size={12} />
          </button>
        )}
        {onClose && (
          <button
            onClick={onClose}
            aria-label="Close"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 22,
              height: 22,
              borderRadius: 4,
              border: 'none',
              background: 'transparent',
              color: 'rgba(255,255,255,0.45)',
              cursor: 'pointer',
              transition: 'background 0.15s, color 0.15s',
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = 'rgba(239,68,68,0.18)';
              (e.currentTarget as HTMLButtonElement).style.color = 'rgba(239,100,100,1)';
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
              (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.45)';
            }}
          >
            <X size={12} />
          </button>
        )}
      </div>
    </div>
  );
};

export default WindowHeader;
