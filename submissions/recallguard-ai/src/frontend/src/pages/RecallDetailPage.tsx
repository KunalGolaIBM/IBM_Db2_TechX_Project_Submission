import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, ClipboardCheck, FileText, Gauge, Megaphone, ShieldCheck, ShieldX, Store, XCircle } from "lucide-react";
import { useRecall, useRecallDecision } from "@/hooks/queries";
import { getRole } from "@/services/api";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, Progress, Tabs } from "@/components/ui";
import { RiskBadge, StatusBadge } from "@/components/shared";
import { cn, fmt, fmtDate, humanize } from "@/lib/utils";

const PRIO_TONE = { P1: "red", P2: "amber", P3: "slate" } as const;
const BASIS_TONE = { DIRECT: "red", INDIRECT: "amber", PRECAUTIONARY: "violet" } as const;

export function ApprovalPanel({ recallId, status }: { recallId: string; status: string }) {
  const [comment, setComment] = useState("");
  const m = useRecallDecision(recallId);
  const role = getRole();
  const canDecide = role === "recall_manager" || role === "admin";
  if (status !== "PENDING_APPROVAL") return null;
  return (
    <Card className="border-amber-500/30">
      <CardHeader title="Human approval required" subtitle="AI agents cannot issue recall notices. An authorised recall manager must decide." icon={<ShieldCheck />} />
      <div className="space-y-3 p-4">
        {!canDecide && <p className="rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-xs text-amber-200">Your current role (<b>{humanize(role)}</b>) cannot approve or reject. Switch to <b>Recall Manager</b> in the top bar.</p>}
        <textarea className="input min-h-[70px]" placeholder="Decision comment (required for rejection)…" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000} aria-label="Decision comment" />
        {m.isError && <p role="alert" className="text-sm text-red-300">{(m.error as Error).message}</p>}
        <div className="flex flex-wrap gap-2">
          <Button variant="success" disabled={!canDecide} loading={m.isPending && m.variables?.kind === "approve"} onClick={() => m.mutate({ kind: "approve", comment: comment || "Approved after review of evidence and verification report" })}><CheckCircle2 />Approve & send simulated notices</Button>
          <Button variant="danger" disabled={!canDecide || !comment.trim()} loading={m.isPending && m.variables?.kind === "reject"} onClick={() => m.mutate({ kind: "reject", comment })}><XCircle />Reject recommendation</Button>
        </div>
      </div>
    </Card>
  );
}

