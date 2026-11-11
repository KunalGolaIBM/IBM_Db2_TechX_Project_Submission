import { useState } from "react";
import { BrainCircuit, Database, HeartPulse, RotateCcw, ShieldCheck, Users } from "lucide-react";
import { useHealth, useRefreshAll } from "@/hooks/queries";
import { api, ApiError, getRole, USERS } from "@/services/api";
import { Badge, Button, Card, CardHeader, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import { KV } from "@/components/shared";

const MATRIX: [string, string[]][] = [
  ["View dashboards, traces, evidence", ["viewer", "analyst", "recall_manager", "admin"]],
  ["Create incidents, upload evidence, run investigations", ["analyst", "recall_manager", "admin"]],
  ["Generate recall plans", ["analyst", "recall_manager", "admin"]],
  ["Approve / reject recalls, verify evidence", ["recall_manager", "admin"]],
  ["Update recall actions", ["recall_manager", "admin"]],
  ["See supplier contact details", ["recall_manager", "admin"]],
];

export default function SettingsPage() {
  const h = useHealth();
  const refresh = useRefreshAll();
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (h.isLoading) return <LoadingState rows={6} />;
  if (h.isError) return <ErrorState error={h.error} onRetry={() => h.refetch()} />;
  const d = h.data!;
  const db = d.database;
  const integ = d.integrations as Record<string, any>;

  return (
    <div>
      <PageHeader eyebrow="Settings" title="System configuration & health" />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Database connection" icon={<Database />} action={<Badge tone={db.is_ibm_db2 && db.connected ? "emerald" : "amber"} dot>{db.is_ibm_db2 ? (db.connected ? "IBM Db2 connected" : "IBM Db2 unreachable") : "DEV MODE"}</Badge>} />
          <div className="p-4">
            <KV k="Mode" v={db.mode} mono />
            <KV k="Engine" v={db.label} />
            {db.target && <KV k="Target" v={db.target} mono />}
            <KV k="Server" v={db.server} />
            <KV k="Latency" v={db.latency_ms !== undefined ? `${db.latency_ms} ms` : "—"} />
            <KV k="Db2 VECTOR type" v={db.vector_supported ? "supported (langchain-db2 DB2VS active)" : "not available — JSON-vector fallback"} />
            {db.warning && <p className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-xs text-amber-200">{db.warning}</p>}
            {db.error && <p className="mt-3 rounded-md border border-red-500/30 bg-red-500/5 p-2 text-xs text-red-200">{db.error}</p>}
          </div>
        </Card>
        <Card>
          <CardHeader title="AI provider" icon={<BrainCircuit />} action={<Badge tone={d.ai.configured ? "violet" : "amber"}>{d.ai.mode}</Badge>} />
          <div className="p-4">
            <KV k="Provider" v={d.ai.provider} mono />
            <KV k="Model" v={d.ai.model ?? "—"} mono />
            <KV k="Configured" v={d.ai.configured ? "yes" : "no"} />
            {d.ai.note && <p className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/5 p-2 text-xs text-amber-200">{d.ai.note}</p>}
            <p className="mt-3 text-[11px] text-slate-500">Configure with LLM_PROVIDER, LLM_MODEL and the provider key in backend/.env. Facts always come from Db2 regardless of mode.</p>
          </div>
        </Card>
        <Card>
          <CardHeader title="System health & integrations" icon={<HeartPulse />} action={<Badge tone={d.status === "ok" ? "emerald" : "red"} dot>{d.status}</Badge>} />
          <div className="p-4">
            {Object.entries(integ).map(([k, v]) => <KV key={k} k={k} v={typeof v === "string" ? v : v.installed ? `installed ${v.version ?? ""}` : "missing"} />)}
            <KV k="Python" v={d.python} mono />
          </div>
        </Card>
        <Card>
          <CardHeader title="Demo data management" icon={<RotateCcw />} />
          <div className="space-y-3 p-4 text-sm text-slate-300">
            <p>Seed data (12 suppliers, 27 lots, 33 batches, 192 shipments) is loaded by the migration runner. Demo incidents created by the tomato demo are flagged <code className="mono">is_demo = 1</code> and can be removed without touching seed or historical data.</p>
            <Button variant="danger" loading={busy} disabled={!["recall_manager", "admin"].includes(getRole())}
              onClick={async () => { setBusy(true); setMsg(null); try { const r = await api.resetDemo(); setMsg(`Removed ${r.removed_incidents.length} demo incident(s).`); await refresh(); } catch (e) { setMsg(e instanceof ApiError ? e.message : String(e)); } setBusy(false); }}>
              <RotateCcw />Reset demo incidents
            </Button>
            {msg && <p className="text-xs text-slate-400">{msg}</p>}
          </div>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="User roles & permissions" subtitle={`Acting as ${USERS[getRole()]} (${getRole()}). Identity is sent as X-User-Id / X-User-Role headers — swap for OIDC/JWT in production.`} icon={<Users />} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead><tr><th className="table-head">Capability</th>{["viewer", "analyst", "recall_manager", "admin"].map((r) => <th key={r} className="table-head text-center">{r}</th>)}</tr></thead>
              <tbody>{MATRIX.map(([cap, roles]) => (
                <tr key={cap} className="border-t border-line"><td className="table-cell text-xs">{cap}</td>
                  {["viewer", "analyst", "recall_manager", "admin"].map((r) => <td key={r} className="table-cell text-center">{roles.includes(r) ? <ShieldCheck className="mx-auto size-4 text-emerald-400" aria-label="allowed" /> : <span className="text-slate-600">—</span>}</td>)}
                </tr>))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
