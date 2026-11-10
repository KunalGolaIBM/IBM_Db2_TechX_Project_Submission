import { useEffect, useMemo, useState } from "react";
import { fmt, MODES, type Doc, type Mode, type Ranked, type TriageResult } from "../api";
import { Tag } from "./ui";
import { lockScroll } from "../lib/scroll";
import RankFlow from "./RankFlow";

const HEAD: Record<Mode, { title: string; how: string }> = {
  keyword: { title: "Keyword", how: "BM25 in plain SQL over NEEDLE.POSTING" },
  vector: { title: "Vector", how: "DiskANN index ADV_DOC_VIX, FETCH APPROX" },
  hybrid: { title: "Hybrid", how: "Reciprocal rank fusion inside Db2" },
};

export default function Rankings({ result, mode }: { result: TriageResult; mode: Mode }) {
  const [open, setOpen] = useState<Doc | null>(null);
  const [hot, setHot] = useState<string | null>(null); // hovered id, lit in every leg
  const fleet = useMemo(() => new Set(result.exposure.map((r) => r.PACKAGE.toLowerCase())), [result]);
  return (
    <>
      <div className="mb-4"><RankFlow result={result} hot={hot} onHot={setHot} /></div>
      <div className="grid gap-4 lg:grid-cols-3">
        {MODES.map((m) => (
          <div key={m} className={`panel min-w-0 overflow-hidden ${m === mode ? "border-t-[3px] border-t-accent" : "hidden border-t-[3px] border-t-hair lg:block"}`} data-testid={`rank-${m}`}>
            <div className="border-b border-hair px-4 py-2.5">
              <h3 className="flex items-baseline justify-between gap-3 text-sm font-semibold">{HEAD[m].title}
                <span className={`font-mono text-[11px] font-medium whitespace-nowrap num ${result.rankings[m].length < result.k ? "text-affected" : "text-mute"}`}>top {result.k}: {result.rankings[m].length} rows</span>
              </h3>
              <p className="mt-0.5 truncate text-xs text-mute">{HEAD[m].how}</p>
            </div>
            {result.rankings[m].length === 0 ? (
              <p className="px-4 py-6 text-sm text-mute">No candidates in this leg for {result.user}.</p>
            ) : (
              <ol>
                {result.rankings[m].map((r) => (
                  <Row key={r.id} r={r} mode={m} doc={result.docs[r.id]} fleet={fleet} onOpen={setOpen} hot={hot === r.id} onHot={setHot} />
                ))}
              </ol>
            )}
          </div>
        ))}
      </div>
      <p className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-mute">
        <span><span className="mr-1 inline-block size-1.5 translate-y-[-1px] rounded-full bg-accent align-middle" />the advisory names a package the synthetic fleet deploys</span>
        <span><span className="font-mono">KW</span> / <span className="font-mono">VEC</span> = the same advisory's rank in the other leg (blank: outside that leg)</span>
        <span><span className="font-mono">dist</span> = cosine distance from Db2's VECTOR_DISTANCE</span>
      </p>
      {open && <Drawer doc={open} onClose={() => setOpen(null)} />}
    </>
  );
}