export default function RecallDetailPage() {
  const { id } = useParams();
  const q = useRecall(id);
  const [tab, setTab] = useState<"items" | "notices" | "excluded" | "report">("items");
  const [prio, setPrio] = useState<string>("ALL");
  const items = useMemo(() => (q.data?.items ?? []).filter((i) => prio === "ALL" || i.priority === prio), [q.data, prio]);

  if (q.isLoading) return <LoadingState rows={8} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const r = q.data!;
  const v = r.verification;
  const products = [...new Map(r.items.map((i) => [i.product_id, i.product_name])).entries()];
  const locations = new Set(r.items.map((i) => i.location_ref));

  return (
    <div>
      <PageHeader eyebrow={`${r.recall_id} · ${r.recall_class.replace("_", " ")}`} title={r.title}
        subtitle={<span className="flex flex-wrap items-center gap-2"><StatusBadge status={r.recall_status} /><RiskBadge value={r.risk_class} score={r.risk_score} /><span className="text-xs">Incident <Link className="text-cyan-300 hover:underline" to={`/incidents/${r.incident_id}`}>{r.incident_id}</Link> · source <span className="mono">{r.incident.source_ref}</span></span></span>}
        actions={<>
          <Button asChild size="sm" variant="ghost"><Link to={`/explorer?ref=${r.incident.source_ref}`}>Supply-chain graph</Link></Button>
          <Button asChild size="sm" variant="ghost"><Link to={`/investigations/${r.incident_id}`}>Agent outputs</Link></Button>
          {["EXECUTING", "COMPLETED"].includes(r.recall_status) && <Button asChild size="sm" variant="primary"><Link to={`/monitoring/${r.recall_id}`}>Monitor execution</Link></Button>}
        </>} />

      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {[["Batches", new Set(r.items.map((i) => i.batch_id)).size], ["Products", products.length], ["Locations", locations.size], ["Units to recover / quarantine", fmt(r.plan.total_units)]].map(([k, val]) => (
          <Card key={k as string} className="p-4"><p className="label">{k}</p><p className="mt-1 text-2xl font-semibold text-white">{val}</p></Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          <ApprovalPanel recallId={r.recall_id} status={r.recall_status} />
          {r.decided_by && (
            <Card className="p-4 text-sm">
              <p className="text-slate-200">{r.recall_status === "REJECTED" ? <ShieldX className="mr-1 inline size-4 text-red-400" /> : <ShieldCheck className="mr-1 inline size-4 text-emerald-400" />}
                Decision by <b>{r.decided_by}</b> on {fmtDate(r.decided_at)}</p>
              {r.decision_comment && <p className="mt-1 text-xs text-slate-400">“{r.decision_comment}”</p>}
            </Card>
          )}

          <Card>
            <CardHeader title="Recommended recall scope" subtitle={r.plan.summary} icon={<ClipboardCheck />} />
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2">
              <Tabs value={tab} onChange={setTab} items={[{ value: "items", label: `Items (${r.items.length})` }, { value: "notices", label: `Instructions (${r.plan.notifications.length})` }, { value: "excluded", label: `Excluded (${r.plan.excluded_batches.length})` }, { value: "report", label: "Recall report" }]} />
              {tab === "items" && <Tabs value={prio} onChange={setPrio} items={["ALL", "P1", "P2", "P3"].map((p) => ({ value: p, label: p }))} />}
            </div>
            {tab === "items" && (items.length === 0 ? <EmptyState title="No items for this filter" /> : (
              <div className="max-h-[560px] overflow-auto">
                <table className="w-full min-w-[900px]">
                  <thead className="sticky top-0 z-10 bg-ink-900"><tr>{["Pri", "Batch / product", "Location", "Units", "Basis", "Reason for inclusion", "Evidence"].map((h) => <th key={h} className="table-head">{h}</th>)}</tr></thead>
                  <tbody>
                    {items.map((i) => (
                      <tr key={i.item_id} className="border-t border-line align-top">
                        <td className="table-cell"><Badge tone={PRIO_TONE[i.priority]}>{i.priority}</Badge></td>
                        <td className="table-cell"><p className="mono text-cyan-300">{i.batch_id}</p><p className="text-xs text-slate-400">{i.product_name}</p></td>
                        <td className="table-cell"><p className="text-xs text-slate-100">{i.location_name}</p><p className="mono text-slate-500">{humanize(i.location_kind)} · {i.location_ref} · {i.city}</p></td>
                        <td className="table-cell tabular-nums">{fmt(i.quantity_units)}</td>
                        <td className="table-cell"><Badge tone={BASIS_TONE[i.inclusion_basis]}>{i.inclusion_basis}</Badge></td>
                        <td className="table-cell max-w-sm text-xs text-slate-300">{i.reason}</td>
                        <td className="table-cell mono max-w-[180px] break-words text-slate-500">{i.evidence_refs}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
            {tab === "notices" && (
              <ul className="max-h-[560px] divide-y divide-line overflow-auto">
                {r.plan.notifications.map((n) => (
                  <li key={n.location_ref} className="px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2"><Store className="size-3.5 text-slate-400" /><span className="text-sm text-slate-100">{n.location_name}</span><span className="mono text-slate-500">{n.location_ref}</span>{n.action_types.map((a) => <Badge key={a} tone={a === "NOTIFY" ? "cyan" : a === "RECOVER" ? "red" : "amber"}>{a}</Badge>)}</div>
                    <p className="mt-1.5 text-xs leading-relaxed text-slate-300">{n.instruction}</p>
                  </li>
                ))}
              </ul>
            )}
            {tab === "excluded" && (
              <div className="p-4">
                <p className="mb-3 text-xs text-slate-400">Targeted recall: these batches share a product SKU with recalled batches, but Db2 genealogy shows no path from the contaminated source. Whole-SKU withdrawal is avoided.</p>
                <ul className="space-y-1.5">{r.plan.excluded_batches.map((e) => <li key={e.batch_id} className="flex items-start gap-2 text-xs"><CheckCircle2 className="mt-0.5 size-3.5 text-emerald-400" /><span className="mono text-slate-200">{e.batch_id}</span><span className="text-slate-400">{e.reason}</span></li>)}</ul>
              </div>
            )}
            {tab === "report" && <pre className="mono m-4 max-h-[560px] overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-ink-950/80 p-4 text-slate-300">{r.plan.report_markdown}</pre>}
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Explainable risk score" subtitle={`Confidence ${r.risk.confidence} · data completeness ${r.risk.data_completeness_pct}%`} icon={<Gauge />} />
            <div className="space-y-2.5 p-4">
              <div className="flex items-baseline gap-2"><span className="text-4xl font-semibold text-white">{r.risk.score}</span><span className="text-sm text-slate-400">/ 100</span><RiskBadge value={r.risk.classification} /></div>
              {r.risk.factors.map((f) => (
                <div key={f.factor}>
                  <div className="flex justify-between text-xs"><span className="capitalize text-slate-300">{f.factor} <span className="text-slate-500">(w {f.weight})</span></span><span className="tabular-nums text-slate-100">+{f.contribution}</span></div>
                  <Progress value={(f.contribution / f.weight) * 100} tone={f.factor === "uncertainty" ? "amber" : f.factor === "severity" ? "red" : "cyan"} className="mt-1" />
                  <p className="mt-0.5 text-[11px] text-slate-500">{f.reason}</p>
                </div>
              ))}
              <p className="border-t border-line pt-2 text-[11px] italic text-slate-500">{r.risk.disclaimer}</p>
            </div>
          </Card>

          <Card>
            <CardHeader title="Independent verification" subtitle={v.summary} icon={<ShieldCheck />} action={<Badge tone={v.verdict === "PASS" ? "emerald" : v.verdict === "FAIL" ? "red" : "amber"}>{v.verdict}</Badge>} />
            <ul className="space-y-2 p-4">
              {v.checks.map((c, i) => (
                <li key={i} className="flex gap-2 text-xs">
                  {c.passed ? <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-emerald-400" /> : <AlertTriangle className={cn("mt-0.5 size-3.5 shrink-0", c.severity === "BLOCKER" ? "text-red-400" : "text-amber-400")} />}
                  <div><p className="text-slate-200">{c.check}</p><p className="text-slate-500">{c.detail}</p></div>
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <CardHeader title="Affected products" icon={<FileText />} />
            <ul className="space-y-1 p-4 text-xs">{products.map(([pid, name]) => <li key={pid} className="flex justify-between"><span className="text-slate-200">{name}</span><span className="mono text-slate-500">{pid}</span></li>)}</ul>
          </Card>
          {r.plan.consumer_notice_recommended && (
            <Card className="border-red-500/30 p-4 text-xs text-red-200"><Megaphone className="mr-1 inline size-4" />Consumer-level public notice recommended (Class I, product reached retail). Requires regulatory sign-off — not generated automatically.</Card>
          )}
        </div>
      </div>
    </div>
  );
}
