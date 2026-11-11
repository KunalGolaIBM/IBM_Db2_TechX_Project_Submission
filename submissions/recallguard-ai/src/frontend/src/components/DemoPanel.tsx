import { CheckCircle2, Circle, Loader2, X, XCircle, FlaskConical, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useDemo, type StepState } from "@/hooks/useDemo";
import { Badge, Button } from "@/components/ui";
import { cn } from "@/lib/utils";

const ICON: Record<StepState, JSX.Element> = {
  pending: <Circle className="size-4 text-slate-600" />,
  running: <Loader2 className="size-4 animate-spin text-cyan-400" />,
  done: <CheckCircle2 className="size-4 text-emerald-400" />,
  error: <XCircle className="size-4 text-red-400" />,
};

export function DemoPanel() {
  const { open, setOpen, steps, investigation, incidentId, recallId, running, error } = useDemo();
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink-950/70 p-3 backdrop-blur-sm md:items-center" role="dialog" aria-modal="true" aria-label="Tomato contamination demo">
      <div className="glass w-full max-w-2xl overflow-hidden shadow-glow">
        <div className="flex items-center justify-between border-b border-line px-5 py-3">
          <div className="flex items-center gap-2">
            <FlaskConical className="size-4 text-red-400" />
            <h2 className="text-sm font-semibold text-white">Tomato Contamination Demo — TOM-2026-041</h2>
            {running && <Badge tone="cyan" dot>live</Badge>}
          </div>
          <button aria-label="Close demo panel" onClick={() => setOpen(false)} className="rounded p-1 text-slate-400 hover:bg-ink-800 hover:text-white"><X className="size-4" /></button>
        </div>
        <ol className="space-y-1 p-4">
          {steps.map((s, i) => (
            <li key={s.key} className={cn("flex gap-3 rounded-lg px-3 py-2.5", s.state === "running" && "bg-cyan-500/5", s.state === "error" && "bg-red-500/5")}>
              <div className="mt-0.5">{ICON[s.state]}</div>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-slate-100"><span className="mr-2 text-slate-500">{i + 1}.</span>{s.label}</p>
                {s.detail && <p className="mono mt-0.5 break-words text-slate-400">{s.detail}</p>}
                {s.key === "investigate" && investigation && (
                  <div className="mt-2 grid grid-cols-5 gap-1.5">
                    {investigation.agents.map((a) => (
                      <div key={a.agent_name} title={`${a.title}: ${a.run_status}`}
                        className={cn("rounded-md border px-1.5 py-1 text-center text-[10px] leading-tight",
                          a.run_status === "COMPLETED" ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300" :
                          a.run_status === "RUNNING" ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-200" :
                          a.run_status === "FAILED" ? "border-red-500/30 bg-red-500/10 text-red-300" : "border-line text-slate-500")}>
                        {a.title.replace(" Agent", "")}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>
        {error && <p className="mx-5 mb-3 rounded-md border border-red-500/30 bg-red-500/5 p-2 text-xs text-red-300">{error}</p>}
        <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line px-5 py-3">
          {incidentId && <Button asChild size="sm" variant="ghost"><Link to={`/investigations/${incidentId}`} onClick={() => setOpen(false)}>Agent details</Link></Button>}
          {incidentId && <Button asChild size="sm" variant="ghost"><Link to={`/explorer?ref=TOM-2026-041`} onClick={() => setOpen(false)}>Supply-chain graph</Link></Button>}
          {recallId && <Button asChild size="sm" variant="primary"><Link to={`/recalls/${recallId}`} onClick={() => setOpen(false)}>Review & approve recall <ArrowRight /></Link></Button>}
        </div>
      </div>
    </div>
  );
}
