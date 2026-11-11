"use client";

import { CloudOff, RotateCw, ServerCrash, TimerOff, TriangleAlert } from "lucide-react";
import type { ApiError } from "@/lib/api/client";
import { API_BASE_URL } from "@/lib/api/client";

const COPY: Record<ApiError["kind"], { title: string; icon: typeof CloudOff; body: string }> = {
  network: { title: "Cannot reach the MetricGuard API", icon: CloudOff, body: `The browser could not connect to ${API_BASE_URL}. Start the backend (make api) and retry.` },
  timeout: { title: "The request timed out", icon: TimerOff, body: "The backend did not answer in time. Nothing was verified. Try again." },
  planner_unavailable: { title: "AI planner unavailable", icon: ServerCrash, body: "The language-model planner could not be used. MetricGuard does not silently switch to the demo planner, so no analysis was run." },
  db_unavailable: { title: "IBM Db2 is unavailable", icon: ServerCrash, body: "The backend reports that the database cannot be reached." },
  not_found: { title: "Not found", icon: TriangleAlert, body: "The backend has no such record." },
  invalid_request: { title: "The question was not accepted", icon: TriangleAlert, body: "The API rejected the request." },
  server: { title: "The backend returned an error", icon: ServerCrash, body: "Something went wrong on the server." },
  malformed: { title: "Unexpected response", icon: TriangleAlert, body: "The backend answered, but not in the documented format. The result was discarded rather than shown." },
};

export function TransportError({ error, onRetry, testId = "transport-error" }: { error: ApiError; onRetry?: () => void; testId?: string }) {
  const c = COPY[error.kind];
  const Icon = c.icon;
  return (
    <div role="alert" data-testid={testId} data-kind={error.kind} className="rounded-2xl border border-bad/25 bg-surface p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-bad-soft text-bad"><Icon aria-hidden className="size-5" /></span>
        <div className="min-w-0">
          <h2 className="text-[20px] font-semibold tracking-tight">{c.title}</h2>
          <p className="mt-0.5 text-[16px] text-ink-2">{c.body}</p>
          {error.message && error.kind !== "network" && error.kind !== "timeout" && <p className="mt-2 break-words font-mono text-[13px] text-ink-3">{error.code ? `${error.code}: ` : ""}{error.message}</p>}
          {error.details && error.details.length > 0 && <ul className="mt-1 list-disc pl-5 text-[14px] text-ink-3">{error.details.map((d) => <li key={d}>{d}</li>)}</ul>}
        </div>
      </div>
      {onRetry && (
        <button type="button" onClick={onRetry} data-testid="retry-transport" className="mt-4 inline-flex items-center gap-2 rounded-xl border border-line-strong bg-white px-4 py-2.5 text-[15px] font-semibold hover:border-ink hover:bg-sunken">
          <RotateCw aria-hidden className="size-4" /> Retry
        </button>
      )}
    </div>
  );
}
