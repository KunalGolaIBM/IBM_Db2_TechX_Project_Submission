import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Home, Music, Library, BookOpen, BarChart2,
  Music2, Settings, Bell,
} from 'lucide-react';
import BottomPlayer from './BottomPlayer';

interface NavItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  path: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'home',        label: 'Home',       icon: <Home size={18} />,     path: '/home' },
  { id: 'now-playing', label: 'Now Playing', icon: <Music size={18} />,    path: '/now-playing' },
  { id: 'library',     label: 'My Library', icon: <Library size={18} />,  path: '/library' },
  { id: 'memories',    label: 'Memories',   icon: <BookOpen size={18} />, path: '/memories' },
  { id: 'analytics',   label: 'Analytics',  icon: <BarChart2 size={18} />,path: '/analytics' },
];

interface AppShellProps {
  children: React.ReactNode;
}

const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        fontFamily: "'Inter', sans-serif",
      }}
    >
      {/* ── Cinematic background ── */}
      <div
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 0,
          background: [
            'radial-gradient(ellipse 60% 55% at 20% 100%, rgba(255,145,40,0.18) 0%, transparent 65%)',
            'radial-gradient(ellipse 30% 40% at 18% 105%, rgba(255,100,20,0.14) 0%, transparent 55%)',
            'radial-gradient(ellipse 22% 50% at 90% 0%,  rgba(180,210,255,0.14) 0%, transparent 65%)',
            'radial-gradient(ellipse 65% 45% at 50% 35%, rgba(80,40,160,0.16)  0%, transparent 70%)',
            'linear-gradient(to top, rgba(4,2,14,0.80) 0%, transparent 40%)',
            'linear-gradient(155deg, #09071a 0%, #110d2e 55%, #1a0a2e 100%)',
          ].join(', '),
        }}
      />

      {/* ── Main layout ── */}
      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* ════ SIDEBAR ════ */}
        <aside
          style={{
            width: 220,
            flexShrink: 0,
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            background: 'rgba(10,8,28,0.72)',
            borderRight: '1px solid rgba(255,255,255,0.07)',
            backdropFilter: 'blur(20px)',
          }}
        >
          {/* Logo */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '20px 20px 18px',
              borderBottom: '1px solid rgba(255,255,255,0.06)',
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 10,
                background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                boxShadow: '0 4px 14px rgba(124,58,237,0.5)',
              }}
            >
              <Music2 size={16} color="#fff" />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#fff', lineHeight: 1.2 }}>
                MoodTunes
              </div>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', marginTop: 1 }}>
                Music Memory
              </div>
            </div>
          </div>

          {/* Nav */}
          <nav style={{ flex: 1, padding: '12px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: 'rgba(255,255,255,0.25)', padding: '6px 10px 8px', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Menu
            </div>
            {NAV_ITEMS.map(item => {
              const isActive = location.pathname === item.path || (location.pathname === '/' && item.path === '/home');
              return (
                <button
                  key={item.id}
                  onClick={() => navigate(item.path)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 12,
                    padding: '10px 12px',
                    borderRadius: 10,
                    border: 'none',
                    background: isActive ? 'rgba(168,85,247,0.18)' : 'transparent',
                    color: isActive ? '#c084fc' : 'rgba(255,255,255,0.50)',
                    fontSize: 13,
                    fontWeight: isActive ? 600 : 400,
                    cursor: 'pointer',
                    textAlign: 'left',
                    width: '100%',
                    transition: 'all 0.15s',
                    position: 'relative',
                  }}
                  onMouseEnter={e => {
                    if (!isActive) {
                      (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.05)';
                      (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.80)';
                    }
                  }}
                  onMouseLeave={e => {
                    if (!isActive) {
                      (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                      (e.currentTarget as HTMLButtonElement).style.color = 'rgba(255,255,255,0.50)';
                    }
                  }}
                >
                  {isActive && (
                    <span
                      style={{
                        position: 'absolute',
                        left: 0,
                        top: '20%',
                        bottom: '20%',
                        width: 3,
                        borderRadius: '0 3px 3px 0',
                        background: '#a855f7',
                        boxShadow: '0 0 8px rgba(168,85,247,0.6)',
                      }}
                    />
                  )}
                  <span style={{ color: isActive ? '#c084fc' : 'inherit', display: 'flex', alignItems: 'center' }}>
                    {item.icon}
                  </span>
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Bottom sidebar */}
          <div
            style={{
              padding: '12px 10px',
              borderTop: '1px solid rgba(255,255,255,0.06)',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            <button
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '9px 12px', borderRadius: 10, border: 'none',
                background: 'transparent', color: 'rgba(255,255,255,0.40)',
                fontSize: 13, cursor: 'pointer', textAlign: 'left', width: '100%',
              }}
            >
              <Settings size={16} />
              Settings
            </button>
          </div>
        </aside>

        {/* ════ RIGHT SIDE ════ */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {/* ── HEADER ── */}
          <header
            style={{
              height: 58,
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0 28px',
              background: 'rgba(10,8,28,0.60)',
              borderBottom: '1px solid rgba(255,255,255,0.07)',
              backdropFilter: 'blur(20px)',
            }}
          >
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#fff' }}>
                {NAV_ITEMS.find(n => location.pathname.startsWith(n.path))?.label ?? 'Home'}
              </div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', marginTop: 1 }}>
                Good evening, Tushar 👋
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <button
                style={{
                  width: 34, height: 34, borderRadius: 10, border: '1px solid rgba(255,255,255,0.10)',
                  background: 'rgba(255,255,255,0.05)', color: 'rgba(255,255,255,0.55)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer',
                }}
              >
                <Bell size={15} />
              </button>
              <div
                style={{
                  width: 34, height: 34, borderRadius: 10,
                  background: 'linear-gradient(135deg, #7c3aed, #a855f7)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontWeight: 700, color: '#fff', cursor: 'pointer',
                  boxShadow: '0 4px 12px rgba(124,58,237,0.4)',
                }}
              >
                T
              </div>
            </div>
          </header>

          {/* ── PAGE CONTENT ── */}
          <main
            style={{
              flex: 1,
              overflowY: 'auto',
              overflowX: 'hidden',
              padding: '28px 28px 0',
              scrollbarWidth: 'thin',
              scrollbarColor: 'rgba(168,85,247,0.3) transparent',
            }}
          >
            {children}
          </main>

          {/* ── BOTTOM PLAYER ── */}
          <BottomPlayer onNavigatePlayer={() => navigate('/now-playing')} />
        </div>
      </div>
    </div>
  );
};

export default AppShell;

