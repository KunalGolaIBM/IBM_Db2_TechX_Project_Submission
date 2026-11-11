import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, PackageCheck, Radar, Radio, Timer, Warehouse } from "lucide-react";
import { useAudit, useRecall, useRecalls, useRefreshAll } from "@/hooks/queries";
import { api, ApiError, getRole } from "@/services/api";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, Progress, StatCard } from "@/components/ui";
import { StatusBadge } from "@/components/shared";
import { fmt, fmtDate, humanize } from "@/lib/utils";

const NEXT: Record<string, Record<string, string>> = { NOTIFY: { SENT: "ACKNOWLEDGED" }, QUARANTINE: { PENDING: "IN_PROGRESS", IN_PROGRESS: "DONE" }, RECOVER: { PENDING: "IN_PROGRESS", IN_PROGRESS: "DONE" } };

export default function MonitoringPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const list = useRecalls();
  const active = (list.data ?? []).filter((r) => ["EXECUTING", "COMPLETED", "APPROVED"].includes(r.recall_status));
  const rid = id ?? active[0]?.recall_id;
  const q = useRecall(rid);
  const audit = useAudit(rid);
  const refresh = useRefreshAll();
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const canAct = ["recall_manager", "admin"].includes(getRole());
  const act = async (key: string, fn: () => Promise<unknown>) => { setBusy(key); setErr(null); try { await fn(); await refresh(); } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)); } finally { setBusy(null); } };

  return (
    <div>
      <PageHeader eyebrow="Recall monitoring" title="Recall execution"
        subtitle="Simulated partner acknowledgements, quarantine status and recovered quantities, all tracked in Db2 RECALL_ACTIONS."
        actions={<select aria-label="Select recall" className="input max-w-sm" value={rid ?? ""} onChange={(e) => nav(`/monitoring/${e.target.value}`)}>
          {active.length === 0 && <option value="">No executing recalls</option>}
          {active.map((r) => <option key={r.recall_id} value={r.recall_id}>{r.recall_id} — {r.source_ref} ({humanize(r.recall_status)})</option>)}
        </select>} />
      {list.isLoading ? <LoadingState /> : !rid ? <Card><EmptyState title="No recall is executing yet" hint="Approve a recall plan to start execution." action={<Button asChild variant="primary"><Link to="/recalls">Go to recall plans</Link></Button>} /></Card> :
        q.isLoading ? <LoadingState rows={6} /> : q.isError ? <ErrorState error={q.error} /> : (() => {
          const r = q.data!;
          const p = r.progress;
          const notify = r.actions.filter((a) => a.action_type === "NOTIFY");
          const phys = r.actions.filter((a) => a.action_type !== "NOTIFY");
          return (
            <>
              <Card className="mb-4 flex flex-wrap items-center gap-3 p-4">
                <Link to={`/recalls/${r.recall_id}`} className="text-sm font-medium text-slate-100 hover:text-cyan-300">{r.title}</Link>
                <StatusBadge status={r.recall_status} /><Badge tone="amber">Channel: SIMULATED</Badge>
                {canAct && r.recall_status === "EXECUTING" && (
                  <div className="ml-auto flex gap-2">
                    <Button size="sm" variant="secondary" loading={busy === "sim"} onClick={() => act("sim", () => api.simulateAcks(r.recall_id))}><Radio />Simulate partner responses</Button>
                    <Button size="sm" variant="success" disabled={p.open_actions > 0} loading={busy === "done"} onClick={() => act("done", () => api.completeRecall(r.recall_id, "All actions closed"))}><CheckCircle2 />Complete recall</Button>
                  </div>
                )}
              </Card>
              {err && <p role="alert" className="mb-3 text-sm text-red-300">{err}</p>}
              <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
                <StatCard label="Acknowledged" value={`${p.acknowledged}/${p.locations_notified}`} icon={<Radio />} tone="cyan" />
                <StatCard label="Quarantine complete" value={`${p.quarantine_done}/${p.quarantine_total}`} icon={<Warehouse />} tone="amber" />
                <StatCard label="Units recovered" value={fmt(p.units_recovered)} icon={<PackageCheck />} tone="emerald" hint={`of ${fmt(p.units_expected)} (${p.recovery_pct}%)`} />
                <StatCard label="Outstanding actions" value={p.open_actions} icon={<Timer />} tone={p.open_actions ? "red" : "emerald"} />
              </div>
              <Card className="mb-4 p-4"><div className="mb-1 flex justify-between text-xs text-slate-400"><span>Recovery progress</span><span>{p.recovery_pct}%</span></div><Progress value={p.recovery_pct} tone="emerald" /></Card>

              <div className="grid gap-4 xl:grid-cols-3">
                <Card className="xl:col-span-2">
                  <CardHeader title="Quarantine & recovery actions" icon={<Radar />} />
                  <div className="max-h-[520px] overflow-auto">
                    <table className="w-full min-w-[720px]">
                      <thead className="sticky top-0 bg-ink-900"><tr>{["Location", "Action", "Status", "Units", "Updated", ""].map((h) => <th key={h} className="table-head">{h}</th>)}</tr></thead>
                      <tbody>
                        {[...phys, ...notify].map((a) => {
                          const next = NEXT[a.action_type]?.[a.action_status];
                          return (
                            <tr key={a.action_id} className="border-t border-line">
                              <td className="table-cell"><p className="text-xs text-slate-100">{a.location_name}</p><p className="mono text-slate-500">{humanize(a.location_kind)} · {a.location_ref}</p></td>
                              <td className="table-cell"><Badge tone={a.action_type === "NOTIFY" ? "cyan" : a.action_type === "RECOVER" ? "red" : "amber"}>{a.action_type}</Badge></td>
                              <td className="table-cell"><Badge tone={["DONE", "ACKNOWLEDGED"].includes(a.action_status) ? "emerald" : a.action_status === "IN_PROGRESS" ? "amber" : "slate"} dot>{humanize(a.action_status)}</Badge></td>
                              <td className="table-cell whitespace-nowrap tabular-nums text-xs">{a.action_type === "NOTIFY" ? "—" : `${fmt(a.units_recovered)} / ${fmt(a.units_expected)}`}</td>
                              <td className="table-cell text-[11px] text-slate-500">{a.updated_by}<br />{fmtDate(a.updated_at)}</td>
                              <td className="table-cell">{canAct && next && r.recall_status === "EXECUTING" && <Button size="sm" variant="ghost" loading={busy === a.action_id} onClick={() => act(a.action_id, () => api.updateAction(r.recall_id, a.action_id, next))}>Mark {humanize(next).toLowerCase()}</Button>}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </Card>
                <Card>
                  <CardHeader title="Execution timeline" subtitle="Db2 audit log" icon={<Timer />} />
                  {audit.isLoading ? <LoadingState /> : (
                    <ol className="max-h-[520px] space-y-3 overflow-auto p-4">
                      {(audit.data ?? []).map((l) => (
                        <li key={l.audit_id} className="border-l border-cyan-500/30 pl-3">
                          <p className="text-xs text-slate-200">{humanize(l.action_name)}</p>
                          <p className="text-[10px] text-slate-500">{l.actor} · {fmtDate(l.occurred_at)}</p>
                        </li>
                      ))}
                    </ol>
                  )}
                </Card>
              </div>
            </>
          );
        })()}
    </div>
  );
}
