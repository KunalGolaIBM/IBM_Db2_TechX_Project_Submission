"use client";

import Link from "next/link";
import { useState } from "react";
import { ChevronLeft, ChevronRight, DatabaseZap } from "lucide-react";
import { listAudit } from "@/lib/api/client";
import { ALL_STATUSES, type ValidationStatus } from "@/lib/api/types";
import { useAsync } from "@/hooks/useAsync";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Skeleton } from "@/components/common/Skeleton";
import { TransportError } from "@/components/analytics/TransportError";
import { STATUS } from "@/lib/status";
import { formatMs, formatTimestamp } from "@/lib/formatters";

const PAGE = 15;

const MODE_LABEL: Record<string, string> = { DEMO_RULE_BASED: "Demo planner", LLM: "AI planner" };
const PROVIDER_BY_NAME: Record<string, string> = { "langchain-meta": "Meta", "langchain-anthropic": "Anthropic" };

/** Audit rows carry the planner name (provider-specific since API 1.2.0) and the execution mode. */
function plannerLabel(mode: string | null | undefined, name: string | null | undefined): string {
  if (!mode) return "—";
  const provider = name ? PROVIDER_BY_NAME[name] : undefined;
  return provider ? `${MODE_LABEL[mode] ?? mode} · ${provider}` : MODE_LABEL[mode] ?? mode;
}

export function AuditList() {
  const [status, setStatus] = useState<ValidationStatus | "">("");
  const [offset, setOffset] = useState(0);
  const q = useAsync((s) => listAudit({ limit: PAGE, offset, status }, s), [status, offset]);
  const data = q.data;
  const total = data?.total ?? 0;
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE, total);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[28px] font-semibold tracking-tight">Audit history</h1>
          <p className="mt-1 flex items-center gap-2 text-[15px] text-ink-3"><DatabaseZap aria-hidden className="size-4" />Every request, stored append-only in IBM Db2 and read back through the API.</p>
        </div>
        <div>
          <label htmlFor="status-filter" className="mb-1 block text-[13px] font-medium text-ink-3">Status</label>
          <select
            id="status-filter" value={status} data-testid="status-filter"
            onChange={(e) => { setStatus(e.target.value as ValidationStatus | ""); setOffset(0); }}
            className="rounded-lg border border-line-strong bg-white px-3 py-2 text-[15px]"
          >
            <option value="">All statuses</option>
            {ALL_STATUSES.map((s) => <option key={s} value={s}>{STATUS[s].label}</option>)}
          </select>
        </div>
      </div>

      {q.error && !data && <TransportError error={q.error} onRetry={q.reload} testId="audit-error" />}

      {q.loading && !data && (
        <div className="space-y-2" data-testid="audit-loading">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14 w-full" />)}</div>
      )}

      {data && (
        <>
          {data.items.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-line-strong bg-surface p-10 text-center" data-testid="audit-empty">
              <p className="text-[17px] font-medium">No audit records{status ? " with this status" : " yet"}.</p>
              <p className="mt-1 text-[15px] text-ink-3">Ask a question in the workspace and it will appear here.</p>
              <Link href="/" className="mt-4 inline-block rounded-xl bg-ink px-4 py-2.5 text-[15px] font-semibold text-white">Open workspace</Link>
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <div className="hidden overflow-hidden rounded-2xl border border-line bg-surface md:block">
                <table className="w-full text-left text-[15px]" data-testid="audit-table">
                  <thead>
                    <tr className="border-b border-line bg-sunken/60 text-[13px] text-ink-3">
                      <th className="px-4 py-3 font-medium">Question</th><th className="px-4 py-3 font-medium">Status</th>
                      <th className="px-4 py-3 font-medium">Planner</th><th className="px-4 py-3 text-right font-medium">Duration</th><th className="px-4 py-3 font-medium">Time (UTC)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((it) => (
                      <tr key={it.request_id} className="border-b border-line last:border-0 hover:bg-sunken/40" data-testid="audit-row">
                        <td className="max-w-[28rem] px-4 py-3">
                          <Link href={`/audit/${it.request_id}`} className="line-clamp-2 rounded font-medium text-ink hover:text-accent-ink hover:underline">{it.question}</Link>
                          <span className="mt-0.5 block truncate font-mono text-[12px] text-ink-3">{it.metric_refs.join(" · ") || "no metric"}</span>
                        </td>
                        <td className="px-4 py-3"><StatusBadge status={it.status} size="sm" /></td>
                        <td className="px-4 py-3 text-ink-2">{plannerLabel(it.execution_mode, it.planner)}</td>
                        <td className="tabular px-4 py-3 text-right text-ink-2">{formatMs(it.total_ms)}</td>
                        <td className="whitespace-nowrap px-4 py-3 text-ink-3">{formatTimestamp(it.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Mobile cards */}
              <ul className="space-y-2 md:hidden" data-testid="audit-cards">
                {data.items.map((it) => (
                  <li key={it.request_id}>
                    <Link href={`/audit/${it.request_id}`} className="block rounded-xl border border-line bg-surface p-4">
                      <p className="line-clamp-3 font-medium">{it.question}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-2"><StatusBadge status={it.status} size="sm" /><span className="text-[13px] text-ink-3">{plannerLabel(it.execution_mode, it.planner)} · {formatMs(it.total_ms)}</span></div>
                      <p className="mt-1.5 text-[12px] text-ink-3">{formatTimestamp(it.created_at)}</p>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}

          <nav aria-label="Pagination" className="flex items-center justify-between text-[14px] text-ink-3">
            <span data-testid="audit-range">{total === 0 ? "0 records" : `${from}–${to} of ${total}`}</span>
            <div className="flex gap-2">
              <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))} className="inline-flex items-center gap-1 rounded-lg border border-line-strong bg-white px-3 py-1.5 font-medium text-ink disabled:opacity-40"><ChevronLeft aria-hidden className="size-4" />Newer</button>
              <button type="button" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)} className="inline-flex items-center gap-1 rounded-lg border border-line-strong bg-white px-3 py-1.5 font-medium text-ink disabled:opacity-40">Older<ChevronRight aria-hidden className="size-4" /></button>
            </div>
          </nav>
          {q.error && <p className="text-[14px] text-bad" role="alert">Refresh failed: {q.error.message}</p>}
        </>
      )}
    </div>
  );
}
