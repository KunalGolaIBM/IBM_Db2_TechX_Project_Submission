import { useTheme } from '../hooks/useTheme';

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const nextTheme = theme === 'dark' ? 'light' : 'dark';

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${nextTheme} theme`}
      title={`Switch to ${nextTheme} theme`}
      className="inline-flex items-center justify-center w-9 h-9 rounded-lg transition-all cursor-pointer border shadow-sm"
      style={{
        color: 'var(--color-app-mission)',
        backgroundColor: 'var(--color-theme-toggle-bg)',
        borderColor: 'color-mix(in srgb, var(--color-app-mission) 42%, transparent)',
        boxShadow: '0 0 0 3px var(--color-app-mission-glow), 0 3px 10px rgba(3,6,13,0.14)',
      }}
      onMouseEnter={e => { e.currentTarget.style.backgroundColor = 'var(--color-app-mission-light)'; }}
      onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'var(--color-theme-toggle-bg)'; }}
    >
      {theme === 'dark' ? (
        <svg className="w-[1.1rem] h-[1.1rem]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path strokeLinecap="round" d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3l1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3l1.42-1.42" />
        </svg>
      ) : (
        <svg className="w-[1.1rem] h-[1.1rem]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.9} aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" d="M20.5 14.7A8.5 8.5 0 1 1 9.3 3.5 6.7 6.7 0 0 0 20.5 14.7Z" />
        </svg>
      )}
    </button>
  );
}