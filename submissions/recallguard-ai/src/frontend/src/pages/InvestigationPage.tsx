import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, BrainCircuit, CheckCircle2, CircleDashed, ClipboardCheck, FileSearch, Loader2, ShieldCheck, Sigma, Truck, XCircle } from "lucide-react";
import { useIncident, useIncidents, useInvestigation, useRefreshAll } from "@/hooks/queries";
import { api, ApiError } from "@/services/api";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, Progress, Tabs } from "@/components/ui";
import { StatusBadge } from "@/components/shared";
import { cn, fmt } from "@/lib/utils";
import type { AgentRun } from "@/types";

const ICONS: Record<string, typeof BrainCircuit> = { investigation: FileSearch, supply_chain: Truck, risk_assessment: Sigma, recall_planning: ClipboardCheck, verification: ShieldCheck };

function StatusIcon({ s }: { s: string }) {
  if (s === "COMPLETED") return <CheckCircle2 className="size-4 text-emerald-400" />;
  if (s === "RUNNING") return <Loader2 className="size-4 animate-spin text-cyan-400" />;
  if (s === "FAILED") return <XCircle className="size-4 text-red-400" />;
  return <CircleDashed className="size-4 text-slate-600" />;
}

function Findings({ a }: { a: AgentRun }) {
  const o = a.output;
  if (!o) return <p className="text-xs text-slate-500">No output yet.</p>;
  switch (a.agent_name) {
    case "investigation":
      return (
        <div className="space-y-3 text-sm">
          <p className="text-slate-200">{o.summary}</p>
          {o.hypothesis && <p className="text-xs text-slate-400"><b className="text-slate-300">Hypothesis:</b> {o.hypothesis}</p>}
          <div className="flex flex-wrap gap-2">
            <Badge tone={o.lab_confirmed ? "red" : "amber"}>{o.lab_confirmed ? "Lab-confirmed" : "Not lab-confirmed"}</Badge>
            <Badge tone="slate">Supplier: {o.supplier_name ?? "—"}</Badge>
            {o.extracted_lot_ids?.map((l: string) => <Badge key={l} tone="cyan">{l}</Badge>)}
          </div>
        </div>
      );
    case "supply_chain":
      return (
        <div className="space-y-3 text-sm">
          <p className="text-slate-200">{o.summary}</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[["Batches", o.affected_batch_ids.length], ["Finished", o.finished_batch_ids.length], ["Products", o.product_ids.length], ["Locations", o.locations.length]].map(([k, v]) => (
              <div key={k} className="rounded-lg border border-line bg-ink-950/50 p-2"><p className="text-[10px] text-slate-500">{k}</p><p className="text-lg font-semibold text-white">{v}</p></div>
            ))}
          </div>
          <p className="mono text-slate-400">Direct: {o.direct_batch_ids.join(", ")}</p>
          <p className="mono text-slate-400">Indirect: {o.indirect_batch_ids.join(", ") || "—"}</p>
          <p className="text-[11px] text-slate-500">Engine: {o.engine} · {o.queries_executed.length} recursive SQL statements</p>
        </div>
      );
    case "risk_assessment":
      return (
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-3"><span className="text-3xl font-semibold text-white">{o.score}</span><Badge tone={o.classification === "CRITICAL" ? "red" : o.classification === "HIGH" ? "amber" : "cyan"}>{o.classification}</Badge><Badge tone="violet">{o.recall_class.replace("_", " ")}</Badge><span className="text-xs text-slate-400">confidence {o.confidence} · completeness {o.data_completeness_pct}%</span></div>
          {o.factors.map((f: any) => (
            <div key={f.factor} className="grid grid-cols-[100px_1fr_48px] items-center gap-2 text-xs">
              <span className="capitalize text-slate-300">{f.factor}</span><Progress value={(f.contribution / f.weight) * 100} tone={f.factor === "uncertainty" ? "amber" : "cyan"} /><span className="text-right tabular-nums text-slate-200">+{f.contribution}</span>
            </div>
          ))}
          {o.narrative && <p className="text-xs text-slate-400">{o.narrative}</p>}
          <p className="text-[11px] italic text-slate-500">{o.disclaimer}</p>
        </div>
      );
    case "recall_planning":
      return (
        <div className="space-y-2 text-sm">
          <p className="text-slate-200">{o.summary}</p>
          <p className="text-xs text-slate-400">{o.items.length} batch-location items · {fmt(o.total_units)} units · {o.notifications.length} simulated notices · {o.excluded_batches.length} same-SKU batches excluded</p>
        </div>
      );
    case "verification":
      return (
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2"><Badge tone={o.verdict === "PASS" ? "emerald" : o.verdict === "FAIL" ? "red" : "amber"}>{o.verdict}</Badge><span className="text-xs text-slate-300">{o.summary}</span></div>
          <ul className="space-y-1">{o.checks.map((c: any, i: number) => (
            <li key={i} className="flex items-start gap-2 text-xs">{c.passed ? <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-400" /> : <AlertTriangle className={cn("mt-0.5 size-3.5 shrink-0", c.severity === "BLOCKER" ? "text-red-400" : "text-amber-400")} />}<span><span className="text-slate-200">{c.check}</span> <span className="text-slate-500">— {c.detail}</span></span></li>
          ))}</ul>
        </div>
      );
  }
  return null;
}

