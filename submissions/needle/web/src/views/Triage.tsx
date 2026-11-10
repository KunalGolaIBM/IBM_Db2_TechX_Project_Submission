import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, fmt, MODES, SAMPLES, type Memo, type Mode, type Session, type TriageResult } from "../api";
import { ErrorState, Kbd, Segmented } from "../components/ui";
import Verdict from "../components/Verdict";
import Rankings from "../components/Rankings";
import Exposure from "../components/Exposure";
import SqlPanel from "../components/SqlPanel";
import MemoCard from "../components/MemoCard";
import Steps from "../components/Steps";

export function useTriageState() {
  const [query, setQuery] = useState(SAMPLES[0].text);
  const [k, setK] = useState(10);
  const [mode, setMode] = useState<Mode>("hybrid");
  const [result, setResult] = useState<TriageResult | null>(null);
  const [memo, setMemo] = useState<Memo | null>(null);
  const reset = () => { setResult(null); setMemo(null); };
  return { query, setQuery, k, setK, mode, setMode, result, setResult, memo, setMemo, reset };
}
export type TriageState = ReturnType<typeof useTriageState>;

const MODE_LABEL: Record<Mode, string> = { keyword: "Keyword", vector: "Vector", hybrid: "Hybrid" };

export interface NextAction { label: string; run: () => void }

