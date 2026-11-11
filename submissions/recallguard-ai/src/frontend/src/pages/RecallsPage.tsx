import { Link } from "react-router-dom";
import { ClipboardCheck } from "lucide-react";
import { useRecalls } from "@/hooks/queries";
import { Card, CardHeader, EmptyState, ErrorState, LoadingState, PageHeader } from "@/components/ui";
import { RiskBadge, StatusBadge } from "@/components/shared";
import { fmt, fmtDate } from "@/lib/utils";

export default function RecallsPage() {
  const q = useRecalls();
  return (
    <div>
      <PageHeader eyebrow="Recall planning" title="Recall plans" subtitle="Evidence-backed, batch-level recall recommendations awaiting or following human decision." />
      <Card>
        <CardHeader title="All recall plans" icon={<ClipboardCheck />} />
        {q.isLoading ? <LoadingState /> : q.isError ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : q.data!.length === 0 ? (
          <EmptyState title="No recall plans yet" hint="Run an investigation and generate a recall plan from its results." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px]">
              <thead><tr>{["Recall", "Source", "Class", "Risk", "Items", "Units", "Status", "Created"].map((h) => <th key={h} className="table-head">{h}</th>)}</tr></thead>
              <tbody>
                {q.data!.map((r) => (
                  <tr key={r.recall_id} className="border-t border-line hover:bg-ink-800/40">
                    <td className="table-cell"><Link to={`/recalls/${r.recall_id}`} className="font-medium text-slate-100 hover:text-cyan-300">{r.title}</Link><p className="mono text-slate-500">{r.recall_id}</p></td>
                    <td className="table-cell mono">{r.source_ref}</td>
                    <td className="table-cell text-xs">{r.recall_class.replace("_", " ")}</td>
                    <td className="table-cell"><RiskBadge value={r.risk_class} score={r.risk_score} /></td>
                    <td className="table-cell tabular-nums">{r.item_count}</td>
                    <td className="table-cell tabular-nums">{fmt(r.units)}</td>
                    <td className="table-cell"><StatusBadge status={r.recall_status} /></td>
                    <td className="table-cell text-xs text-slate-400">{fmtDate(r.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
