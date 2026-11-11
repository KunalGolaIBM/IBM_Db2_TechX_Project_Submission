import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BrainCircuit, ClipboardCheck, FileText, GitBranch, MessageSquare, RefreshCw, Upload } from "lucide-react";
import { useAudit, useIncident, useRefreshAll } from "@/hooks/queries";
import { api, ApiError } from "@/services/api";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import { KV, SeverityBadge, StatusBadge, StatusStepper } from "@/components/shared";
import { fmtDate, humanize } from "@/lib/utils";

export default function IncidentDetailPage() {
  const { id } = useParams();
  const q = useIncident(id);
  const audit = useAudit(id);
  const refresh = useRefreshAll();
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  if (q.isLoading) return <LoadingState rows={6} />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const inc = q.data!;
  const act = async (key: string, fn: () => Promise<unknown>) => {
    setBusy(key); setErr(null);
    try { await fn(); await refresh(); } catch (e) { setErr(e instanceof ApiError ? e.message : String(e)); } finally { setBusy(null); }
  };
  const canInvestigate = ["REPORTED", "INVESTIGATING", "EVIDENCE_REVIEW", "RECALL_RECOMMENDED", "PENDING_APPROVAL", "REJECTED"].includes(inc.incident_status);
  const activeRecall = inc.recalls?.find((r) => r.recall_status !== "SUPERSEDED");

  return (
    <div>
      <PageHeader eyebrow={inc.incident_id} title={inc.title}
        subtitle={<span className="flex flex-wrap items-center gap-2"><SeverityBadge value={inc.severity} /><StatusBadge status={inc.incident_status} />{inc.is_demo && <Badge tone="violet">demo</Badge>}</span>}
        actions={<>
          <Button asChild size="sm" variant="ghost"><Link to={`/explorer?ref=${inc.source_ref}`}><GitBranch />Trace</Link></Button>
          <Button asChild size="sm" variant="secondary"><Link to={`/investigations/${inc.incident_id}`}><BrainCircuit />Agents</Link></Button>
          {inc.incident_status === "REPORTED" && <Button size="sm" variant="primary" loading={busy === "inv"} onClick={() => act("inv", () => api.investigate(inc.incident_id))}><BrainCircuit />Initiate AI investigation</Button>}
          {inc.incident_status === "RECALL_RECOMMENDED" && <Button size="sm" variant="primary" loading={busy === "gen"} onClick={() => act("gen", () => api.generateRecall(inc.incident_id))}><ClipboardCheck />Generate recall plan</Button>}
          {activeRecall && <Button asChild size="sm" variant="primary"><Link to={`/recalls/${activeRecall.recall_id}`}><ClipboardCheck />Recall {activeRecall.recall_id}</Link></Button>}
        </>} />
      {err && <p role="alert" className="mb-3 rounded-md border border-red-500/30 bg-red-500/5 p-2 text-sm text-red-300">{err}</p>}
      <Card className="mb-4 p-4"><StatusStepper status={inc.incident_status} /></Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Incident details" icon={<FileText />} />
          <div className="p-4">
            <KV k="Source" v={`${inc.source_kind} ${inc.source_ref}`} mono />
            <KV k="Contaminant" v={inc.contaminant} />
            <KV k="Category" v={humanize(inc.contamination_category)} />
            <KV k="Supplier" v={inc.supplier_name ? `${inc.supplier_name} (${inc.supplier_id})` : "—"} />
            <KV k="Reported by" v={inc.reported_by} />
            <KV k="Discovered" v={fmtDate(inc.discovered_at)} />
            {inc.description && <p className="mt-3 text-xs leading-relaxed text-slate-400">{inc.description}</p>}
          </div>
          {canInvestigate && inc.incident_status !== "REPORTED" && (
            <div className="border-t border-line p-4">
              <Button size="sm" variant="outline" loading={busy === "re"} onClick={() => act("re", () => api.reinvestigate(inc.incident_id, comment || "Requested from incident page"))}><RefreshCw />Request another investigation</Button>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Evidence" icon={<Upload />} subtitle={`${inc.evidence?.length ?? 0} document(s)`} action={
            <label className="cursor-pointer text-xs text-cyan-300 hover:underline">
              Upload<input type="file" className="sr-only" accept=".pdf,.txt,.md,.csv" aria-label="Upload evidence"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) act("up", () => api.upload(f, f.name, inc.incident_id)); }} />
            </label>} />
          {(inc.evidence?.length ?? 0) === 0 ? <EmptyState title="No evidence attached" hint="Upload the laboratory report to ground the investigation." /> : (
            <ul className="divide-y divide-line">
              {inc.evidence!.map((d) => (
                <li key={d.document_id} className="px-4 py-2.5">
                  <p className="truncate text-sm text-slate-100">{d.filename}</p>
                  <p className="mono text-slate-500">{d.document_id} · {humanize(d.doc_type)} · {d.extracted.claims.length} claims · {d.extracted.summary.positive_results} positive</p>
                  <Badge tone={d.verification_status === "VERIFIED" ? "emerald" : d.verification_status === "DISPUTED" ? "red" : "slate"} className="mt-1">{d.verification_status}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="Comments & review notes" icon={<MessageSquare />} />
          <div className="max-h-64 space-y-2 overflow-y-auto p-4">
            {(inc.comments?.length ?? 0) === 0 && <p className="text-xs text-slate-500">No comments yet.</p>}
            {inc.comments?.map((c) => (
              <div key={c.comment_id} className="rounded-lg border border-line bg-ink-950/50 p-2.5">
                <p className="text-xs text-slate-200">{c.body}</p>
                <p className="mt-1 text-[10px] text-slate-500">{c.author} · {humanize(c.author_role)} · {fmtDate(c.created_at)}</p>
              </div>
            ))}
          </div>
          <div className="flex gap-2 border-t border-line p-3">
            <input className="input" placeholder="Add a review comment…" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={2000} aria-label="Comment" />
            <Button size="sm" disabled={!comment.trim()} loading={busy === "c"} onClick={() => act("c", async () => { await api.comment(inc.incident_id, comment); setComment(""); })}>Post</Button>
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader title="Audit trail" subtitle="Every change, recorded in Db2 AUDIT_LOGS" icon={<FileText />} />
        {audit.isLoading ? <LoadingState /> : (audit.data?.length ?? 0) === 0 ? <EmptyState title="No audit entries" /> : (
          <div className="max-h-80 overflow-auto">
            <table className="w-full min-w-[720px]">
              <thead className="sticky top-0 bg-ink-900"><tr><th className="table-head">Time</th><th className="table-head">Actor</th><th className="table-head">Action</th><th className="table-head">Details</th></tr></thead>
              <tbody>{audit.data!.map((a) => (
                <tr key={a.audit_id} className="border-t border-line align-top">
                  <td className="table-cell whitespace-nowrap text-xs text-slate-400">{fmtDate(a.occurred_at)}</td>
                  <td className="table-cell text-xs">{a.actor}<p className="text-[10px] text-slate-500">{a.actor_role}</p></td>
                  <td className="table-cell text-xs">{humanize(a.action_name)}</td>
                  <td className="table-cell mono max-w-md break-words text-slate-400">{a.details}</td>
                </tr>))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
