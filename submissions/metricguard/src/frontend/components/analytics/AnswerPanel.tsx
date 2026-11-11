"use client";

import { BarChart3, Table2, TriangleAlert } from "lucide-react";
import { useState } from "react";
import clsx from "clsx";
import type { AnalyzeResponse } from "@/lib/api/types";
import { formatValue } from "@/lib/formatters";
import { InlineNotice } from "@/components/common/InlineNotice";
import { ResultChart } from "./ResultChart";
import { ResultTable } from "./ResultTable";

/** VERIFIED / EXECUTED_WITH_WARNINGS: headline, KPIs, chart, table. Uses backend values only. */
export function AnswerPanel({ r }: { r: AnalyzeResponse }) {
  const [view, setView] = useState<"chart" | "table">("chart");
  const { answer, result, chart } = r;
  if (!answer || !result) return null;

  const warnings = r.verification.reasons.filter((x) => x.severity === "warning");
  const metricCols = result.columns.filter((c) => c.role === "metric");
  const singleRow = result.rows.length === 1 && result.columns.every((c) => c.role === "metric");
  const hasChart = !!chart && chart.type !== "kpi" && chart.type !== "table" && chart.series.some((s) => s.points.length > 0);
  const chartMetricKeys = new Set(chart?.series.map((s) => s.metric) ?? []);
  const omitted = hasChart ? metricCols.filter((c) => !chartMetricKeys.has(c.name)) : [];
  const executedWithWarnings = r.status === "EXECUTED_WITH_WARNINGS";
  const empty = result.rows.length === 0;

  return (
    <div className="space-y-4">
      {warnings.length > 0 && (
        <InlineNotice tone="warn" icon={TriangleAlert} role="status" testId="warning-banner" title={executedWithWarnings ? "Review before relying on these numbers" : "Warnings"}>
          <ul className="list-disc space-y-0.5 pl-5">
            {warnings.map((w) => <li key={w.code}>{w.message}</li>)}
          </ul>
        </InlineNotice>
      )}

      <section aria-label="Answer" className="rounded-2xl border border-line bg-surface p-5 sm:p-6" data-testid="answer-card">
        {answer.headline && (
          <>
            <p className="text-[14px] font-medium text-ink-3">{answer.headline.label}</p>
            <p className="tabular mt-1 break-words text-[44px] font-semibold leading-none tracking-tight sm:text-[56px]" data-testid="headline-value">
              {answer.headline.formatted}
            </p>
          </>
        )}
        <p className={clsx("max-w-[62ch] text-[17px] leading-relaxed text-ink-2", answer.headline && "mt-4")} data-testid="answer-summary">{answer.summary}</p>

        {singleRow && metricCols.length > 1 && (
          <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-line pt-5 sm:grid-cols-3" data-testid="kpi-tiles">
            {metricCols.map((c) => (
              <div key={c.name} className="rounded-xl bg-sunken/70 px-4 py-3">
                <dt className="text-[13px] text-ink-3">{c.label}</dt>
                <dd className="tabular mt-0.5 text-[22px] font-semibold leading-tight">
                  {formatValue(result.rows[0]?.[c.name] as number | null | undefined, c.unit, c.scale)}
                  {result.rows[0]?.[c.name] == null && <span className="sr-only"> (undefined)</span>}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      {empty && <InlineNotice tone="warn" icon={TriangleAlert} title="No rows returned">The query ran, but nothing matched. Try a period inside the data coverage.</InlineNotice>}

      {!singleRow && !empty && (
        <section aria-label="Chart and data" className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-[17px] font-semibold">{chart?.title ?? "Result"}</h2>
            {hasChart && (
              <div role="tablist" aria-label="View" className="inline-flex rounded-lg border border-line bg-sunken/60 p-0.5">
                {([["chart", "Chart", BarChart3], ["table", "Table", Table2]] as const).map(([id, label, Icon]) => (
                  <button
                    key={id} role="tab" aria-selected={view === id} onClick={() => setView(id)} data-testid={`view-${id}`}
                    className={clsx("inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-[14px] font-medium", view === id ? "bg-white text-ink shadow-sm" : "text-ink-3 hover:text-ink")}
                  >
                    <Icon aria-hidden className="size-3.5" /> {label}
                  </button>
                ))}
              </div>
            )}
          </div>
          {hasChart && view === "chart" ? (
            <>
              <ResultChart chart={chart!} />
              {omitted.length > 0 && (
                <p className="mt-3 text-[13px] text-ink-3">
                  Chart shows {chart!.series.map((s) => s.label).join(", ")} only. {omitted.map((c) => c.label).join(", ")} {omitted.length > 1 ? "are" : "is"} in the table.
                </p>
              )}
            </>
          ) : (
            <ResultTable result={result} caption={chart?.title} />
          )}
          {result.truncated && <p className="mt-3 text-[13px] text-warn">Result truncated to {result.row_count} rows.</p>}
        </section>
      )}
    </div>
  );
}
