"use client";

import { Check, Minus, TriangleAlert, X } from "lucide-react";
import { useState } from "react";
import clsx from "clsx";
import type { CheckStatus, VerificationCheck } from "@/lib/api/types";
import { checkName } from "@/lib/formatters";

const ICON: Record<CheckStatus, { Icon: typeof Check; cls: string; label: string }> = {
  PASS: { Icon: Check, cls: "bg-[#4fc08d]/15 text-ev-ok", label: "Passed" },
  WARN: { Icon: TriangleAlert, cls: "bg-[#e3b341]/15 text-ev-warn", label: "Warning" },
  FAIL: { Icon: X, cls: "bg-[#f0746c]/15 text-ev-bad", label: "Failed" },
  SKIPPED: { Icon: Minus, cls: "bg-white/5 text-ev-ink-3", label: "Skipped" },
};

export function checkSummary(checks: VerificationCheck[]) {
  const n = (s: CheckStatus) => checks.filter((c) => c.status === s).length;
  return { pass: n("PASS"), warn: n("WARN"), fail: n("FAIL"), skipped: n("SKIPPED"), total: checks.length };
}

export function ChecksList({ checks }: { checks: VerificationCheck[] }) {
  const [details, setDetails] = useState(false);
  if (checks.length === 0) return <p className="text-[14px] text-ev-ink-3">No per-check record is stored for this request.</p>;
  return (
    <div>
      <button type="button" onClick={() => setDetails((d) => !d)} aria-pressed={details} data-testid="toggle-check-details"
        className="mb-2 rounded-md px-1 text-[13px] font-medium text-[#8ab4f8] hover:underline">
        {details ? "Hide details" : "Show details"}
      </button>
      <ol className="space-y-0.5" data-testid="checks-list">
        {checks.map((c) => {
          const { Icon, cls, label } = ICON[c.status];
          const showDetail = details || c.status === "WARN" || c.status === "FAIL";
          return (
            <li key={c.id} data-check-id={c.id} data-check-status={c.status} className="flex items-start gap-3 rounded-lg px-2 py-1 hover:bg-white/[0.03]">
              <span className={clsx("mt-0.5 grid size-5 shrink-0 place-items-center rounded-full", cls)} title={label}>
                <Icon aria-hidden className="size-3" strokeWidth={3} /><span className="sr-only">{label}</span>
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] leading-snug text-ev-ink">
                  <span className="mr-2 font-mono text-[12px] text-ev-ink-3">{c.id}</span>{checkName(c.name)}
                </p>
                {showDetail && <p className={clsx("text-[13px] leading-snug", c.status === "SKIPPED" ? "text-ev-ink-3" : "text-ev-ink-2")}>{c.detail}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