function Row({ r, mode, doc, fleet, onOpen, hot, onHot }: {
  r: Ranked; mode: Mode; doc?: Doc; fleet: Set<string>; onOpen: (d: Doc) => void; hot: boolean; onHot: (id: string | null) => void;
}) {
  const pkg = doc?.packages[0] ?? "";
  const inFleet = !!doc?.packages.some((p) => fleet.has(p.toLowerCase()));
  return (
    <li onMouseEnter={() => onHot(r.id)} onMouseLeave={() => onHot(null)} onFocus={() => onHot(r.id)} onBlur={() => onHot(null)}
      className={`group grid grid-cols-[1.75rem_minmax(0,1fr)_auto] items-start gap-x-2 border-b border-hair px-4 py-2 transition-colors duration-150 last:border-b-0 ${hot ? "bg-accent-wash" : ""}`}>
      <span className="pt-px font-mono text-xs text-mute num">{r.rank}</span>
      <span className="min-w-0">
        <span className="flex min-w-0 items-center gap-2">
          <a href={doc?.osv ?? `https://osv.dev/vulnerability/${r.id}`} target="_blank" rel="noreferrer noopener"
            className="truncate font-mono text-[13px] font-semibold text-ink underline decoration-rule decoration-1 underline-offset-[3px] hover:text-accent-strong hover:decoration-accent-strong">{r.id}</a>
          {doc?.embargoed && <Tag tone="red" title={`Embargoed until ${doc.embargo_until?.slice(0, 10)}`}>EMBARGOED</Tag>}
        </span>
        <button onClick={() => doc && onOpen(doc)} title="Show the advisory"
          className="mt-0.5 flex w-full min-w-0 items-center gap-1.5 text-left text-xs text-mute hover:text-ink">
          {inFleet && <span className="size-1.5 shrink-0 rounded-full bg-accent" title="Package deployed in the synthetic fleet" />}
          <span className="shrink-0 font-mono text-ink-2">{pkg}</span>
          <span className="truncate">{doc?.title}</span>
        </button>
      </span>
      <span className="flex shrink-0 items-center gap-1.5 pt-px font-mono text-[11px] text-mute num">
        {mode === "vector" && <span className="w-[4.25rem] text-right text-ink-2">dist {fmt.dec(r.vec_dist)}</span>}
        {mode !== "keyword" && <Cross label="KW" v={r.kw_rank} />}
        {mode !== "vector" && <Cross label="VEC" v={r.vec_rank} />}
      </span>
    </li>
  );
}

function Cross({ label, v }: { label: string; v: number | null }) {
  return (
    <span className={`inline-flex w-[3.4rem] justify-between rounded-[3px] px-1 ${v == null ? "text-rule" : "bg-surface text-ink-2"}`}>
      <span>{label}</span><span>{v ?? "–"}</span>
    </span>
  );
}

function Drawer({ doc, onClose }: { doc: Doc; onClose: () => void }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    lockScroll(true);
    return () => { window.removeEventListener("keydown", k); lockScroll(false); };
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label={doc.id}>
      <button className="absolute inset-0 bg-ink/25" aria-label="Close" onClick={onClose} />
      <aside data-lenis-prevent className="fade-in absolute inset-y-0 right-0 flex w-full max-w-[560px] flex-col overflow-y-auto border-l border-hair bg-paper p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="font-mono text-[15px] font-semibold break-all">{doc.id}</p>
            <p className="mt-1 text-md font-semibold">{doc.title || "No summary in the record"}</p>
          </div>
          <button className="btn btn-quiet min-h-9 px-3" onClick={onClose}>Close</button>
        </div>
        <dl className="mt-5 grid grid-cols-[7rem_minmax(0,1fr)] gap-x-4 gap-y-2 text-sm">
          <dt className="text-mute">Packages</dt><dd className="font-mono text-[13px]">{doc.packages.join(", ") || "–"}</dd>
          <dt className="text-mute">Aliases</dt><dd className="font-mono text-[13px] break-words">{doc.aliases.join(", ") || "–"}</dd>
          <dt className="text-mute">Published</dt><dd className="font-mono text-[13px]">{doc.published ?? "–"}</dd>
          {doc.embargoed && (<><dt className="text-mute">Embargo</dt><dd><Tag tone="red">EMBARGOED</Tag> <span className="font-mono text-[13px]">until {doc.embargo_until?.slice(0, 10)}</span></dd></>)}
        </dl>
        {doc.details && <p className="mt-5 text-sm whitespace-pre-line text-ink-2">{doc.details}</p>}
        <a className="mt-6 text-sm" href={doc.osv} target="_blank" rel="noreferrer noopener">Open {doc.id} on osv.dev ↗</a>
      </aside>
    </div>
  );
}