export default function Triage({ session, state, demo, autoRun, onAutoRunDone, onSwitch }: {
  session: Session; state: TriageState; demo: boolean; autoRun: boolean; onAutoRunDone: () => void;
  onSwitch: (user: string) => void;
}) {
  const { query, setQuery, k, setK, mode, setMode, result, setResult, memo, setMemo } = state;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const box = useRef<HTMLTextAreaElement>(null);

  const run = async (text: string = query) => {
    if (text.trim().length < 3 || busy) { box.current?.focus(); return; }
    setBusy(true);
    setErr(null);
    setMemo(null);
    try {
      setResult(await api.triage(text.trim(), k));
    } catch (e) {
      setResult(null);
      setErr(e as ApiError);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (autoRun) { onAutoRunDone(); run(); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const modeIds = useMemo(() => new Set((result?.rankings?.[mode] ?? []).map((r) => r.id)), [result, mode]);
  const ok = result && !result.fatal;
  const empty = ok && MODES.every((m) => (result.rankings[m] ?? []).length === 0);

  return (
    <div className="grid gap-6">
      {!result && !busy && !err && (
        <Steps current={2} done1={<>Signed in as <span className="font-mono font-semibold text-ink-2">{session.user}</span>, {fmt.int(session.visible_docs)} advisories visible.</>} />
      )}
      <section aria-label="Query" className="panel p-4 sm:p-5">
        <label htmlFor="q" className="flex items-baseline justify-between gap-4">
          <span className="text-sm font-semibold">Advisory or chat message</span>
          <span className="hidden text-xs text-mute sm:inline">Runs as <span className="font-mono font-semibold text-ink-2">{session.user}</span> · <Kbd>Ctrl</Kbd>/<Kbd>⌘</Kbd> <Kbd>Enter</Kbd></span>
        </label>
        <textarea id="q" ref={box} value={query} onChange={(e) => setQuery(e.target.value)} rows={3} maxLength={4000}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) run(); }}
          className="field mt-2 min-h-[5.5rem] resize-y text-[15px] leading-6" spellCheck={false} />
        <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-mute">Try</span>
            {SAMPLES.map((s) => (
              <button key={s.label} onClick={() => setQuery(s.text)}
                className={`rounded-[6px] border px-2.5 py-1 text-[13px] transition-colors duration-150 ${query === s.text ? "border-ink bg-ink text-paper" : "border-rule text-ink-2 hover:border-ink"}`}>
                {s.label}
              </button>
            ))}
          </div>
          <div className="ml-auto flex items-center gap-3">
            <span className="text-xs whitespace-nowrap text-mute" id="k-label">Top k</span>
            <Segmented label="Top k" value={String(k)} onChange={(v) => setK(Number(v))}
              options={[5, 10, 20].map((n) => ({ value: String(n), label: <span className="font-mono num">{n}</span> }))} />
            <button className="btn btn-primary min-w-[9.5rem]" onClick={() => run()} disabled={busy} data-testid="run-triage">
              {busy ? "Running…" : "Run triage"}
            </button>
          </div>
        </div>
      </section>

      {busy && <Loading user={session.user} />}
      {!busy && err && <ErrorState kind={err.kind} message={err.message} onRetry={() => run()} />}
      {!busy && result?.fatal && <ErrorState kind={result.fatal.kind} message={result.fatal.message} onRetry={() => run()} />}

      {!busy && ok && (
        <div className="fade-in grid gap-6">
          <RouterLine result={result} />
          {empty ? (
            <div className="panel p-6">
              <p className="font-semibold">No advisory visible to {result.user} matched this text.</p>
              <p className="mt-1 text-sm text-mute">
                Row access control lets this identity read {fmt.int(result.visible_docs)} advisories. Try naming the package or the
                kind of flaw, or sign in as an identity with wider access.
              </p>
            </div>
          ) : (
            <>
              <Verdict result={result} modeIds={modeIds} mode={mode} />
              <TryNext result={result} demo={demo} onSwitch={onSwitch}
                onSample={() => { setQuery(SAMPLES[1].text); run(SAMPLES[1].text); }} />
              <section aria-label="Ranked advisories">
                <div className="mb-3 flex flex-wrap items-end justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-semibold tracking-[-0.01em]">One statement, three orderings</h2>
                    <p className="mt-0.5 text-sm text-mute">
                      The same candidate set from <code className="font-mono text-[13px] text-ink-2">{result.sql.path}</code>, ranked by each leg.
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-mute">Ranking for services and memo</span>
                    <Segmented label="Ranking used for exposure and memo" value={mode} onChange={(m) => { setMode(m); setMemo(null); }}
                      options={MODES.map((m) => ({ value: m, label: MODE_LABEL[m] }))} />
                  </div>
                </div>
                <Rankings result={result} mode={mode} />
              </section>
              <SqlPanel result={result} />
              <Exposure result={result} modeIds={modeIds} />
              <MemoCard result={result} mode={mode} memo={memo} setMemo={setMemo} />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function RouterLine({ result }: { result: TriageResult }) {
  const t = result.timings_ms;
  const exact = result.router.how === "exact scan";
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-y border-hair py-3" data-testid="router-line">
      <p className="flex min-w-0 items-center gap-2.5 text-sm">
        <span className={`rounded-[3px] px-1.5 py-[1px] font-mono text-[11px] font-semibold ${exact ? "bg-ink text-paper" : "bg-accent-wash text-accent-strong"}`}>
          {exact ? "EXACT" : "APPROX"}
        </span>
        <span className="font-medium text-ink" data-testid="router-text">{result.router.line}</span>
      </p>
      <p className="ml-auto flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-mute num">
        <span>embed {fmt.ms(t.embed)}</span>
        <span>triage SQL {fmt.ms(t.triage_sql)}</span>
        <span>docs {fmt.ms(t.docs_sql)}</span>
        <span>exposure {fmt.ms(t.exposure_sql)}</span>
        <span className="text-ink-2">{result.user} · {result.ts}</span>
      </p>
    </div>
  );
}

export function useElapsed(on = true) {
  const [t, setT] = useState(0);
  useEffect(() => {
    if (!on) return;
    const t0 = performance.now();
    const id = window.setInterval(() => setT((performance.now() - t0) / 1000), 100);
    return () => window.clearInterval(id);
  }, [on]);
  return t;
}

function Loading({ user }: { user: string }) {
  const t = useElapsed();
  return (
    <div className="grid gap-6" aria-busy="true" aria-live="polite">
      <div className="grid gap-3">
        <div className="flex flex-wrap items-baseline justify-between gap-3 text-sm">
          <p className="text-ink-2">Running <span className="font-mono font-semibold text-ink">NEEDLE.TRIAGE_MODE</span> as{" "}
            <span className="font-mono font-semibold text-ink">{user}</span></p>
          <span className="font-mono text-xs text-mute num">{t.toFixed(1)} s</span>
        </div>
        <div className="progress-line" />
        <ol className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-mute">
          <li><span className="font-mono text-ink-2">nomic-embed-text</span> turns the question into 768 numbers</li>
          <li>Db2 ranks by keyword and by meaning under row access control</li>
          <li>the SBOM join finds the services</li>
        </ol>
      </div>
      <div className="grid gap-5 overflow-hidden rounded-[6px] bg-slab p-6 lg:grid-cols-[minmax(0,1fr)_auto]">
        <div className="grid content-start gap-3">
          <div className="skeleton-dark h-9 w-[46%]" />
          <div className="skeleton-dark h-3.5 w-[72%]" style={{ ["--d" as string]: ".12s" }} />
          <div className="skeleton-dark h-3.5 w-[58%]" style={{ ["--d" as string]: ".2s" }} />
        </div>
        <div className="grid grid-cols-4 gap-6">
          {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton-dark h-14 w-24" style={{ ["--d" as string]: `${0.1 + i * 0.08}s` }} />)}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {[0, 1, 2].map((c) => (
          <div key={c} className={`panel overflow-hidden ${c === 1 ? "hidden lg:block" : c === 0 ? "hidden lg:block" : ""}`}>
            <div className="border-b border-hair px-4 py-3"><div className="skeleton h-3.5 w-24" style={{ ["--d" as string]: `${c * 0.1}s` }} /></div>
            {Array.from({ length: 10 }).map((_, r) => (
              <div key={r} className="grid grid-cols-[1.75rem_minmax(0,1fr)_3.5rem] items-center gap-2 border-b border-hair px-4 py-2.5 last:border-b-0">
                <div className="skeleton h-3 w-3" style={{ ["--d" as string]: `${c * 0.1 + r * 0.06}s` }} />
                <div className="grid gap-1.5">
                  <div className="skeleton h-3 w-[62%]" style={{ ["--d" as string]: `${c * 0.1 + r * 0.06}s` }} />
                  <div className="skeleton h-2.5 w-[88%] opacity-70" style={{ ["--d" as string]: `${c * 0.1 + r * 0.06 + 0.04}s` }} />
                </div>
                <div className="skeleton h-3 w-full" style={{ ["--d" as string]: `${c * 0.1 + r * 0.06}s` }} />
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function TryNext({ result, demo, onSwitch, onSample }: {
  result: TriageResult; demo: boolean; onSwitch: (u: string) => void; onSample: () => void;
}) {
  const embargoed = Object.values(result.docs).filter((d) => d.embargoed).map((d) => d.id);
  let text: ReactNode, action: NextAction | null = null;
  if (!demo) {
    text = <>Sign in as another Db2 user to see how row access control changes this answer, or read why the search depth changes per user.</>;
    action = { label: "Read the finding", run: () => { window.location.hash = "/finding"; } };
  } else if (result.user === "NDL_SENIOR" && embargoed.length) {
    text = <><b className="font-mono">{embargoed[0]}</b> is under embargo, and this senior analyst may see it. Ask the same question as the junior analyst: Db2 removes it before the result leaves the database.</>;
    action = { label: "Run as NDL_JUNIOR", run: () => onSwitch("NDL_JUNIOR") };
  } else if (result.user === "NDL_SENIOR") {
    text = <>This answer has no embargoed advisory. The Pillow FlashPix sample does: run it, then compare with the junior analyst.</>;
    action = { label: "Run the FlashPix sample", run: onSample };
  } else if (result.user === "NDL_JUNIOR") {
    text = <>Now ask as NDL_P10, who may see a tenth of the advisories. Under Db2's shared plan that analyst gets back far fewer rows than asked for; NEEDLE's router switches to an exact scan and still returns {result.k}.</>;
    action = { label: "Run as NDL_P10", run: () => onSwitch("NDL_P10") };
  } else {
    text = <>That is the router at work: a full top {result.k} for an analyst who sees a tenth of the rows. The finding shows what happens without it.</>;
    action = { label: "Read the finding", run: () => { window.location.hash = "/finding"; } };
  }
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-[6px] border border-accent/40 bg-accent-wash px-4 py-3" data-testid="try-next">
      <p className="min-w-0 flex-1 text-sm text-ink-2"><span className="mr-2 font-semibold text-accent-strong">Try next</span>{text}</p>
      {action && <button className="btn btn-accent min-h-9" onClick={action.run}>{action.label}</button>}
    </div>
  );
}
