"use client";

import { ArrowRight, Ban, PencilLine, RotateCw, ServerCrash } from "lucide-react";
import type { AnalyzeResponse } from "@/lib/api/types";
import { useBackend } from "@/components/layout/BackendProvider";

const btn = "inline-flex items-center gap-2 rounded-xl border border-line-strong bg-white px-4 py-2.5 text-[15px] font-semibold text-ink transition-colors hover:border-ink hover:bg-sunken";

/** AMBIGUOUS: nothing executed; offer each clarification as a verbatim re-submit. */
export function AmbiguousPanel({ r, onAsk, onEdit }: { r: AnalyzeResponse; onAsk: (q: string) => void; onEdit: () => void }) {
  const c = r.clarification;
  const warnings = r.verification.reasons;
  return (
    <section aria-label="Clarification needed" className="rounded-2xl border border-amb/25 bg-surface p-5 sm:p-6" data-testid="ambiguous-panel">
      <p className="text-[14px] font-medium text-amb">Why this is ambiguous</p>
      <ul className="mt-1.5 space-y-1 text-[16px] text-ink-2">
        {warnings.map((w) => <li key={w.code}>{w.message}</li>)}
      </ul>
      {c && (
        <>
          <h2 className="mt-5 text-[20px] font-semibold tracking-tight">{c.prompt}</h2>
          <ul className="mt-3 grid gap-3 sm:grid-cols-2">
            {c.options.map((o) => (
              <li key={o.id}>
                <button type="button" onClick={() => onAsk(o.suggested_question)} data-testid={`clarify-${o.id}`}
                  className="group flex h-full w-full flex-col items-start rounded-xl border border-line-strong bg-white p-4 text-left transition-colors hover:border-amb hover:bg-amb-soft/50">
                  <span className="flex w-full items-center justify-between text-[17px] font-semibold">{o.label}<ArrowRight aria-hidden className="size-4 text-ink-3 transition-transform group-hover:translate-x-0.5" /></span>
                  <span className="mt-1 text-[14px] leading-snug text-ink-3">{o.description}</span>
                  <span className="mt-2 text-[14px] leading-snug text-ink-2">“{o.suggested_question}”</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <button type="button" onClick={onEdit} className={`${btn} mt-4`}><PencilLine aria-hidden className="size-4" /> Revise the question</button>
    </section>
  );
}

/** BLOCKED: rejected before execution; no numbers; point at what the API *does* approve. */
export function BlockedPanel({ r, onAsk, onEdit }: { r: AnalyzeResponse; onAsk: (q: string) => void; onEdit: () => void }) {
  const { catalog, examples } = useBackend();
  const errors = r.verification.reasons.filter((x) => x.severity === "error");
  const failedChecks = r.verification.checks.filter((c) => c.status === "FAIL");
  const tryThese = (examples.data?.examples ?? []).filter((e) => e.expected_status === "VERIFIED").slice(0, 3);
  return (
    <section aria-label="Request blocked" className="rounded-2xl border border-bad/25 bg-surface p-5 sm:p-6" data-testid="blocked-panel">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-bad-soft text-bad"><Ban aria-hidden className="size-5" /></span>
        <div className="min-w-0">
          <h2 className="text-[20px] font-semibold tracking-tight">Rejected before execution</h2>
          <p className="mt-0.5 text-[16px] text-ink-2" data-testid="blocked-no-sql">No SQL was executed against IBM Db2, so no data was read or changed.</p>
        </div>
      </div>
      <ul className="mt-4 space-y-2" data-testid="blocked-reasons">
        {errors.map((e) => (
          <li key={e.code} className="rounded-lg bg-bad-soft/60 px-3.5 py-2.5 text-[15px] leading-snug text-ink">
            <span className="mr-2 rounded bg-white px-1.5 py-0.5 font-mono text-[12px] font-medium text-bad">{e.code}</span>{e.message}
          </li>
        ))}
        {errors.length === 0 && <li className="text-ink-2">{r.verification.summary}</li>}
      </ul>
      {failedChecks.length > 0 && <p className="mt-3 text-[13px] text-ink-3">Stopped at {failedChecks.map((c) => c.id).join(", ")}. See the evidence panel.</p>}

      {(catalog.data || tryThese.length > 0) && (
        <div className="mt-5 border-t border-line pt-4">
          <p className="text-[13px] font-medium uppercase tracking-wider text-ink-3">What MetricGuard can answer</p>
          {catalog.data && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {catalog.data.metrics.map((m) => <li key={m.name} className="rounded-full bg-sunken px-3 py-1 text-[14px] text-ink-2">{m.display_name}</li>)}
            </ul>
          )}
          {catalog.data && <p className="mt-2 text-[14px] text-ink-3">By {catalog.data.dimensions.map((d) => d.display_name.toLowerCase()).join(", ")}.</p>}
          {tryThese.length > 0 && (
            <ul className="mt-3 space-y-1.5">
              {tryThese.map((e) => (
                <li key={e.id}><button type="button" onClick={() => onAsk(e.question)} className="rounded-md text-left text-[15px] text-accent-ink underline-offset-4 hover:underline">{e.question}</button></li>
              ))}
            </ul>
          )}
        </div>
      )}
      <button type="button" onClick={onEdit} className={`${btn} mt-4`}><PencilLine aria-hidden className="size-4" /> Revise the question</button>
    </section>
  );
}

/** EXECUTION_FAILED: planned and governed, but Db2 did not finish. Never shows numbers. */
export function FailedPanel({ r, onRetry }: { r: AnalyzeResponse; onRetry: () => void }) {
  const err = r.error;
  return (
    <section aria-label="Execution failed" className="rounded-2xl border border-fail/30 bg-surface p-5 sm:p-6" data-testid="failed-panel">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-fail-soft text-fail"><ServerCrash aria-hidden className="size-5" /></span>
        <div className="min-w-0">
          <h2 className="text-[20px] font-semibold tracking-tight">The query did not complete</h2>
          <p className="mt-0.5 text-[16px] text-ink-2">IBM Db2 did not return a result, so there are no numbers to show. This is not a verified answer.</p>
        </div>
      </div>
      {err && (
        <dl className="mt-4 grid gap-x-6 gap-y-1 rounded-lg bg-fail-soft/60 px-4 py-3 text-[15px] sm:grid-cols-[auto_1fr]" data-testid="failed-error">
          <dt className="text-ink-3">Error</dt><dd className="font-mono text-[14px]">{err.code}</dd>
          <dt className="text-ink-3">Message</dt><dd>{err.message}</dd>
          {err.sqlstate && <><dt className="text-ink-3">SQLSTATE</dt><dd className="font-mono text-[14px]">{err.sqlstate}</dd></>}
        </dl>
      )}
      <p className="mt-3 text-[14px] text-ink-3">The governed SQL that was attempted is listed in the evidence panel.</p>
      <button type="button" onClick={onRetry} className={`${btn} mt-4`} data-testid="retry"><RotateCw aria-hidden className="size-4" /> Retry</button>
    </section>
  );
}
