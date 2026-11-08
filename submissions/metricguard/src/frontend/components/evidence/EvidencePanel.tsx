"use client";

import Link from "next/link";
import { ExternalLink, Fingerprint } from "lucide-react";
import clsx from "clsx";
import type { EvidenceModel } from "@/lib/evidence-model";
import { STATUS } from "@/lib/status";
import { formatDateRange, formatMs, formatTimestamp, shortHash, titleCase } from "@/lib/formatters";
import { useBackend } from "@/components/layout/BackendProvider";
import { CopyButton } from "@/components/common/CopyButton";
import { Collapsible } from "./Collapsible";
import { ChecksList, checkSummary } from "./ChecksList";
import { SqlBlock } from "./SqlBlock";

const VERDICT_TEXT: Record<string, string> = {
  VERIFIED: "Passed every check below. This confirms approved metric definitions, governed read-only SQL and reconciled totals. It does not certify that the underlying data is correct.",
  EXECUTED_WITH_WARNINGS: "The governed SQL ran, but at least one check raised a warning. Review it before relying on the numbers.",
  AMBIGUOUS: "Nothing was executed. The question needs a single interpretation first.",
  BLOCKED: "Stopped before execution by a governance check. No SQL ran against IBM Db2.",
  EXECUTION_FAILED: "The query was valid but Db2 did not finish it. No result is available.",
};
const VERDICT_COLOR: Record<string, string> = {
  VERIFIED: "text-ev-ok", EXECUTED_WITH_WARNINGS: "text-ev-warn", AMBIGUOUS: "text-[#a99cf5]", BLOCKED: "text-ev-bad", EXECUTION_FAILED: "text-[#f0a15a]",
};

function Mono({ children, className }: { children: React.ReactNode; className?: string }) {
  return <span className={clsx("break-all font-mono text-[12.5px]", className)}>{children}</span>;
}

function Verdict({ m }: { m: EvidenceModel }) {
  const s = STATUS[m.status];
  const Icon = s.icon;
  const sum = checkSummary(m.verification.checks);
  return (
    <div className="px-5 pb-5 pt-5" data-testid="verdict">
      <div className="flex items-start gap-3">
        <Icon aria-hidden className={clsx("mt-0.5 size-6 shrink-0", VERDICT_COLOR[m.status])} strokeWidth={2} />
        <div className="min-w-0">
          <p className="text-[12px] font-medium uppercase tracking-[0.12em] text-ev-ink-3">Validation status</p>
          <p className={clsx("text-[22px] font-semibold leading-tight", VERDICT_COLOR[m.status])} data-testid="verdict-status">{s.label}</p>
        </div>
      </div>
      <p className="mt-3 text-[15px] leading-relaxed text-ev-ink" data-testid="verdict-summary">{m.verification.summary}</p>
      <p className="mt-2 text-[14px] leading-relaxed text-ev-ink-2">{VERDICT_TEXT[m.status]}</p>
      {sum.total > 0 && (
        <p className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[13px] text-ev-ink-2" data-testid="check-counts">
          <span className="text-ev-ok">{sum.pass} passed</span>
          {sum.warn > 0 && <span className="text-ev-warn">{sum.warn} warning</span>}
          {sum.fail > 0 && <span className="text-ev-bad">{sum.fail} failed</span>}
          {sum.skipped > 0 && <span className="text-ev-ink-3">{sum.skipped} skipped</span>}
          <span className="text-ev-ink-3">of {sum.total}</span>
        </p>
      )}
    </div>
  );
}

