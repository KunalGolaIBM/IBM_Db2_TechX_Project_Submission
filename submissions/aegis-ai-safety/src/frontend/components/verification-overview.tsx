"use client";

import { Database, Loader2 } from "lucide-react";
import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CLASSIFICATION_META } from "@/components/classification";
import { cn, formatDate } from "@/lib/utils";
import type { Classification, Verification } from "@/lib/types";

const ORDER: Classification[] = [
  "SUPPORTED",
  "CONTRADICTED",
  "INSUFFICIENT_EVIDENCE",
  "VERIFICATION_ERROR",
];

interface VerificationOverviewProps {
  verification: Verification | null;
  loading: boolean;
}

export function VerificationOverview({ verification, loading }: VerificationOverviewProps) {
  const counts = verification?.counts ?? {
    total: 0,
    supported: 0,
    contradicted: 0,
    insufficient_evidence: 0,
    verification_error: 0,
  };

  const keyFor: Record<Classification, keyof typeof counts> = {
    SUPPORTED: "supported",
    CONTRADICTED: "contradicted",
    INSUFFICIENT_EVIDENCE: "insufficient_evidence",
    VERIFICATION_ERROR: "verification_error",
  };

  const chartData = ORDER.map((key) => ({
    key,
    name: CLASSIFICATION_META[key].label,
    value: counts[keyFor[key]],
    fill: CLASSIFICATION_META[key].chartColor,
  })).filter((item) => item.value > 0);

  const hasChart = chartData.length > 0;

  return (
    <Card id="overview" className="h-full scroll-mt-24">
      <CardHeader className="flex-row items-start justify-between space-y-0">
        <div>
          <p className="eyebrow">02 / Verification overview</p>
          <CardTitle className="mt-1.5 text-base">Evidence coverage</CardTitle>
        </div>
        {loading ? <Loader2 className="h-4 w-4 animate-spin text-accent" /> : null}
      </CardHeader>

      <CardContent className="space-y-5">
        <div className="relative mx-auto h-[188px] w-full max-w-[260px]">
          {hasChart ? (
            <>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={58}
                    outerRadius={78}
                    paddingAngle={2}
                    stroke="hsl(var(--panel))"
                    strokeWidth={2}
                    isAnimationActive={false}
                  >
                    {chartData.map((entry) => (
                      <Cell key={entry.key} fill={entry.fill} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-3xl font-semibold tabular-nums tracking-tight">
                  {counts.total}
                </span>
                <span className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.16em] text-muted">
                  claims
                </span>
              </div>
            </>
          ) : (
            <div className="flex h-full items-center justify-center">
              <div className="flex h-[156px] w-[156px] flex-col items-center justify-center rounded-full border border-dashed border-border">
                <span className="text-3xl font-semibold tabular-nums tracking-tight">0</span>
                <span className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.16em] text-muted">
                  claims
                </span>
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          {ORDER.map((key) => {
            const meta = CLASSIFICATION_META[key];
            return (
              <div
                key={key}
                className={cn(
                  "rounded-md border px-3 py-2.5",
                  meta.borderClass,
                  meta.bgClass
                )}
              >
                <div className="flex items-center gap-1.5">
                  <span className={cn("h-1.5 w-1.5 rounded-full", meta.dotClass)} />
                  <span className="font-mono text-[9px] uppercase tracking-wider text-muted">
                    {meta.short}
                  </span>
                </div>
                <p className={cn("mt-1 text-xl font-semibold tabular-nums", meta.textClass)}>
                  {counts[keyFor[key]]}
                </p>
              </div>
            );
          })}
        </div>

        <div className="space-y-2 border-t border-border pt-4 text-[11px]">
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted">Session</span>
            <span className="font-mono text-fg">
              {verification ? `#${verification.session_id}` : "—"}
            </span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted">Model provider</span>
            <span className="max-w-[190px] truncate font-mono text-fg">
              {verification?.model_provider ?? "—"}
            </span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted">Created</span>
            <span className="font-mono text-fg">{formatDate(verification?.created_at)}</span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted">Duration</span>
            <span className="font-mono text-fg">
              {verification?.duration_ms != null
                ? `${(verification.duration_ms / 1000).toFixed(1)} s`
                : "—"}
            </span>
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-muted">Evidence store</span>
            <span className="flex items-center gap-1 font-mono text-fg">
              <Database className="h-3 w-3 text-accent" aria-hidden="true" />
              IBM Db2
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
