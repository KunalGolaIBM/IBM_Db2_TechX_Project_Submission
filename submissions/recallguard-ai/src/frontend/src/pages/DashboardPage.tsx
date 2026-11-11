import { Link } from "react-router-dom";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertOctagon, ArrowRight, Boxes, ClipboardCheck, FlaskConical, MapPin, PackageSearch, ShieldAlert, Siren, Timer } from "lucide-react";
import { useDashboard, useIncidents } from "@/hooks/queries";
import { useDemo } from "@/hooks/useDemo";
import { Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, StatCard } from "@/components/ui";
import { SeverityBadge, StatusBadge } from "@/components/shared";
import { fmt, fmtDate, humanize, timeAgo } from "@/lib/utils";

const RISK_COLORS: Record<string, string> = { CRITICAL: "#f87171", HIGH: "#fbbf24", MODERATE: "#22d3ee", LOW: "#34d399" };
const tooltipStyle = { background: "#0d172b", border: "1px solid rgba(148,163,184,.15)", borderRadius: 8, fontSize: 12, color: "#e2e8f0" };

export default function DashboardPage() {
  const dash = useDashboard();
  const incidents = useIncidents();
  const { run, running } = useDemo();

  if (dash.isLoading) return <LoadingState label="Loading dashboard" rows={6} />;
  if (dash.isError) return <ErrorState error={dash.error} onRetry={() => dash.refetch()} />;
  const d = dash.data!;
  const k = d.kpis;
  const risk = ["CRITICAL", "HIGH", "MODERATE", "LOW"].map((c) => ({ name: c, value: d.risk_distribution.find((r) => r.risk_class === c)?.n ?? 0 })).filter((r) => r.value > 0);
  const status = d.status_distribution.map((s) => ({ name: humanize(s.incident_status), n: s.n }));
  const network = [
    ["Suppliers", d.network.suppliers], ["Ingredient lots", d.network.lots], ["Batches", d.network.batches], ["Products", d.network.products],
    ["Warehouses", d.network.warehouses], ["Distributors", d.network.distributors], ["Retailers", d.network.retailers], ["Shipments", d.network.shipments],
  ] as const;

  return (
    <div>
      <PageHeader eyebrow="Executive overview" title="Food-safety command centre"
        subtitle="Live view of contamination incidents, Db2-traced exposure and recall execution across the supply network."
        actions={<Button variant="primary" onClick={run} loading={running}><FlaskConical />Run Tomato Contamination Demo</Button>} />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" data-testid="kpis">
        <StatCard label="Total incidents" value={fmt(k.total_incidents)} icon={<Siren />} tone="slate" hint={`${k.active_incidents} active · ${k.critical_incidents} critical`} />
        <StatCard label="Products under investigation" value={fmt(k.products_under_investigation)} icon={<PackageSearch />} tone="amber" />
        <StatCard label="Potentially affected batches" value={fmt(k.batches_potentially_affected)} icon={<Boxes />} tone="red" />
        <StatCard label="Affected locations" value={fmt(k.locations_affected)} icon={<MapPin />} tone="violet" hint="warehouses, distributors, retailers" />
        <StatCard label="Pending approvals" value={fmt(k.pending_approvals)} icon={<Timer />} tone="amber" />
        <StatCard label="Active recalls" value={fmt(k.active_recalls)} icon={<ShieldAlert />} tone="cyan" hint={`${k.completed_recalls} completed`} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader title="Recall risk distribution" subtitle="Explainable risk class of current recall plans" icon={<AlertOctagon />} />
          {risk.length === 0 ? <EmptyState title="No recall plans yet" /> : (
            <div className="flex flex-wrap items-center gap-4 p-4">
              <div className="h-44 w-44 shrink-0">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={risk} dataKey="value" innerRadius={48} outerRadius={72} paddingAngle={2} stroke="none">
                      {risk.map((r) => <Cell key={r.name} fill={RISK_COLORS[r.name]} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="space-y-2 text-sm">
                {risk.map((r) => (
                  <li key={r.name} className="flex items-center gap-2"><span className="size-2.5 rounded-sm" style={{ background: RISK_COLORS[r.name] }} /><span className="text-slate-300">{r.name}</span><span className="ml-auto pl-4 tabular-nums text-white">{r.value}</span></li>
                ))}
              </ul>
            </div>
          )}
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader title="Incidents by workflow state" icon={<ClipboardCheck />} />
          <div className="h-52 p-3">
            <ResponsiveContainer>
              <BarChart data={status} layout="vertical" margin={{ left: 20, right: 12 }}>
                <XAxis type="number" allowDecimals={false} tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={120} tick={{ fill: "#94a3b8", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(148,163,184,.06)" }} />
                <Bar dataKey="n" fill="#22d3ee" radius={[0, 4, 4, 0]} barSize={14} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader title="Supply-chain overview" subtitle={`Records in ${d.engine}`} icon={<Boxes />} />
          <div className="grid grid-cols-2 gap-2 p-4">
            {network.map(([label, v]) => (
              <div key={label} className="rounded-lg border border-line bg-ink-950/50 px-3 py-2">
                <p className="text-[11px] text-slate-500">{label}</p>
                <p className="text-lg font-semibold tabular-nums text-slate-100">{fmt(v)}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-3">
          <CardHeader title="Incidents" icon={<Siren />} action={<Button asChild size="sm" variant="ghost"><Link to="/incidents">All <ArrowRight /></Link></Button>} />
          {incidents.isLoading ? <LoadingState /> : incidents.isError ? <ErrorState error={incidents.error} /> : (incidents.data?.length ?? 0) === 0 ? (
            <EmptyState title="No incidents yet" hint="Run the tomato demo to register the first incident." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px]">
                <thead><tr><th className="table-head">Incident</th><th className="table-head">Source</th><th className="table-head">Severity</th><th className="table-head">Status</th><th className="table-head">Discovered</th></tr></thead>
                <tbody>
                  {incidents.data!.slice(0, 6).map((i) => (
                    <tr key={i.incident_id} className="border-t border-line hover:bg-ink-800/40">
                      <td className="table-cell"><Link to={`/incidents/${i.incident_id}`} className="font-medium text-slate-100 hover:text-cyan-300">{i.title}</Link><p className="mono text-slate-500">{i.incident_id}</p></td>
                      <td className="table-cell mono">{i.source_ref}</td>
                      <td className="table-cell"><SeverityBadge value={i.severity} /></td>
                      <td className="table-cell"><StatusBadge status={i.incident_status} /></td>
                      <td className="table-cell text-xs text-slate-400">{fmtDate(i.discovered_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader title="Recent activity" subtitle="From the Db2 audit log" icon={<Timer />} />
          {d.timeline.length === 0 ? <EmptyState title="No activity yet" /> : (
            <ol className="relative space-y-3 p-4 before:absolute before:bottom-4 before:left-[21px] before:top-4 before:w-px before:bg-line">
              {d.timeline.map((t, i) => (
                <li key={i} className="relative flex gap-3 pl-6">
                  <span className="absolute left-[3px] top-1.5 size-2 rounded-full bg-cyan-400 ring-4 ring-ink-900" />
                  <div className="min-w-0">
                    <p className="text-[13px] text-slate-200">{humanize(t.action_name)} <span className="mono text-cyan-300">{t.entity_ref}</span></p>
                    <p className="text-[11px] text-slate-500">{t.actor} · {timeAgo(t.occurred_at)}</p>
                  </div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>
    </div>
  );
}
