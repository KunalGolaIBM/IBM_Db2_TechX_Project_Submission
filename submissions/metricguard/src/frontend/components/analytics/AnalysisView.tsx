"use client";

import { Quote } from "lucide-react";
import type { AnalyzeResponse } from "@/lib/api/types";
import { STATUS } from "@/lib/status";
import { fromAnalyze } from "@/lib/evidence-model";
import { StatusBadge } from "@/components/common/StatusBadge";
import { EvidencePanel } from "@/components/evidence/EvidencePanel";
import { ModeDisclosure } from "./ModeDisclosure";
import { AnswerPanel } from "./AnswerPanel";
import { AmbiguousPanel, BlockedPanel, FailedPanel } from "./OutcomePanels";

/** Status drives layout (API contract §9). Answer on the left, evidence on the right. */
export function AnalysisView({ r, onAsk, onEdit }: { r: AnalyzeResponse; onAsk: (q: string) => void; onEdit: () => void }) {
  const s = STATUS[r.status];
  return (
    <div className="rise space-y-4" data-testid="analysis-view" data-status={r.status}>
      <ModeDisclosure planner={r.planner} status={r.status} />

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,34rem)]">
        <div className="min-w-0 space-y-4">
          <div className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge status={r.status} />
              <span className="text-[14px] text-ink-3">{s.headline}</span>
            </div>
            <p className="mt-3 flex items-start gap-2 text-[17px] font-medium leading-snug" data-testid="echo-question">
              <Quote aria-hidden className="mt-1 size-4 shrink-0 text-ink-3" />{r.question}
            </p>
          </div>

          {(r.status === "VERIFIED" || r.status === "EXECUTED_WITH_WARNINGS") && <AnswerPanel r={r} />}
          {r.status === "AMBIGUOUS" && <AmbiguousPanel r={r} onAsk={onAsk} onEdit={onEdit} />}
          {r.status === "BLOCKED" && <BlockedPanel r={r} onAsk={onAsk} onEdit={onEdit} />}
          {r.status === "EXECUTION_FAILED" && <FailedPanel r={r} onRetry={() => onAsk(r.question)} />}
        </div>

        <div className="min-w-0 xl:sticky xl:top-20">
          <EvidencePanel model={fromAnalyze(r)} />
        </div>
      </div>
    </div>
  );
}
