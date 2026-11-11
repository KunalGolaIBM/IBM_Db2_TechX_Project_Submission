import { useState, type FormEvent } from "react";
import { FileSearch, FileText, Search, Upload } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useEvidence, useRefreshAll } from "@/hooks/queries";
import { api, ApiError, getRole } from "@/services/api";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader, Tabs } from "@/components/ui";
import { cn, fmtDate, humanize } from "@/lib/utils";
import type { EvidenceDoc } from "@/types";

const TYPES = ["ALL", "LAB_REPORT", "SUPPLIER_CERTIFICATE", "QC_RECORD", "CONTAMINATION_NOTICE", "OTHER"];
const VER_TONE = { VERIFIED: "emerald", DISPUTED: "red", UNVERIFIED: "slate" } as const;

function DocDetail({ d }: { d: EvidenceDoc }) {
  const refresh = useRefreshAll();
  const canVerify = ["recall_manager", "admin"].includes(getRole());
  const [err, setErr] = useState<string | null>(null);
  const setV = async (s: string) => { try { setErr(null); await api.setVerification(d.document_id, s); await refresh(); } catch (e) { setErr(String((e as Error).message)); } };
  const groups = d.extracted.claims.reduce<Record<string, typeof d.extracted.claims>>((acc, c) => ((acc[c.type] ||= []).push(c), acc), {});
  return (
    <div className="p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Badge tone={VER_TONE[d.verification_status]}>{d.verification_status}</Badge>
        <span className="mono text-slate-500">{d.document_id} · sha256 {d.sha256.slice(0, 12)}… · {d.page_count} page(s)</span>
        {canVerify && <div className="ml-auto flex gap-1">{["VERIFIED", "DISPUTED", "UNVERIFIED"].map((s) => <Button key={s} size="sm" variant={s === "VERIFIED" ? "success" : s === "DISPUTED" ? "danger" : "ghost"} disabled={d.verification_status === s} onClick={() => setV(s)}>{humanize(s)}</Button>)}</div>}
      </div>
      {err && <p className="mb-2 text-xs text-red-300">{err}</p>}
      <p className="mb-3 text-[11px] text-slate-500">{d.extracted.method}. Each claim cites page and section; nothing is inferred beyond the document text.</p>
      {Object.keys(groups).length === 0 ? <EmptyState title="No claims extracted" /> : Object.entries(groups).map(([type, claims]) => (
        <div key={type} className="mb-3">
          <p className="label mb-1.5">{humanize(type)} ({claims.length})</p>
          <ul className="space-y-1.5">
            {claims.map((c, i) => (
              <li key={i} className={cn("rounded-lg border p-2", c.positive ? "border-red-500/30 bg-red-500/5" : "border-line bg-ink-950/50")}>
                <div className="flex flex-wrap items-center gap-2"><span className="text-xs font-medium text-slate-100">{c.value}</span>
                  {c.exists_in_db === false && <Badge tone="amber">not in Db2</Badge>}{c.exists_in_db && <Badge tone="emerald">matches Db2</Badge>}{c.positive && <Badge tone="red">positive</Badge>}
                  <span className="mono ml-auto text-slate-500">p.{c.page}{c.section ? ` · ${c.section}` : ""}</span></div>
                {c.type !== "test_result" && <p className="mt-1 text-[11px] text-slate-400">“{c.snippet}”</p>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

export default function EvidencePage() {
  const docs = useEvidence();
  const refresh = useRefreshAll();
  const [type, setType] = useState("ALL");
  const [sel, setSel] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [upErr, setUpErr] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const search = useQuery({ queryKey: ["search", query], queryFn: () => api.searchEvidence(query), enabled: query.length >= 2 });

  const list = (docs.data ?? []).filter((d) => type === "ALL" || d.doc_type === type);
  const current = docs.data?.find((d) => d.document_id === sel) ?? list[0];
  const onSearch = (e: FormEvent) => { e.preventDefault(); setQuery(q.trim()); };
  const onUpload = async (f?: File) => {
    if (!f) return;
    setUploading(true); setUpErr(null);
    try { const d = await api.upload(f, f.name); await refresh(); setSel(d.document_id); } catch (e) { setUpErr(e instanceof ApiError ? e.message : String(e)); } finally { setUploading(false); }
  };

  return (
    <div>
      <PageHeader eyebrow="Evidence vault" title="Evidence & document intelligence"
        subtitle="Laboratory reports, supplier certificates, QC records and contamination notices — parsed, chunked, embedded and stored in Db2 for cited retrieval."
        actions={<label className="inline-flex"><Button asChild variant="primary" loading={uploading}><span className="cursor-pointer"><Upload />Upload document<input type="file" className="sr-only" accept=".pdf,.txt,.md,.csv" aria-label="Upload document" onChange={(e) => onUpload(e.target.files?.[0])} /></span></Button></label>} />
      {upErr && <p role="alert" className="mb-3 rounded-md border border-red-500/30 bg-red-500/5 p-2 text-sm text-red-300">{upErr}</p>}

      <Card className="mb-4">
        <form onSubmit={onSearch} className="flex flex-col gap-2 p-3 md:flex-row">
          <div className="relative flex-1"><Search className="absolute left-3 top-2.5 size-4 text-slate-500" /><input className="input pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask the evidence: e.g. “Salmonella result for tomato puree” or “pasteurisation deviation”" aria-label="Search evidence" /></div>
          <Button type="submit" variant="secondary"><FileSearch />Search</Button>
        </form>
        {query && (
          <div className="border-t border-line p-3">
            {search.isLoading ? <LoadingState rows={2} /> : search.isError ? <ErrorState error={search.error} /> : (
              <>
                <p className="mb-2 text-[11px] text-slate-500">Retrieval engine: <span className="text-slate-300">{search.data!.engine}</span></p>
                {search.data!.results.length === 0 ? <EmptyState title="No matching passages" /> : (
                  <ul className="space-y-2">{search.data!.results.map((r) => (
                    <li key={r.chunk_id} className="rounded-lg border border-line bg-ink-950/50 p-2.5">
                      <div className="flex flex-wrap items-center gap-2"><button className="mono text-cyan-300 hover:underline" onClick={() => setSel(r.document_id)}>{r.citation}</button><Badge tone={VER_TONE[r.verification_status as keyof typeof VER_TONE] ?? "slate"}>{r.verification_status}</Badge><span className="mono ml-auto text-slate-500">score {r.score}</span></div>
                      <p className="mt-1 line-clamp-3 whitespace-pre-line text-xs text-slate-300">{r.content}</p>
                    </li>))}
                  </ul>
                )}
              </>
            )}
          </div>
        )}
      </Card>

      <div className="mb-3 overflow-x-auto"><Tabs value={type} onChange={setType} items={TYPES.map((t) => ({ value: t, label: t === "ALL" ? "All" : humanize(t) }))} /></div>
      <div className="grid gap-4 lg:grid-cols-5">
        <Card className="lg:col-span-2">
          <CardHeader title="Documents" icon={<FileText />} subtitle={`${list.length} shown`} />
          {docs.isLoading ? <LoadingState /> : docs.isError ? <ErrorState error={docs.error} onRetry={() => docs.refetch()} /> : list.length === 0 ? <EmptyState title="No documents" /> : (
            <ul className="max-h-[640px] divide-y divide-line overflow-auto">
              {list.map((d) => (
                <li key={d.document_id}>
                  <button onClick={() => setSel(d.document_id)} className={cn("w-full px-4 py-2.5 text-left hover:bg-ink-800/40", current?.document_id === d.document_id && "bg-cyan-500/[0.06]")}>
                    <p className="truncate text-sm text-slate-100">{d.filename}</p>
                    <p className="mono text-slate-500">{humanize(d.doc_type)} · {d.incident_id ?? "unlinked"} · {fmtDate(d.created_at)}</p>
                    <div className="mt-1 flex gap-1.5"><Badge tone={VER_TONE[d.verification_status]}>{d.verification_status}</Badge>{d.extracted.summary.positive_results > 0 && <Badge tone="red">{d.extracted.summary.positive_results} positive</Badge>}</div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="lg:col-span-3">
          <CardHeader title={current?.filename ?? "Select a document"} subtitle={current ? `${humanize(current.doc_type)} · uploaded by ${current.uploaded_by}` : undefined} icon={<FileSearch />} />
          {current ? <DocDetail d={current} /> : <EmptyState title="No document selected" />}
        </Card>
      </div>
    </div>
  );
}
