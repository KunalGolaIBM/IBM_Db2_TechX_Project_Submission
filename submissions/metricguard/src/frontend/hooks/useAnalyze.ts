"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { analyze, ApiError } from "@/lib/api/client";
import type { AnalyzeResponse } from "@/lib/api/types";

export type AnalyzePhase = "idle" | "loading" | "done" | "error";

export interface AnalyzeState {
  phase: AnalyzePhase;
  response: AnalyzeResponse | null;
  error: ApiError | null;
  question: string;
  elapsedMs: number;
}

const INITIAL: AnalyzeState = { phase: "idle", response: null, error: null, question: "", elapsedMs: 0 };

/**
 * One analysis at a time. A second `submit` while one is in flight is ignored (duplicate protection);
 * `cancel` aborts the request.
 */
export function useAnalyze() {
  const [state, setState] = useState<AnalyzeState>(INITIAL);
  const inFlight = useRef<AbortController | null>(null);
  const startedAt = useRef(0);

  useEffect(() => {
    if (state.phase !== "loading") return;
    const id = setInterval(() => setState((s) => (s.phase === "loading" ? { ...s, elapsedMs: performance.now() - startedAt.current } : s)), 500);
    return () => clearInterval(id);
  }, [state.phase]);

  useEffect(() => () => inFlight.current?.abort(), []);

  const submit = useCallback(async (question: string) => {
    const q = question.trim();
    if (q.length < 3 || inFlight.current) return;
    const ctrl = new AbortController();
    inFlight.current = ctrl;
    startedAt.current = performance.now();
    setState({ phase: "loading", response: null, error: null, question: q, elapsedMs: 0 });
    try {
      const response = await analyze(q, ctrl.signal);
      setState({ phase: "done", response, error: null, question: q, elapsedMs: performance.now() - startedAt.current });
    } catch (err) {
      if (ctrl.signal.aborted) { setState(INITIAL); }
      else {
        const error = err instanceof ApiError ? err : new ApiError("server", "Unexpected error.");
        setState({ phase: "error", response: null, error, question: q, elapsedMs: performance.now() - startedAt.current });
      }
    } finally {
      inFlight.current = null;
    }
  }, []);

  const cancel = useCallback(() => inFlight.current?.abort(), []);
  const reset = useCallback(() => setState(INITIAL), []);

  return { ...state, submit, cancel, reset };
}
