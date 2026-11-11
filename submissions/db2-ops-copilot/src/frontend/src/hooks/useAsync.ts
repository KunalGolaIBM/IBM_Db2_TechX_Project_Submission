import { useCallback, useEffect, useRef, useState } from "react";
import { ApiClientError } from "../api/client";

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/**
 * Small data-fetching hook: loading / error / data states + manual reload.
 * `reload()` is stable; `load` runs once on mount.
 */
export function useAsync<T>(fetcher: () => Promise<T>, load = true) {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    loading: load,
    error: null,
  });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const reload = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fetcherRef.current();
      setState({ data, loading: false, error: null });
    } catch (err) {
      const message =
        err instanceof ApiClientError ? err.message : "Unexpected error";
      setState({ data: null, loading: false, error: message });
    }
  }, []);

  useEffect(() => {
    if (load) void reload();
  }, [load, reload]);

  return { ...state, reload };
}

export function errorMessage(err: unknown): string {
  if (err instanceof ApiClientError) return err.message;
  if (err instanceof Error) return err.message;
  return "Unexpected error";
}
