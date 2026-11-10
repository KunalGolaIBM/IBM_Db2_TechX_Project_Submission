import { useState } from "react";
import { api, ApiError, fmt, SAMPLES, type Compare as CompareT, type Session } from "../api";
import { ErrorState, Tag } from "./ui";

export default function Compare({ session, demo }: { session: Session | null; demo: boolean }) {
  const [query, setQuery] = useState(SAMPLES[1].text);
  const [res, setRes] = useState<CompareT | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const run = async () => {
    setBusy(true);
    setErr(null);
    try { setRes(await api.compare(query.trim(), 10)); } catch (e) { setErr(e as ApiError); } finally { setBusy(false); }
  };
  const ready = !!session && demo;

  // What Db2 returned to the senior identity and not to the junior one (each from its own connection).
  const ids = (u: string) => (res?.identities.find((i) => i.user === u)?.rankings?.hybrid ?? []).map((r) => r.id);
  const senior = res?.identities.find((i) => i.user === "NDL_SENIOR");
  const juniorIds = new Set(ids("NDL_JUNIOR"));
  const onlySenior = res && !senior?.fatal ? ids("NDL_SENIOR").filter((id) => !juniorIds.has(id)) : [];

  return (
    <section aria-labelledby="compare-title" className="border-t border-hair pt-10" data-testid="compare">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 id="compare-title" className="text-xl font-semibold tracking-[-0.01em]">Same query, three Db2 identities</h2>
          <p className="mt-1 max-w-[72ch] text-sm text-mute">
            Each column is its own Db2 connection. Nothing is filtered in the app: what a column lacks, Db2 did not return to that identity.
          </p>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <input className="field max-w-[760px] flex-1 font-mono text-[13px]" value={query} onChange={(e) => setQuery(e.target.value)}
          aria-label="Query to compare" maxLength={4000} />
        <button className="btn btn-primary" onClick={run} disabled={!ready || busy || query.trim().length < 3} data-testid="compare-btn">
          {busy ? "Running three times…" : "Compare identities"}
        </button>
      </div>
      {!ready && (
        <p className="mt-3 text-sm text-mute">
          {demo ? "Pick a demo identity in the top bar first." : "Comparing signs in as three demo identities, so it needs the demo identity switcher (NEEDLE_DEMO_SWITCHER=1). With your own sign-in, run the same query on the Triage page as each user."}
        </p>
      )}
      {err && <div className="mt-4"><ErrorState kind={err.kind} message={err.message} onRetry={run} /></div>}
      {busy && (
        <div className="mt-5 grid gap-4 lg:grid-cols-3" aria-busy="true">
          {["NDL_SENIOR", "NDL_JUNIOR", "NDL_P10"].map((u, c) => (
            <div key={u} className="panel overflow-hidden">
              <div className="flex items-center justify-between border-b border-hair px-4 py-3">
                <span className="rounded-[3px] bg-ink px-1.5 py-[1px] font-mono text-[12px] font-semibold text-paper">{u}</span>
                <div className="skeleton h-3 w-20" style={{ ["--d" as string]: `${c * 0.15}s` }} />
              </div>
              <div className="grid grid-cols-3 gap-3 border-b border-hair px-4 py-3">
                {[0, 1, 2].map((i) => <div key={i} className="skeleton h-8" style={{ ["--d" as string]: `${c * 0.15 + i * 0.05}s` }} />)}
              </div>
              <div className="grid gap-2.5 px-4 py-3">
                {Array.from({ length: 8 }).map((_, r) => <div key={r} className="skeleton h-3" style={{ width: `${70 - (r % 3) * 9}%`, ["--d" as string]: `${c * 0.15 + r * 0.07}s` }} />)}
              </div>
            </div>
          ))}
        </div>
      )}
      {!busy && res && (
        <p className="fade-in mt-5 text-sm" data-testid="compare-diff">
          {onlySenior.length ? (
            <>Returned to <b className="font-mono">NDL_SENIOR</b> and not to <b className="font-mono">NDL_JUNIOR</b>:{" "}
              {onlySenior.map((id, n) => (
                <span key={id}><b className="font-mono">{id}</b>{senior?.docs?.[id]?.embargoed ? <span className="text-affected"> (embargoed)</span> : null}{n < onlySenior.length - 1 ? ", " : ""}</span>
              ))}. Db2's row permission removed {onlySenior.length === 1 ? "it" : "them"} before the result left the database.</>
          ) : <>NDL_SENIOR and NDL_JUNIOR got the same hybrid top {res.k} for this query.</>}
        </p>
      )}
      {!busy && res && (
        <div className="fade-in mt-4 grid gap-4 lg:grid-cols-3">
          {res.identities.map((i) => (
            <div key={i.user} className="panel min-w-0 overflow-hidden">
              <div className="border-b border-hair px-4 py-3">
                <p className="flex items-center justify-between gap-3">
                  <span className="rounded-[3px] bg-ink px-1.5 py-[1px] font-mono text-[12px] font-semibold text-paper">{i.user}</span>
                  <span className="font-mono text-xs text-mute num">{fmt.int(i.visible_docs ?? null)} visible</span>
                </p>
                <p className="mt-1.5 text-xs text-mute">{i.role}</p>
              </div>
              {i.fatal ? (
                <div className="p-4"><ErrorState kind={i.fatal.kind} message={i.fatal.message} /></div>
              ) : (
                <>
                  <dl className="grid grid-cols-3 border-b border-hair text-center">
                    <Cell label="hybrid rows" value={`${i.rankings?.hybrid.length ?? 0} of ${res.k}`} />
                    <Cell label="router" value={i.router?.how === "exact scan" ? "exact" : `approx ${i.router?.depth}`} />
                    <Cell label="embargoed" value={String(i.embargoed_ids?.length ?? 0)} red={!!i.embargoed_ids?.length} />
                  </dl>
                  <p className="border-b border-hair px-4 py-2 text-xs text-ink-2">{i.router?.line}</p>
                  <ol className="py-1">
                    {(i.rankings?.hybrid ?? []).map((r) => {
                      const d = i.docs?.[r.id];
                      const hiddenFromJunior = i.user === "NDL_SENIOR" && onlySenior.includes(r.id);
                      return (
                        <li key={r.id} className="grid grid-cols-[1.5rem_minmax(0,1fr)_auto] items-center gap-2 px-4 py-1.5">
                          <span className="font-mono text-xs text-mute num">{r.rank}</span>
                          <span className="min-w-0 truncate font-mono text-[13px] font-semibold">{r.id}</span>
                          <span className="flex gap-1">
                            {d?.embargoed && <Tag tone="red">EMBARGOED</Tag>}
                            {hiddenFromJunior && <Tag tone="accent" title="Not returned to NDL_JUNIOR">not for junior</Tag>}
                          </span>
                        </li>
                      );
                    })}
                  </ol>
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function Cell({ label, value, red }: { label: string; value: string; red?: boolean }) {
  return (
    <div className="border-r border-hair px-2 py-2.5 last:border-r-0">
      <dd className={`font-mono text-sm font-semibold num ${red ? "text-affected" : ""}`}>{value}</dd>
      <dt className="text-[11px] text-mute">{label}</dt>
    </div>
  );
}
