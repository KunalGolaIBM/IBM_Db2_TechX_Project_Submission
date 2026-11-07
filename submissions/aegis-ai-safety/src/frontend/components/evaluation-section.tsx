"use client";

import { BarChart3, ExternalLink, FlaskConical } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { EvaluationData } from "@/lib/types";

const METRICS = [
  "Macro F1",
  "Per-class precision / recall",
  "Confusion matrix",
  "False-positive analysis",
  "Retrieval Recall@K",
  "Verification latency",
];

interface ClassificationMetrics {
  n?: number;
  accuracy?: number;
  macro_f1?: number;
  per_class?: Record<
    string,
    { precision?: number; recall?: number; f1?: number; support?: number }
  >;
  confusion_matrix?: Record<string, Record<string, number>>;
}

interface EvaluationResults {
  classification?: ClassificationMetrics;
  retrieval?: Record<string, { k?: number; recall?: number; n?: number } | number>;
  latency?: { n?: number; mean_ms?: number | null; median_ms?: number | null; p95_ms?: number | null };
}

function formatMetric(value: number | undefined): string {
  return typeof value === "number" ? value.toFixed(3) : "—";
}

export function EvaluationSection({ evaluation }: { evaluation: EvaluationData | null }) {
  const results = (evaluation?.results ?? null) as EvaluationResults | null;
  const completed = evaluation?.status === "completed" && results?.classification;

  return (
    <Card id="evaluation" className="scroll-mt-24">
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <p className="eyebrow">05 / Evaluation</p>
          <CardTitle className="mt-1.5 text-base">Benchmark evidence</CardTitle>
        </div>
        <span className="rounded-full border border-border bg-panel-2 px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider text-muted">
          {evaluation?.dataset ?? "SciFact"} · {evaluation?.license ?? "CC BY-NC 2.0"}
        </span>
      </CardHeader>

      <CardContent>
        {completed ? (
          <div className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                { label: "Macro F1", value: formatMetric(results.classification?.macro_f1) },
                { label: "Accuracy", value: formatMetric(results.classification?.accuracy) },
                { label: "Claims", value: String(results.classification?.n ?? "—") },
              ].map((metric) => (
                <div key={metric.label} className="rounded-md border border-border bg-panel-2/50 px-3.5 py-3">
                  <p className="font-mono text-[9px] uppercase tracking-wider text-muted">{metric.label}</p>
                  <p className="mt-1 text-xl font-semibold tabular-nums text-fg">{metric.value}</p>
                </div>
              ))}
            </div>

            <div className="overflow-x-auto rounded-md border border-border">
              <table className="w-full text-left text-[11px]">
                <thead className="bg-panel-2 font-mono text-[9px] uppercase tracking-wider text-muted">
                  <tr>
                    <th className="px-3 py-2">Class</th>
                    <th className="px-3 py-2">Precision</th>
                    <th className="px-3 py-2">Recall</th>
                    <th className="px-3 py-2">F1</th>
                    <th className="px-3 py-2">Support</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {Object.entries(results.classification?.per_class ?? {}).map(([label, values]) => (
                    <tr key={label}>
                      <td className="px-3 py-2 font-mono text-fg">{label}</td>
                      <td className="px-3 py-2 tabular-nums">{formatMetric(values.precision)}</td>
                      <td className="px-3 py-2 tabular-nums">{formatMetric(values.recall)}</td>
                      <td className="px-3 py-2 tabular-nums">{formatMetric(values.f1)}</td>
                      <td className="px-3 py-2 tabular-nums">{values.support ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {results.classification?.confusion_matrix ? (
              <div>
                <p className="eyebrow mb-2">Confusion matrix (gold rows / predicted columns)</p>
                <div className="overflow-x-auto rounded-md border border-border">
                  <table className="w-full text-left text-[11px]">
                    <thead className="bg-panel-2 font-mono text-[9px] uppercase tracking-wider text-muted">
                      <tr>
                        <th className="px-3 py-2">Gold</th>
                        {Object.keys(results.classification.confusion_matrix).map((label) => (
                          <th key={label} className="px-3 py-2">{label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {Object.entries(results.classification.confusion_matrix).map(([gold, row]) => (
                        <tr key={gold}>
                          <td className="px-3 py-2 font-mono text-fg">{gold}</td>
                          {Object.keys(results.classification?.confusion_matrix ?? {}).map((label) => (
                            <td key={label} className="px-3 py-2 tabular-nums">
                              {row[label] ?? 0}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-md border border-border bg-panel-2/40 px-3.5 py-3">
                <p className="eyebrow">Retrieval</p>
                <div className="mt-2 space-y-1 font-mono text-[11px] text-fg">
                  {Object.entries(results.retrieval ?? {})
                    .filter(([, value]) => typeof value === "object" && value !== null && "recall" in value)
                    .map(([name, value]) => (
                      <p key={name}>
                        {name.replaceAll("_", " ")}: {formatMetric((value as { recall?: number }).recall)}
                      </p>
                    ))}
                  {!results.retrieval ? <p className="text-muted">Not measured</p> : null}
                </div>
              </div>
              <div className="rounded-md border border-border bg-panel-2/40 px-3.5 py-3">
                <p className="eyebrow">Latency</p>
                <div className="mt-2 space-y-1 font-mono text-[11px] text-fg">
                  <p>
                    Mean:{" "}
                    {typeof results.latency?.mean_ms === "number"
                      ? `${(results.latency.mean_ms / 1000).toFixed(1)} s`
                      : "—"}
                  </p>
                  <p>
                    Median:{" "}
                    {typeof results.latency?.median_ms === "number"
                      ? `${(results.latency.median_ms / 1000).toFixed(1)} s`
                      : "—"}
                  </p>
                  <p>
                    p95:{" "}
                    {typeof results.latency?.p95_ms === "number"
                      ? `${(results.latency.p95_ms / 1000).toFixed(1)} s`
                      : "—"}
                  </p>
                </div>
              </div>
            </div>
            <p className="font-mono text-[10px] leading-5 text-muted">{evaluation?.message}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center rounded-lg border border-dashed border-border px-6 py-10 text-center">
            <span className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-panel-2">
              <BarChart3 className="h-5 w-5 text-muted" aria-hidden="true" />
            </span>
            <p className="mt-4 text-sm font-medium text-fg">No benchmark has been run</p>
            <p className="mt-1.5 max-w-lg text-xs leading-5 text-muted">
              {evaluation?.message ??
                "SciFact loading, metric calculation, and prediction formats are implemented, but no measured score exists yet. AEGIS never displays placeholder accuracy statistics."}
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-1.5">
              {METRICS.map((metric) => (
                <span
                  key={metric}
                  className="rounded border border-border bg-panel-2 px-1.5 py-0.5 font-mono text-[9px] text-muted"
                >
                  {metric}
                </span>
              ))}
            </div>
            <a
              className="mt-4 inline-flex items-center gap-1.5 text-[11px] text-accent hover:underline"
              href="https://github.com/sakethdonepudi/aegis-ai-safety/tree/main/experiments"
              target="_blank"
              rel="noreferrer"
            >
              <FlaskConical className="h-3 w-3" aria-hidden="true" />
              Evaluation harness and dataset manifest
              <ExternalLink className="h-3 w-3" aria-hidden="true" />
            </a>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
