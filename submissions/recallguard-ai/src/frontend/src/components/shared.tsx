import { Check } from "lucide-react";
import { Badge } from "@/components/ui";
import { cn, humanize, RISK_TONE, STATUS_TONE } from "@/lib/utils";

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONE[status] ?? "slate"} dot>{humanize(status)}</Badge>;
}

export function RiskBadge({ value, score }: { value: string; score?: number }) {
  return <Badge tone={RISK_TONE[value] ?? "slate"} className={value === "CRITICAL" ? "animate-pulseRing" : undefined}>{value}{score !== undefined && ` · ${score}`}</Badge>;
}

export function SeverityBadge({ value }: { value: string }) {
  return <Badge tone={RISK_TONE[value] ?? "slate"}>{value}</Badge>;
}

const FLOW = ["REPORTED", "INVESTIGATING", "EVIDENCE_REVIEW", "RECALL_RECOMMENDED", "PENDING_APPROVAL", "APPROVED", "EXECUTING", "COMPLETED"];

export function StatusStepper({ status }: { status: string }) {
  const rejected = status === "REJECTED";
  const idx = rejected ? FLOW.indexOf("PENDING_APPROVAL") : FLOW.indexOf(status);
  return (
    <ol className="flex w-full items-center overflow-x-auto pb-1" aria-label="Incident workflow">
      {FLOW.map((s, i) => {
        const done = i < idx || (i === idx && status === "COMPLETED");
        const cur = i === idx && !done;
        return (
          <li key={s} className="flex min-w-[88px] flex-1 items-center">
            <div className="flex flex-col items-center gap-1">
              <div className={cn("grid size-6 place-items-center rounded-full border text-[10px]",
                done ? "border-emerald-400/60 bg-emerald-500/20 text-emerald-300" :
                cur ? (rejected ? "border-red-400 bg-red-500/20 text-red-300" : "border-cyan-400 bg-cyan-500/20 text-cyan-200 animate-pulse") : "border-line text-slate-600")}>
                {done ? <Check className="size-3.5" /> : i + 1}
              </div>
              <span className={cn("whitespace-nowrap text-[10px]", cur ? "text-slate-100" : "text-slate-500")}>{cur && rejected ? "Rejected" : humanize(s)}</span>
            </div>
            {i < FLOW.length - 1 && <div className={cn("mx-1 mb-4 h-px flex-1", i < idx ? "bg-emerald-500/40" : "bg-line")} />}
          </li>
        );
      })}
    </ol>
  );
}

export function KV({ k, v, mono }: { k: string; v: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-line/60 py-1.5 last:border-0">
      <span className="shrink-0 text-xs text-slate-400">{k}</span>
      <span className={cn("min-w-0 break-words text-right text-xs text-slate-100", mono && "mono break-all")}>{v ?? "—"}</span>
    </div>
  );
}

export function SqlTransparency({ queries, engine }: { queries: { query: string; rows: number; ms: number }[]; engine: string }) {
  return (
    <div className="space-y-1.5">
      <p className="text-[11px] text-slate-500">Executed by: <span className={engine.includes("NOT") ? "text-amber-300" : "text-emerald-300"}>{engine}</span></p>
      {queries.map((q, i) => (
        <div key={i} className="flex flex-wrap items-center justify-between gap-x-2 rounded-md border border-line bg-ink-950/60 px-2 py-1">
          <code className="mono text-cyan-300">{q.query}</code>
          <span className="mono text-slate-400">{q.rows} rows · {q.ms} ms</span>
        </div>
      ))}
    </div>
  );
}