function Evidence({ a }: { a: AgentRun }) {
  const o = a.output;
  if (a.agent_name !== "investigation" || !o) return <p className="text-xs text-slate-500">Evidence is attached to the Investigation Agent; other agents cite Db2 records (see Findings & Log).</p>;
  return (
    <div className="space-y-2">
      {o.lab_findings.map((f: any, i: number) => (
        <div key={i} className={cn("rounded-lg border p-2.5", f.positive ? "border-red-500/30 bg-red-500/5" : "border-line bg-ink-950/50")}>
          <p className="text-xs text-slate-200">“{f.snippet}”</p>
          <p className="mono mt-1 text-slate-500">{f.filename} · p.{f.page}{f.section ? ` · ${f.section}` : ""} · {f.positive ? "POSITIVE" : "negative/neutral"}</p>
        </div>
      ))}
      {o.supporting_records.map((f: any, i: number) => (
        <div key={`s${i}`} className="rounded-lg border border-line bg-ink-950/50 p-2.5">
          <p className="text-xs text-slate-200">{f.snippet}</p>
          <p className="mono mt-1 text-slate-500">QUALITY_REPORTS {f.filename} · {f.claim_type} · {f.value}</p>
        </div>
      ))}
    </div>
  );
}

function Uncertainty({ a }: { a: AgentRun }) {
  const o = a.output;
  if (!o) return null;
  const items: { tone: "red" | "amber"; title: string; text: string }[] = [];
  o.conflicts?.forEach((c: any) => items.push({ tone: "red", title: `Conflict: ${c.topic}`, text: `A: ${c.statement_a}\nB: ${c.statement_b}\n→ ${c.resolution}` }));
  o.missing_evidence?.forEach((m: string) => items.push({ tone: "amber", title: "Missing evidence", text: m }));
  o.data_gaps?.forEach((g: any) => items.push({ tone: g.severity === "HIGH" ? "red" : "amber", title: g.code, text: g.message }));
  o.human_review_reasons?.forEach((r: string) => items.push({ tone: "amber", title: "Human review", text: r }));
  if (!items.length) return <p className="text-xs text-slate-500">No uncertainty reported by this agent.</p>;
  return <div className="space-y-2">{items.map((it, i) => (
    <div key={i} className={cn("rounded-lg border p-2.5", it.tone === "red" ? "border-red-500/30 bg-red-500/5" : "border-amber-500/30 bg-amber-500/5")}>
      <p className="text-xs font-medium text-slate-100">{it.title}</p><p className="whitespace-pre-line text-xs text-slate-300">{it.text}</p>
    </div>))}</div>;
}

function AgentPanel({ a }: { a: AgentRun }) {
  const [tab, setTab] = useState<"findings" | "evidence" | "uncertainty" | "log" | "json">("findings");
  return (
    <div className="p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <Tabs value={tab} onChange={setTab} items={[{ value: "findings", label: "Findings" }, { value: "evidence", label: "Evidence" }, { value: "uncertainty", label: "Uncertainty & gaps" }, { value: "log", label: "Execution log" }, { value: "json", label: "Structured output" }]} />
        <Badge tone={a.execution_mode === "CREWAI_LLM" ? "violet" : "amber"}>{a.execution_mode === "CREWAI_LLM" ? "CrewAI · LLM narrative" : "Deterministic fallback · not an LLM"}</Badge>
      </div>
      {tab === "findings" && <Findings a={a} />}
      {tab === "evidence" && <Evidence a={a} />}
      {tab === "uncertainty" && <Uncertainty a={a} />}
      {tab === "log" && <pre className="mono max-h-96 overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-ink-950/80 p-3 text-slate-300">{a.log.join("\n") || "—"}</pre>}
      {tab === "json" && <pre className="mono max-h-96 overflow-auto rounded-lg border border-line bg-ink-950/80 p-3 text-slate-300">{JSON.stringify(a.output, null, 2)}</pre>}
    </div>
  );
}

