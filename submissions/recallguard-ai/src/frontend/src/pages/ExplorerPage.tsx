import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, Database, GitBranch, Search } from "lucide-react";
import { useCatalog, useImpact, useTrace } from "@/hooks/queries";
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import { GraphLegend, SupplyGraph } from "@/components/SupplyGraph";
import { KV, SqlTransparency } from "@/components/shared";
import { fmt, humanize } from "@/lib/utils";
import type { GraphNode } from "@/types";

const QUICK = ["TOM-2026-041", "TOM-2026-042", "PB-2026-1007", "PB-2026-1030", "CHI-2026-017", "MLK-2026-233"];

export default function ExplorerPage() {
  const [params, setParams] = useSearchParams();
  const ref = params.get("ref") ?? "TOM-2026-041";
  const [input, setInput] = useState(ref);
  const [sel, setSel] = useState<GraphNode | null>(null);
  const trace = useTrace(ref);
  const isLot = !ref.startsWith("PB-");
  const impact = useImpact(ref);
  const catalog = useCatalog();

  const go = (e?: FormEvent, value?: string) => {
    e?.preventDefault();
    const v = (value ?? input).trim().toUpperCase();
    if (v) { setParams({ ref: v }); setInput(v); setSel(null); }
  };
  const s = impact.data?.summary;

  return (
    <div>
      <PageHeader eyebrow="Supply chain explorer" title="Batch genealogy & distribution"
        subtitle="Every edge below is returned by Db2 recursive common table expressions: upstream ingredients, transformations, finished products, and the shipment network to retailers." />
      <Card className="mb-4 p-3">
        <form onSubmit={go} className="flex flex-col gap-2 md:flex-row md:items-center">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 size-4 text-slate-500" />
            <input className="input mono pl-9 uppercase" list="explorer-refs" value={input} onChange={(e) => setInput(e.target.value)} aria-label="Lot or batch ID" placeholder="Lot or batch ID…" />
            <datalist id="explorer-refs">
              {catalog.data?.lots.map((l) => <option key={l.lot_id} value={l.lot_id}>{l.ingredient_name}</option>)}
              {catalog.data?.batches.map((b) => <option key={b.batch_id} value={b.batch_id}>{b.product_name ?? b.description}</option>)}
            </datalist>
          </div>
          <Button type="submit" variant="primary"><GitBranch />Trace genealogy</Button>
        </form>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {QUICK.map((q) => <button key={q} onClick={() => go(undefined, q)} className={`mono rounded-md border px-2 py-0.5 ${q === ref ? "border-cyan-500/50 text-cyan-300" : "border-line text-slate-400 hover:text-slate-200"}`}>{q}</button>)}
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-4">
        <Card className="xl:col-span-3">
          <CardHeader title={<span>Genealogy of <span className="mono text-cyan-300">{ref}</span></span>} icon={<GitBranch />}
            subtitle={trace.data ? `${trace.data.nodes.length} nodes · ${trace.data.edges.length} relationships · ${trace.data.nodes.filter((n) => n.affected).length} affected by open incidents` : undefined} />
          <div className="p-3">
            {trace.isLoading ? <LoadingState label="Tracing in Db2" rows={8} /> : trace.isError ? <ErrorState error={trace.error} /> : trace.data!.nodes.length === 0 ? <EmptyState title="No relationships" /> : (
              <>
                <SupplyGraph nodes={trace.data!.nodes} edges={trace.data!.edges} selected={sel?.id} onSelect={setSel} height={600} />
                <div className="mt-3"><GraphLegend /></div>
              </>
            )}
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title={sel ? sel.label : "Select a node"} subtitle={sel ? humanize(sel.type) : "Click any node to inspect it"} />
            <div className="p-4">
              {sel ? (
                <>
                  <KV k="ID" v={sel.id} mono />
                  <KV k="Detail" v={sel.subtitle} />
                  <KV k="Affected" v={sel.affected ? <Badge tone="red" dot>yes — open incident</Badge> : <Badge tone="emerald">no link found</Badge>} />
                  {(sel.type === "lot" || sel.type === "intermediate" || sel.type === "finished") && sel.id !== ref && (
                    <Button size="sm" variant="outline" className="mt-3 w-full" onClick={() => go(undefined, sel.id)}>Trace this {sel.type === "lot" ? "lot" : "batch"}</Button>
                  )}
                  {!sel.affected && <p className="mt-3 text-[11px] text-slate-500">"No link found" means Db2 has no genealogy/shipment path from an open incident's source to this node. It is not a safety certification.</p>}
                </>
              ) : <p className="text-xs text-slate-500">Red borders mark nodes reachable from the source of an open contamination incident.</p>}
            </div>
          </Card>

          {isLot && s && (
            <Card>
              <CardHeader title="Impact analysis" subtitle="Db2 recursive trace" icon={<AlertTriangle />} />
              <div className="p-4">
                <KV k="Batches (direct / indirect)" v={`${s.batches_total} (${s.batches_direct} / ${s.batches_indirect})`} />
                <KV k="Finished products" v={s.products} />
                <KV k="Units produced" v={fmt(s.units_produced)} />
                <KV k="Units at retail" v={fmt(s.units_at_retail)} />
                <KV k="Warehouses / distributors" v={`${s.warehouses} / ${s.distributors}`} />
                <KV k="Retailers / cities" v={`${s.retailers} / ${s.cities}`} />
                <KV k="Traceability gaps" v={<Badge tone={s.data_gaps ? "amber" : "emerald"}>{s.data_gaps}</Badge>} />
              </div>
            </Card>
          )}

          {trace.data && (
            <Card>
              <CardHeader title="Db2 queries executed" icon={<Database />} />
              <div className="p-3"><SqlTransparency queries={[...trace.data.queries, ...(impact.data?.queries ?? [])]} engine={trace.data.engine} /></div>
            </Card>
          )}
        </div>
      </div>

      {isLot && impact.data && impact.data.data_gaps.length > 0 && (
        <Card className="mt-4">
          <CardHeader title="Missing records & uncertainty" subtitle="Handled conservatively — never treated as safe" icon={<AlertTriangle />} />
          <ul className="divide-y divide-line">
            {impact.data.data_gaps.map((g, i) => (
              <li key={i} className="flex gap-3 px-4 py-2.5">
                <Badge tone={g.severity === "HIGH" ? "red" : "amber"}>{g.severity}</Badge>
                <div><p className="mono text-amber-200">{g.code}</p><p className="text-xs text-slate-300">{g.message}</p></div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
