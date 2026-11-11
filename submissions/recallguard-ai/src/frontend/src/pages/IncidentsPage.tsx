import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { FilePlus2, Siren, Upload } from "lucide-react";
import { useCatalog, useIncidents } from "@/hooks/queries";
import { api, ApiError } from "@/services/api";
import { Button, Card, CardHeader, EmptyState, ErrorState, Field, LoadingState, PageHeader } from "@/components/ui";
import { SeverityBadge, StatusBadge } from "@/components/shared";
import { fmtDate } from "@/lib/utils";

const CATEGORIES = ["MICROBIAL", "CHEMICAL", "PHYSICAL", "ALLERGEN", "OTHER"];
const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

export function IncidentForm() {
  const nav = useNavigate();
  const qc = useQueryClient();
  const catalog = useCatalog();
  const [form, setForm] = useState({ title: "", source_ref: "", contaminant: "", contamination_category: "MICROBIAL", severity: "HIGH", supplier_id: "", description: "" });
  const [file, setFile] = useState<File | null>(null);
  const [start, setStart] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string | null>(null);
  const set = (k: keyof typeof form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      setProgress("Registering incident in Db2…");
      const inc = await api.createIncident({ ...form, supplier_id: form.supplier_id || undefined, description: form.description || undefined });
      if (file) {
        setProgress("Uploading & parsing laboratory report…");
        await api.upload(file, file.name, inc.incident_id);
      }
      if (start) {
        setProgress("Starting AI investigation…");
        await api.investigate(inc.incident_id);
      }
      await qc.invalidateQueries();
      nav(start ? `/investigations/${inc.incident_id}` : `/incidents/${inc.incident_id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false); setProgress(null);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-3 p-4" aria-label="Create incident">
      <Field label="Incident title"><input className="input" required minLength={5} maxLength={160} value={form.title} onChange={set("title")} placeholder="e.g. Salmonella in tomato puree lot" /></Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Affected ingredient lot or batch ID" hint="Must exist in Db2 (validated server-side)">
          <input className="input mono uppercase" required list="refs" value={form.source_ref} onChange={set("source_ref")} placeholder="TOM-2026-041" pattern="[A-Za-z0-9][A-Za-z0-9-]{2,29}" />
          <datalist id="refs">
            {catalog.data?.lots.map((l) => <option key={l.lot_id} value={l.lot_id}>{l.ingredient_name} · {l.supplier_name}</option>)}
            {catalog.data?.batches.map((b) => <option key={b.batch_id} value={b.batch_id}>{b.product_name ?? b.description}</option>)}
          </datalist>
        </Field>
        <Field label="Contaminant"><input className="input" required minLength={2} value={form.contaminant} onChange={set("contaminant")} placeholder="Salmonella Typhimurium" /></Field>
        <Field label="Contamination category">
          <select className="input" value={form.contamination_category} onChange={set("contamination_category")}>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select>
        </Field>
        <Field label="Severity">
          <select className="input" value={form.severity} onChange={set("severity")}>{SEVERITIES.map((c) => <option key={c}>{c}</option>)}</select>
        </Field>
        <Field label="Supplier (optional)" hint="Auto-resolved from the lot when blank">
          <select className="input" value={form.supplier_id} onChange={set("supplier_id")}>
            <option value="">Auto from lot</option>
            {catalog.data?.suppliers.map((s) => <option key={s.supplier_id} value={s.supplier_id}>{s.supplier_name}</option>)}
          </select>
        </Field>
        <Field label="Laboratory report (PDF/TXT/MD/CSV, ≤10 MB)">
          <label className="input flex cursor-pointer items-center gap-2 text-slate-400">
            <Upload className="size-4" /><span className="truncate">{file ? file.name : "Choose file…"}</span>
            <input type="file" className="sr-only" accept=".pdf,.txt,.md,.csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} aria-label="Laboratory report" />
          </label>
        </Field>
      </div>
      <Field label="Description"><textarea className="input min-h-[70px]" maxLength={2000} value={form.description} onChange={set("description")} /></Field>
      <label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={start} onChange={(e) => setStart(e.target.checked)} className="accent-cyan-400" />Initiate AI investigation immediately</label>
      {error && <p role="alert" className="rounded-md border border-red-500/30 bg-red-500/5 p-2 text-sm text-red-300">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" variant="primary" loading={busy}><FilePlus2 />Register incident</Button>
        {progress && <span className="text-xs text-slate-400">{progress}</span>}
      </div>
    </form>
  );
}

export default function IncidentsPage() {
  const q = useIncidents();
  return (
    <div>
      <PageHeader eyebrow="Incident investigation" title="Contamination incidents" subtitle="Register a contamination report against an ingredient lot or production batch, attach the laboratory report, and launch the multi-agent investigation." />
      <div className="grid gap-4 xl:grid-cols-5">
        <Card className="xl:col-span-2"><CardHeader title="New contamination incident" icon={<FilePlus2 />} /><IncidentForm /></Card>
        <Card className="xl:col-span-3">
          <CardHeader title="All incidents" icon={<Siren />} subtitle={q.data ? `${q.data.length} total` : undefined} />
          {q.isLoading ? <LoadingState /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : q.data!.length === 0 ? <EmptyState title="No incidents" /> : (
            <ul className="divide-y divide-line">
              {q.data!.map((i) => (
                <li key={i.incident_id}>
                  <Link to={`/incidents/${i.incident_id}`} className="flex flex-col gap-2 px-4 py-3 hover:bg-ink-800/40 sm:flex-row sm:items-center">
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-slate-100">{i.title}</p>
                      <p className="mono text-slate-500">{i.incident_id} · {i.source_ref} · {i.supplier_name ?? "—"} · {fmtDate(i.discovered_at)}{i.is_demo ? " · demo" : ""}</p>
                    </div>
                    <div className="flex items-center gap-2"><SeverityBadge value={i.severity} /><StatusBadge status={i.incident_status} /></div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