export default function InvestigationPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const incidents = useIncidents();
  const incident = useIncident(id);
  const inv = useInvestigation(id);
  const refresh = useRefreshAll();
  const [open, setOpen] = useState<string>("investigation");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const picker = (
    <select aria-label="Select incident" className="input max-w-sm" value={id ?? ""} onChange={(e) => nav(`/investigations/${e.target.value}`)}>
      <option value="" disabled>Select an incident…</option>
      {incidents.data?.map((i) => <option key={i.incident_id} value={i.incident_id}>{i.incident_id} — {i.title}</option>)}
    </select>
  );
  const notFound = inv.isError && inv.error instanceof ApiError && inv.error.status === 404;
  const run = inv.data;
  const status = incident.data?.incident_status;

  return (
    <div>
      <PageHeader eyebrow="AI investigation centre" title="Multi-agent investigation"
        subtitle="Five CrewAI agents share one investigation context. Facts come from Db2; agents may only add narrative, and the Verification Agent re-checks everything against Db2."
        actions={picker} />
      {!id ? <Card><EmptyState title="Choose an incident to inspect its agents" /></Card> : inv.isLoading ? <LoadingState rows={6} /> : notFound ? (
        <Card><EmptyState title="No investigation has run yet" action={<Button variant="primary" loading={busy} onClick={async () => { setBusy(true); try { await api.investigate(id); await refresh(); } catch (e) { setErr(String(e)); } setBusy(false); }}><BrainCircuit />Initiate AI investigation</Button>} /></Card>
      ) : inv.isError ? <ErrorState error={inv.error} /> : run && (
        <>
          <Card className="mb-4 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="mono text-slate-400">{run.run_id}</span>
              <Badge tone={run.status === "COMPLETED" ? "emerald" : run.status === "FAILED" ? "red" : "cyan"} dot>{run.status}</Badge>
              {status && <StatusBadge status={status} />}
              <Badge tone={run.mode === "CREWAI_LLM" ? "violet" : "amber"}>{run.mode}</Badge>
              <span className="text-xs text-slate-400">{run.mode_note}</span>
              <div className="ml-auto flex gap-2">
                {status === "RECALL_RECOMMENDED" && <Button size="sm" variant="primary" loading={busy} onClick={async () => { setBusy(true); setErr(null); try { const rc = await api.generateRecall(id); await refresh(); nav(`/recalls/${rc.recall_id}`); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } setBusy(false); }}><ClipboardCheck />Generate recall plan</Button>}
                {incident.data?.recalls?.find((r) => r.recall_status !== "SUPERSEDED") && <Button asChild size="sm" variant="secondary"><Link to={`/recalls/${incident.data.recalls.find((r) => r.recall_status !== "SUPERSEDED")!.recall_id}`}>Open recall plan</Link></Button>}
              </div>
            </div>
            <Progress className="mt-3" value={run.progress * 100} tone={run.status === "FAILED" ? "red" : "cyan"} />
            {err && <p role="alert" className="mt-2 text-sm text-red-300">{err}</p>}
          </Card>

          <div className="grid gap-3 md:grid-cols-5">
            {run.agents.map((a, i) => {
              const Icon = ICONS[a.agent_name] ?? BrainCircuit;
              return (
                <button key={a.agent_name} onClick={() => setOpen(a.agent_name)} aria-pressed={open === a.agent_name}
                  className={cn("glass relative p-3 text-left transition-colors", open === a.agent_name ? "border-cyan-500/50 bg-cyan-500/[0.06]" : "hover:border-slate-500/40")}>
                  <div className="flex items-center justify-between"><Icon className="size-4 text-cyan-300" /><StatusIcon s={a.run_status} /></div>
                  <p className="mt-2 text-[13px] font-medium text-slate-100">{a.title}</p>
                  <p className="text-[10px] text-slate-500">Step {i + 1} · {a.run_status.toLowerCase()}</p>
                </button>
              );
            })}
          </div>
          {run.agents.filter((a) => a.agent_name === open).map((a) => (
            <Card key={a.agent_name} className="mt-4"><CardHeader title={a.title} subtitle={`${a.started_at ?? ""} → ${a.completed_at ?? "…"}`} icon={<BrainCircuit />} /><AgentPanel a={a} /></Card>
          ))}
        </>
      )}
    </div>
  );
}
