import { useEffect, useState } from "react";
import { api, evidenceUrl, fmt, type ExplainPlan, type TriageResult } from "../api";

type Tab = "call" | "plan" | "proc" | "exposure";
const TABS: { id: Tab; label: string }[] = [
  { id: "call", label: "The call" },
  { id: "plan", label: "Access plan" },
  { id: "proc", label: "TRIAGE_MODE source" },
  { id: "exposure", label: "Exposure join" },
];

export default function SqlPanel({ result }: { result: TriageResult }) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("call");
  return (
    <section aria-label="SQL and access plan" className="panel overflow-hidden">
      <button onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-center justify-between gap-4 px-4 py-3 text-left hover:bg-ground sm:px-5">
        <span>
          <span className="text-sm font-semibold">The SQL Db2 ran, and its access plan</span>
          <span className="ml-3 hidden font-mono text-xs text-mute sm:inline">{result.sql.call.split("--")[0].trim()}</span>
        </span>
        <span className="font-mono text-xs text-accent-text">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <div className="fade-in border-t border-hair">
          <div role="tablist" aria-label="SQL views" className="flex gap-1 overflow-x-auto px-3 pt-2 sm:px-4">
            {TABS.map((t) => (
              <button key={t.id} role="tab" aria-selected={tab === t.id} onClick={() => setTab(t.id)}
                className={`rounded-[4px] px-3 py-1.5 text-[13px] font-medium whitespace-nowrap transition-colors duration-150 ${tab === t.id ? "bg-ink text-paper" : "text-ink-2 hover:bg-surface"}`}>
                {t.label}
              </button>
            ))}
          </div>
          <div className="p-4 sm:p-5">
            {tab === "call" && <Call result={result} />}
            {tab === "plan" && <Plans />}
            {tab === "proc" && <pre data-lenis-prevent className="code max-h-[520px]">{result.sql.procedure}</pre>}
            {tab === "exposure" && (
              <div className="grid gap-3">
                <p className="text-sm text-mute">Parameter values are the advisory ids ranked above, as visible to {result.user}. Each id is bound twice.</p>
                <pre data-lenis-prevent className="code max-h-[420px]">{result.sql.exposure}</pre>
                <pre className="code">{JSON.stringify({ params: result.sql.exposure_params }, null, 2)}</pre>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function Call({ result }: { result: TriageResult }) {
  const p = result.sql.params as Record<string, unknown>;
  const terms = Array.isArray(p.P_QTERMS) ? (p.P_QTERMS as string[]) : [];
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
      <div className="grid content-start gap-3">
        <pre className="code">{result.sql.call}</pre>
        <p className="text-sm text-mute">
          Every value is a bound parameter. The query text never becomes SQL: it becomes a vector and a list of terms.
          Only the integer depth is written as a literal, because <code className="font-mono text-[13px] text-ink-2">FETCH APPROX FIRST ? ROWS</code> did not use the vector index on Db2 12.1.5 (see Access plan).
        </p>
      </div>
      <dl className="grid content-start gap-y-2 text-sm">
        <Param name="P_QVEC" value={String(p.P_QVEC ?? "")} />
        <Param name="P_QTERMS" value={terms.length ? terms.join(" · ") : "–"} />
        <Param name="P_K" value={fmt.int(p.P_K as number)} />
        <Param name="P_DEPTH" value={`${fmt.int(p.P_DEPTH as number)}  (router: ${String(p.depth_reason ?? result.router.reason ?? "–")})`} />
      </dl>
    </div>
  );
}

function Param({ name, value }: { name: string; value: string }) {
  return (
    <div className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3 border-b border-hair pb-2">
      <dt className="font-mono text-[13px] font-semibold text-accent-strong">{name}</dt>
      <dd className="font-mono text-[13px] break-words text-ink-2">{value}</dd>
    </div>
  );
}

function Plans() {
  const [plans, setPlans] = useState<ExplainPlan[] | null>(null);
  const [src, setSrc] = useState("");
  const [err, setErr] = useState("");
  useEffect(() => { api.explain().then((r) => { setPlans(r.plans); setSrc(r.source); }).catch((e) => setErr(String(e.message))); }, []);
  if (err) return <p className="text-sm text-affected">{err}</p>;
  if (!plans) return <div className="skeleton h-64" />;
  return (
    <div className="grid gap-3">
      <p className="text-sm text-mute">
        Captured with <code className="font-mono text-[13px] text-ink-2">db2exfmt</code> on the full corpus, from{" "}
        <a href={evidenceUrl(src)} target="_blank" rel="noreferrer">{src}</a>. Same statement, one difference: how k is written.
      </p>
      <div className="grid gap-4 xl:grid-cols-2">
        {plans.map((pl) => (
          <figure key={pl.name} className="min-w-0">
            <figcaption className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-sm font-semibold">{pl.name === "APPROX_bound" ? "k as a literal: FETCH APPROX FIRST 10" : "k as a parameter marker: FETCH APPROX FIRST ?"}</span>
              <span className="font-mono text-xs text-mute num">
                cost {pl.total_cost?.toFixed(1)} · {pl.uses_vector_index ? <span className="font-semibold text-accent-strong">uses ADV_DOC_VIX</span> : <span className="font-semibold text-affected">table scan</span>}
              </span>
            </figcaption>
            <pre className="code text-[11.5px]">
              {pl.plan.split("\n").map((l, i) => (
                <span key={i} className={/IXSCAN|VECIDX|ADV_DOC_VIX/.test(l) ? "font-semibold text-[#5fd3db]" : undefined}>{l + "\n"}</span>
              ))}
            </pre>
          </figure>
        ))}
      </div>
    </div>
  );
}
