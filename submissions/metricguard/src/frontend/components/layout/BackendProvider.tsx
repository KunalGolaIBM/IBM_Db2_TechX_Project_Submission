"use client";

import { createContext, useContext } from "react";
import { useCatalog, useExamples, useHealth } from "@/hooks/useBackend";
import type { AsyncState } from "@/hooks/useAsync";
import type { ExamplesResponse, HealthResponse, MetricsResponse } from "@/lib/api/types";

interface Backend {
  health: AsyncState<HealthResponse>;
  catalog: AsyncState<MetricsResponse>;
  examples: AsyncState<ExamplesResponse>;
}

const Ctx = createContext<Backend | null>(null);

/** Loads health, the metric catalog and the example questions once, from the real backend. */
export function BackendProvider({ children }: { children: React.ReactNode }) {
  const health = useHealth();
  const catalog = useCatalog();
  const examples = useExamples();
  return <Ctx.Provider value={{ health, catalog, examples }}>{children}</Ctx.Provider>;
}

export function useBackend(): Backend {
  const v = useContext(Ctx);
  if (!v) throw new Error("useBackend must be used inside <BackendProvider>");
  return v;
}
