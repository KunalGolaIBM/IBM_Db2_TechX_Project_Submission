import { createContext, useContext, useEffect, useState } from 'react';

export type Theme = 'dark' | 'light';

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
}

const THEME_STORAGE_KEY = 'odyssey-theme';
const DARK_SCHEME_QUERY = '(prefers-color-scheme: dark)';
const ThemeContext = createContext<ThemeContextValue | null>(null);

function getStoredTheme(): Theme | null {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  return stored === 'light' || stored === 'dark' ? stored : null;
}

function getSystemMediaQuery(): MediaQueryList | null {
  return typeof window.matchMedia === 'function' ? window.matchMedia(DARK_SCHEME_QUERY) : null;
}

function getSystemTheme(): Theme {
  const mediaQuery = getSystemMediaQuery();
  if (!mediaQuery) return 'dark';
  return mediaQuery.matches ? 'dark' : 'light';
}

function resolveTheme(): Theme {
  return getStoredTheme() ?? getSystemTheme();
}


export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(resolveTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    const syncTheme = () => setTheme(resolveTheme());

    const handleStorage = (event: StorageEvent) => {
      if (event.key === THEME_STORAGE_KEY || event.key === null) syncTheme();
    };

    const mediaQuery = getSystemMediaQuery();
    mediaQuery?.addEventListener('change', syncTheme);
    window.addEventListener('storage', handleStorage);

    syncTheme();

    return () => {
      mediaQuery?.removeEventListener('change', syncTheme);
      window.removeEventListener('storage', handleStorage);
    };
  }, []);

  const toggleTheme = () => {
    const nextTheme: Theme = theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    setTheme(nextTheme);
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme must be used within ThemeProvider');
  return context;
}