import { useState } from "react";
import { api, ApiError, type Memo, type Mode, type TriageResult } from "../api";
import { ErrorState } from "./ui";
import { useElapsed } from "../views/Triage";

export default function MemoCard({ result, mode, memo, setMemo }: {
  result: TriageResult; mode: Mode; memo: Memo | null; setMemo: (m: Memo | null) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<ApiError | null>(null);
  const go = async () => {
    setBusy(true);
    setErr(null);
    try { setMemo(await api.memo(mode)); } catch (e) { setErr(e as ApiError); } finally { setBusy(false); }
  };
  return (
    <section aria-label="Triage memo" className="panel p-4 sm:p-5" data-testid="memo">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold tracking-[-0.01em]">Triage memo</h2>
          <p className="mt-0.5 max-w-[80ch] text-sm text-mute">
            A local model (Ollama, through LangChain) drafts it from {result.user}'s top {mode} advisories and exposure rows.
            The verifier then deletes any sentence whose IDs, services, status claims or day counts the SQL did not return.
          </p>
        </div>
        <button className="btn btn-primary" onClick={go} disabled={busy} data-testid="memo-btn">
          {busy ? "Writing locally…" : memo ? "Write it again" : "Write the memo"}
        </button>
      </div>

      {busy && <MemoLoading />}
      {!busy && err && <div className="mt-4"><ErrorState kind={err.kind} message={err.message} onRetry={go} /></div>}

      {!busy && memo && (
        <div className="fade-in mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div className="min-w-0">
            <p className="mb-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-xs text-mute num">
              <span className="font-semibold text-accent-strong">CHECKED AGAINST SQL</span>
              <span>{memo.model}</span><span>{memo.elapsed_s.toFixed(1)} s</span>
              <span>{memo.kept} kept</span><span className={memo.removed.length ? "text-affected" : ""}>{memo.removed.length} removed</span>
            </p>
            <div className="rounded-[6px] border border-hair bg-ground p-4 text-[15px] leading-6" data-testid="memo-text">
              {memo.text ? <MemoText text={memo.text} /> : <p className="text-mute">The verifier removed every sentence.</p>}
            </div>
          </div>
          <div className="grid min-w-0 content-start gap-3">
            <div>
              <p className="mb-2 font-mono text-xs font-semibold text-affected">REMOVED BY THE VERIFIER · {memo.removed.length}</p>
              {memo.removed.length === 0 ? (
                <p className="text-sm text-mute">Nothing removed: every ID, service, status and day count matched the SQL rows.</p>
              ) : (
                <ul className="grid gap-2.5">
                  {memo.removed.map((r, i) => (
                    <li key={i} className="border-l-2 border-affected/60 pl-3 text-sm">
                      <span className="text-mute line-through decoration-affected/70">{r.text}</span>
                      <span className="mt-0.5 block font-mono text-xs text-ink-2">{r.reasons.join("; ")}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <details className="group rounded-[6px] border border-hair">
              <summary className="cursor-pointer list-none px-3 py-2 text-sm text-ink-2 hover:bg-ground">
                <span className="mr-2 rounded-[3px] bg-amber-wash px-1.5 py-[1px] font-mono text-[11px] font-semibold text-amber">UNVERIFIED</span>
                Raw model output
              </summary>
              <pre data-lenis-prevent className="max-h-72 overflow-auto border-t border-hair px-3 py-2 font-mono text-xs whitespace-pre-wrap text-mute">{memo.raw_unverified}</pre>
            </details>
          </div>
        </div>
      )}
    </section>
  );
}

function MemoText({ text }: { text: string }) {
  const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
  const bullets = lines.filter((l) => /^[-*•]\s+/.test(l));
  if (bullets.length === lines.length) {
    return <ul className="grid list-disc gap-1.5 pl-5">{lines.map((l, i) => <li key={i}>{l.replace(/^[-*•]\s+/, "")}</li>)}</ul>;
  }
  return <div className="grid gap-2">{lines.map((l, i) => <p key={i}>{l.replace(/^[-*•]\s+/, "• ")}</p>)}</div>;
}

function MemoLoading() {
  const t = useElapsed();
  return (
    <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]" aria-busy="true" aria-live="polite">
      <div className="grid content-start gap-2.5 rounded-[6px] border border-hair bg-ground p-4">
        <p className="mb-1 flex items-baseline justify-between text-xs text-mute">
          <span>The local model is writing; the verifier checks each sentence next.</span>
          <span className="font-mono num">{t.toFixed(1)} s</span>
        </p>
        {[94, 86, 91, 72].map((w, i) => <div key={i} className="skeleton h-3.5" style={{ width: `${w}%`, ["--d" as string]: `${i * 0.12}s` }} />)}
      </div>
      <div className="grid content-start gap-2.5">
        <div className="skeleton h-3 w-40" />
        <div className="skeleton h-3.5 w-[80%]" style={{ ["--d" as string]: ".1s" }} />
        <div className="skeleton h-9 w-full" style={{ ["--d" as string]: ".2s" }} />
      </div>
    </div>
  );
}
