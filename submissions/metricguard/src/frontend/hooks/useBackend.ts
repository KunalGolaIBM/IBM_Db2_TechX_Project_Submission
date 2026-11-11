"use client";

import { getExamples, getHealth, getMetrics } from "@/lib/api/client";
import { useAsync } from "./useAsync";

/** Health is the only source for the "connected" indicator. Polled every 30 s. */
export const useHealth = () => useAsync((s) => getHealth(s), [], 30_000);
export const useCatalog = () => useAsync((s) => getMetrics(s), []);
export const useExamples = () => useAsync((s) => getExamples(s), []);
