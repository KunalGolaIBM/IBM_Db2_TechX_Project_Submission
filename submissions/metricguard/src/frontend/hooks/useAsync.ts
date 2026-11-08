"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api/client";

export interface AsyncState<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
}

/** Fetch on mount (and when `deps` change), cancel on unmount, optional polling. */
export function useAsync<T>(fn: (signal: AbortSignal) => Promise<T>, deps: unknown[], pollMs?: number): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const fnRef = useRef(fn);
  useEffect(() => { fnRef.current = fn; });

  useEffect(() => {
    const ctrl = new AbortController();
    let first = true;
    const run = async () => {
      if (first) setLoading(true);
      try {
        const result = await fnRef.current(ctrl.signal);
        if (ctrl.signal.aborted) return;
        setData(result);
        setError(null);
      } catch (err) {
        if (ctrl.signal.aborted) return;
        setError(err instanceof ApiError ? err : new ApiError("server", err instanceof Error ? err.message : "Unknown error"));
      } finally {
        if (!ctrl.signal.aborted) setLoading(false);
        first = false;
      }
    };
    void run();
    const id = pollMs ? setInterval(() => void run(), pollMs) : undefined;
    return () => { ctrl.abort(); if (id) clearInterval(id); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick, pollMs]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data, error, loading, reload };
}
