import React from 'react';
import { Home, Music, Library, BookOpen, BarChart2 } from 'lucide-react';

interface SidebarItem {
  id: string;
  label: string;
  icon: React.ReactNode;
}

const ITEMS: SidebarItem[] = [
  { id: 'Home',       label: 'Home',    icon: <Home size={18} /> },
  { id: 'NowPlaying', label: 'Playing', icon: <Music size={18} /> },
  { id: 'Library',    label: 'Library', icon: <Library size={18} /> },
  { id: 'Memory',     label: 'Memory',  icon: <BookOpen size={18} /> },
  { id: 'Analytics',  label: 'Stats',   icon: <BarChart2 size={18} /> },
];

interface SidebarProps {
  activeItem: string;
  onSelect: (item: string) => void;
}

const Sidebar: React.FC<SidebarProps> = ({ activeItem, onSelect }) => {
  return (
    <div
      style={{
        width: 56,
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '8px 0',
        gap: 2,
        background: 'rgba(255,255,255,0.025)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        flexShrink: 0,
      }}
    >
      {ITEMS.map(item => {
        const isActive = activeItem === item.id;
        return (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            aria-label={item.label}
            aria-current={isActive ? 'page' : undefined}
            style={{
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '8px 0',
              gap: 3,
              border: 'none',
              borderLeft: isActive ? '2px solid #a855f7' : '2px solid transparent',
              borderRadius: 0,
              background: isActive ? 'rgba(168,85,247,0.18)' : 'transparent',
              color: isActive ? '#c084fc' : 'rgba(255,255,255,0.40)',
              cursor: 'pointer',
              transition: 'background 0.15s, color 0.15s, border-color 0.15s',
            }}
            onMouseEnter={e => {
              if (!isActive) {
                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.05)';
                (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.70)';
              }
            }}
            onMouseLeave={e => {
              if (!isActive) {
                (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.40)';
              }
            }}
          >
            {item.icon}
            <span style={{ fontSize: 9, lineHeight: 1, letterSpacing: '0.02em' }}>{item.label}</span>
          </button>
        );
      })}
    </div>
  );
};

export default Sidebar;
