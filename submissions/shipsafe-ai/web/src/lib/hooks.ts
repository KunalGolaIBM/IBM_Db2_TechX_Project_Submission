import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from './api';

/** Fetch a JSON resource; optional polling interval in ms. */
export function useApi<T>(path: string | null, pollMs?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  const alive = useRef(true);

  const load = useCallback(async () => {
    if (!path) return;
    try {
      const res = await api<T>(path);
      if (alive.current) {
        setData(res);
        setError(null);
      }
    } catch (e) {
      if (alive.current) setError(e as Error);
    } finally {
      if (alive.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => {
    alive.current = true;
    setLoading(!!path);
    load();
    if (!pollMs || !path) return () => { alive.current = false; };
    const id = window.setInterval(load, pollMs);
    return () => {
      alive.current = false;
      window.clearInterval(id);
    };
  }, [path, pollMs, load]);

  return { data, error, loading, reload: load, setData };
}

export function useHotkey(key: string, handler: (e: KeyboardEvent) => void, opts: { meta?: boolean } = {}) {
  useEffect(() => {
    const fn = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable);
      if (opts.meta) {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === key) handler(e);
      } else if (!typing && !e.metaKey && !e.ctrlKey && !e.altKey && e.key.toLowerCase() === key) {
        handler(e);
      }
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [key, handler, opts.meta]);
}