function Parameters({ m }: { m: EvidenceModel }) {
  const params = m.sql?.parameters ?? [];
  if (params.length === 0) return <p className="text-[14px] text-ev-ink-3">No parameters.</p>;
  return (
    <div className="scroll-quiet overflow-x-auto rounded-lg border border-ev-line" tabIndex={0} role="region" aria-label="SQL parameters">
      <table className="w-full min-w-max text-left text-[13px]" data-testid="params-table">
        <thead><tr className="border-b border-ev-line text-ev-ink-3"><th className="px-3 py-2 font-medium">#</th><th className="px-3 py-2 font-medium">Name</th><th className="px-3 py-2 font-medium">Type</th><th className="px-3 py-2 font-medium">Value</th></tr></thead>
        <tbody>
          {params.map((p) => (
            <tr key={p.position} className="border-b border-ev-line last:border-0">
              <td className="px-3 py-2 text-ev-ink-3">{p.position}</td>
              <td className="px-3 py-2"><Mono>{p.name}</Mono></td>
              <td className="px-3 py-2"><Mono className="text-ev-ink-2">{p.db2_type}</Mono></td>
              <td className="px-3 py-2"><Mono className="text-ev-ink">{p.value === null ? "NULL" : String(p.value)}</Mono></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MetricDefinitions({ m }: { m: EvidenceModel }) {
  const { catalog } = useBackend();
  if (m.metrics.length === 0) return <p className="text-[14px] text-ev-ink-3">No metric was resolved for this request.</p>;
  return (
    <ul className="space-y-3" data-testid="metric-definitions">
      {m.metrics.map((x) => {
        const info = catalog.data?.metrics.find((c) => c.name === x.name);
        return (
          <li key={x.ref} className="rounded-xl border border-ev-line bg-ev-raised p-3.5">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="text-[15px] font-semibold text-ev-ink">{x.displayName ?? info?.display_name ?? titleCase(x.name)}</span>
              <Mono className="text-ev-ink-2" >{x.ref}</Mono>
              {x.db2HashMatch === true && <span className="rounded-full bg-[#4fc08d]/15 px-2 py-0.5 text-[12px] font-medium text-ev-ok">Matches Db2 registry</span>}
              {x.db2HashMatch === false && <span className="rounded-full bg-[#f0746c]/15 px-2 py-0.5 text-[12px] font-medium text-ev-bad">Registry mismatch</span>}
              {x.db2HashMatch === null && <span className="rounded-full bg-white/5 px-2 py-0.5 text-[12px] font-medium text-ev-ink-3">Registry not checked</span>}
            </div>
            {info && <p className="mt-1.5 text-[13.5px] leading-snug text-ev-ink-2">{info.calculation}</p>}
            {info && <p className="mt-1 text-[12.5px] text-ev-ink-3">Owner {info.owner} · {info.lifecycle_status.toLowerCase()} · {info.eligible_order_statuses.join(", ").toLowerCase()} orders</p>}
            <div className="mt-2 flex items-center gap-2 text-ev-ink-3">
              <Fingerprint aria-hidden className="size-3.5 shrink-0" />
              <Mono className="min-w-0 truncate" >sha256 {shortHash(x.definitionHash, 16)}</Mono>
              <CopyButton text={x.definitionHash} label="Copy hash" className="ml-auto text-ev-ink-2 hover:bg-white/10" />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Interpretation({ m }: { m: EvidenceModel }) {
  const p = m.plan;
  const rows: [string, React.ReactNode][] = [];
  if (p) {
    rows.push(["Metrics", p.metrics.map((x) => `${x.name}@${x.version}`).join(", ")]);
    rows.push(["Period", `${formatDateRange(p.date_range.start_date, p.date_range.end_date)}${p.date_range.source === "default" ? " (default: full data coverage)" : ""}`]);
    rows.push(["Group by", p.dimensions?.length ? p.dimensions.join(", ") : "none (single total)"]);
    rows.push(["Filters", p.filters?.length ? p.filters.map((f) => `${f.field} in ${f.values.join(", ")}`).join("; ") : "none"]);
    if (p.order_by?.length) rows.push(["Sort", p.order_by.map((o) => `${o.field} ${o.direction}`).join(", ")]);
    if (p.limit) rows.push(["Limit", String(p.limit)]);
  }
  return (
    <div className="space-y-3 text-[14px]" data-testid="interpretation">
      {p ? (
        <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-[6.5rem_1fr]">
          {rows.map(([k, v]) => (<div key={k} className="contents"><dt className="text-ev-ink-3">{k}</dt><dd className="min-w-0 break-words text-ev-ink"><Mono className="text-ev-ink">{v}</Mono></dd></div>))}
        </dl>
      ) : <p className="text-ev-ink-3">No query plan was produced for this request.</p>}
      {m.assumptions.length > 0 && (
        <ul className="space-y-1 border-t border-ev-line pt-3">
          {m.assumptions.map((a) => <li key={a.code} className="text-ev-ink-2"><Mono className="mr-2 text-ev-ink-3">{a.code}</Mono>{a.message}</li>)}
        </ul>
      )}
      {m.planner && (
        <p className="border-t border-ev-line pt-3 text-ev-ink-2">
          Planned by <Mono className="text-ev-ink">{m.planner.name ?? "unknown"}</Mono>
          {m.planner.mode && <> · mode <Mono className="text-ev-ink">{m.planner.mode}</Mono></>}
          {m.planner.model && <> · model <Mono className="text-ev-ink">{m.planner.model}</Mono></>}
          {m.planner.mode === "DEMO_RULE_BASED" && <span className="mt-1 block text-ev-warn">Rule-based planner, not an LLM.</span>}
        </p>
      )}
    </div>
  );
}

function Footer({ m }: { m: EvidenceModel }) {
  const t = m.timing as Record<string, number | null | undefined>;
  const parts: [string, number | null | undefined][] = [["Plan", t.planning_ms], ["Validate", t.validation_ms], ["Execute", t.execution_ms], ["Verify", t.verification_ms]];
  return (
    <div className="space-y-3 border-t border-ev-line bg-black/20 px-5 py-4 text-[13px]" data-testid="evidence-footer">
      <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1">
        <span className="text-ev-ink-3">Total <strong className="tabular font-semibold text-ev-ink" data-testid="total-ms">{formatMs(t.total_ms)}</strong></span>
        {parts.map(([k, v]) => <span key={k} className="text-ev-ink-3">{k} <span className="tabular text-ev-ink-2">{formatMs(v)}</span></span>)}
      </div>
      <dl className="space-y-1.5">
        <div className="flex items-center gap-2">
          <dt className="w-16 shrink-0 text-ev-ink-3">Request</dt>
          <dd className="flex min-w-0 flex-1 items-center gap-1"><Mono className="min-w-0 truncate text-ev-ink" ><span data-testid="request-id">{m.requestId}</span></Mono><CopyButton text={m.requestId} label="Copy" className="text-ev-ink-2 hover:bg-white/10" /></dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="w-16 shrink-0 text-ev-ink-3">Audit</dt>
          <dd className="min-w-0 flex-1 text-ev-ink-2">
            {m.source === "audit" && <>This stored Db2 audit record <Mono className="text-ev-ink-3">(append-only)</Mono></>}
            {m.source === "live" && m.auditPersisted && m.auditPath && (
              <Link href={`/audit/${m.requestId}`} className="inline-flex items-center gap-1.5 rounded text-[#8ab4f8] underline-offset-4 hover:underline" data-testid="audit-link">
                Recorded in Db2 · open audit entry <ExternalLink aria-hidden className="size-3.5" />
              </Link>
            )}
            {m.source === "live" && !m.auditPersisted && <span className="text-ev-warn" data-testid="audit-not-persisted">Not logged: the audit write failed. The answer itself is valid.</span>}
          </dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="w-16 shrink-0 text-ev-ink-3">Time</dt>
          <dd className="text-ev-ink-2">{formatTimestamp(m.createdAt)}</dd>
        </div>
      </dl>
    </div>
  );
}

export function EvidencePanel({ model: m, className }: { model: EvidenceModel; className?: string }) {
  const checks = m.verification.checks;
  const sum = checkSummary(checks);
  return (
    <aside aria-label="Verification evidence" data-testid="evidence-panel" className={clsx("ev overflow-hidden rounded-2xl bg-ev text-ev-ink shadow-[0_10px_30px_-12px_rgba(20,19,15,0.45)]", className)}>
      <header className="flex items-center gap-2 border-b border-ev-line px-5 py-3">
        <h2 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ev-ink-2">Verification evidence</h2>
      </header>
      <Verdict m={m} />

      <p className="border-t border-ev-line bg-white/[0.02] px-5 py-2 text-[11.5px] font-semibold uppercase tracking-[0.14em] text-ev-ink-3">Execution evidence</p>
      <Collapsible title="Executed SQL" meta={m.sql ? `${m.sql.text.split("\n").length} lines · ${m.sql.parameters.length} params` : "none"} defaultOpen testId="sec-sql">
        {m.sql ? (
          <>
            <SqlBlock sql={m.sql.text} sqlHash={m.sql.sqlHash} />
            {(m.sql.tables?.length ?? 0) > 0 && <p className="mt-2 break-words text-[12.5px] text-ev-ink-3">Tables: <Mono className="text-ev-ink-2">{m.sql.tables!.join(", ")}</Mono></p>}
            {m.sql.generatedBy && <p className="mt-1 text-[12.5px] text-ev-ink-3">Generated by <Mono className="text-ev-ink-2">{m.sql.generatedBy}</Mono>, not by the language model.</p>}
          </>
        ) : (
          <p className="text-[14px] text-ev-ink-2" data-testid="no-sql">{m.status === "BLOCKED" || m.status === "AMBIGUOUS" ? "No SQL was generated or executed for this request." : "No SQL is stored for this request."}</p>
        )}
      </Collapsible>
      <Collapsible title="Verification checks" meta={sum.total ? `${sum.pass}/${sum.total} passed` : undefined} defaultOpen={sum.pass > 0} testId="sec-checks">
        <ChecksList checks={checks} />
      </Collapsible>
      <Collapsible title="Query parameters" meta={m.sql ? `${m.sql.parameters.length} bound values` : undefined} testId="sec-params"><Parameters m={m} /></Collapsible>
      <Collapsible title="Metric definitions" meta={m.metrics.map((x) => x.ref).join(" · ")} defaultOpen={m.metrics.length > 0} testId="sec-metrics"><MetricDefinitions m={m} /></Collapsible>

      <p className="border-t border-ev-line bg-white/[0.02] px-5 py-2 text-[11.5px] font-semibold uppercase tracking-[0.14em] text-ev-ink-3">Interpretation</p>
      <Collapsible title="How the question was read" meta={m.plan ? `${m.plan.metrics.length} metric${m.plan.metrics.length > 1 ? "s" : ""}` : "no plan"} testId="sec-plan"><Interpretation m={m} /></Collapsible>

      <Footer m={m} />
    </aside>
  );
}
