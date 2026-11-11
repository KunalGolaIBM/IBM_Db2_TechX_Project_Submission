"use client";

import Link from "next/link";
import { ArrowLeft, Quote } from "lucide-react";
import { getAuditDetail } from "@/lib/api/client";
import { useAsync } from "@/hooks/useAsync";
import { fromAudit } from "@/lib/evidence-model";
import { STATUS } from "@/lib/status";
import { StatusBadge } from "@/components/common/StatusBadge";
import { Skeleton } from "@/components/common/Skeleton";
import { EvidencePanel } from "@/components/evidence/EvidencePanel";
import { ResultTable } from "@/components/analytics/ResultTable";
import { ModeDisclosure } from "@/components/analytics/ModeDisclosure";
import { TransportError } from "@/components/analytics/TransportError";

/** Audit rows store the planner name only; names are provider-specific since API 1.2.0. */
function providerFromName(name: string | null | undefined): "meta" | "anthropic" | null {
  return name === "langchain-meta" ? "meta" : name === "langchain-anthropic" ? "anthropic" : null;
}

export function AuditDetailView({ id }: { id: string }) {
  const q = useAsync((s) => getAuditDetail(id, s), [id]);
  const d = q.data;

  return (
    <div className="space-y-5">
      <Link href="/audit" className="inline-flex items-center gap-1.5 rounded-md text-[15px] font-medium text-ink-2 hover:text-ink"><ArrowLeft aria-hidden className="size-4" />Audit history</Link>

      {q.error && !d && <TransportError error={q.error} onRetry={q.reload} testId="audit-detail-error" />}
      {q.loading && !d && <div className="space-y-3" data-testid="audit-detail-loading"><Skeleton className="h-32 w-full" /><Skeleton className="h-64 w-full" /></div>}

      {d && (
        <div className="rise space-y-4" data-testid="audit-detail" data-status={d.status}>
          {d.execution_mode ? (
            <ModeDisclosure planner={{ name: d.planner ?? "unknown", model: d.planner_model ?? null, execution_mode: d.execution_mode, disclosure: null, provider: providerFromName(d.planner) }} status={d.status} />
          ) : (
            <p className="rounded-xl border border-line bg-surface px-4 py-3 text-[15px] text-ink-2">This record predates planner-mode logging (API 1.1.0).</p>
          )}
          <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,34rem)]">
            <div className="min-w-0 space-y-4">
              <section className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
                <div className="flex flex-wrap items-center gap-3"><StatusBadge status={d.status} /><span className="text-[14px] text-ink-3">{STATUS[d.status].headline}</span></div>
                <p className="mt-3 flex items-start gap-2 text-[18px] font-medium leading-snug" data-testid="audit-question"><Quote aria-hidden className="mt-1 size-4 shrink-0 text-ink-3" />{d.question}</p>
                {d.answer_summary && <p className="mt-3 text-[17px] leading-relaxed text-ink-2" data-testid="audit-answer-summary">{d.answer_summary}</p>}
                {d.status_reason && <p className="mt-2 font-mono text-[13px] text-ink-3">reason: {d.status_reason}</p>}
                {d.error && <p className="mt-3 rounded-lg bg-fail-soft px-3 py-2 text-[15px] text-fail">{d.error.code}: {d.error.message}{d.error.sqlstate ? ` (SQLSTATE ${d.error.sqlstate})` : ""}</p>}
              </section>

              {d.result_preview && d.result_preview.rows.length > 0 && (
                <section className="rounded-2xl border border-line bg-surface p-5 sm:p-6" aria-label="Stored result preview">
                  <h2 className="mb-3 text-[17px] font-semibold">Stored result <span className="text-[14px] font-normal text-ink-3">· first {d.result_preview.rows.length} of {d.row_count ?? d.result_preview.row_count} rows</span></h2>
                  <ResultTable result={d.result_preview} caption="Stored result preview" />
                </section>
              )}
              {(!d.result_preview || d.result_preview.rows.length === 0) && (d.status === "BLOCKED" || d.status === "AMBIGUOUS" || d.status === "EXECUTION_FAILED") && (
                <p className="rounded-xl border border-line bg-surface px-4 py-3 text-[15px] text-ink-2">No result was produced, and none is shown. {d.status === "BLOCKED" && "No SQL was executed."}</p>
              )}
            </div>
            <div className="min-w-0 xl:sticky xl:top-20"><EvidencePanel model={fromAudit(d)} /></div>
          </div>
        </div>
      )}
    </div>
  );
}
