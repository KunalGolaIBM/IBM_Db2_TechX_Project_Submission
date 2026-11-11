"use client";

import { ArrowRight, Loader2, Square } from "lucide-react";
import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import clsx from "clsx";
import { useBackend } from "@/components/layout/BackendProvider";
import { DEMO_SCENARIOS } from "@/lib/demo-scenarios";
import { StatusBadge } from "@/components/common/StatusBadge";

export interface QuestionFormHandle { setQuestion: (q: string, focus?: boolean) => void; focus: () => void }

interface Props { loading: boolean; onSubmit: (q: string) => void; onCancel: () => void }

export const QuestionForm = forwardRef<QuestionFormHandle, Props>(function QuestionForm({ loading, onSubmit, onCancel }, ref) {
  const [value, setValue] = useState("");
  const [showAll, setShowAll] = useState(false);
  const area = useRef<HTMLTextAreaElement>(null);
  const { examples } = useBackend();

  useImperativeHandle(ref, () => ({
    setQuestion: (q, focus = true) => { setValue(q); if (focus) requestAnimationFrame(() => { area.current?.focus(); area.current?.setSelectionRange(q.length, q.length); }); },
    focus: () => area.current?.focus(),
  }));

  const tooShort = value.trim().length < 3;
  const submit = () => { if (!loading && !tooShort) onSubmit(value); };

  return (
    <section aria-labelledby="ask-title" className="rounded-2xl border border-line bg-surface p-5 shadow-[0_1px_0_rgba(20,19,15,0.03)] sm:p-6">
      <h1 id="ask-title" className="text-balance text-[28px] font-semibold leading-tight tracking-tight sm:text-[34px]">
        Don’t just trust the number. <span className="text-ink-3">Verify the evidence.</span>
      </h1>

      <form
        className="mt-5"
        onSubmit={(e) => { e.preventDefault(); submit(); }}
        aria-busy={loading}
      >
        <label htmlFor="question" className="mb-2 block text-sm font-medium text-ink-2">Ask a question about sales, refunds or orders</label>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-stretch">
          <textarea
            id="question" ref={area} rows={2} maxLength={1000} value={value} disabled={loading}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); } }}
            placeholder="e.g. What was net revenue by month in the first half of 2026?"
            aria-describedby="question-hint"
            className="min-h-[3.75rem] w-full flex-1 resize-y rounded-xl border border-line-strong bg-white px-4 py-3 text-[17px] leading-snug text-ink placeholder:text-ink-3 focus-visible:border-accent disabled:bg-sunken disabled:text-ink-2"
          />
          {loading ? (
            <button type="button" onClick={onCancel} className="inline-flex items-center justify-center gap-2 rounded-xl border border-line-strong bg-surface px-5 py-3 text-[15px] font-semibold text-ink hover:bg-sunken sm:w-40">
              <Square aria-hidden className="size-3.5 fill-current" /> Cancel
            </button>
          ) : (
            <button
              type="submit" disabled={tooShort} data-testid="submit-question"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-ink px-5 py-3 text-[15px] font-semibold text-white transition-colors hover:bg-black disabled:cursor-not-allowed disabled:bg-line-strong sm:w-40"
            >
              Analyze <ArrowRight aria-hidden className="size-4" />
            </button>
          )}
        </div>
        <p id="question-hint" className="mt-2 flex items-center gap-2 text-[13px] text-ink-3">
          {loading ? <><Loader2 aria-hidden className="size-3.5 animate-spin" /> Planning, then running on IBM Db2…</> : <>Press <kbd className="rounded border border-line-strong bg-sunken px-1.5 font-mono text-[12px]">⌘/Ctrl</kbd> + <kbd className="rounded border border-line-strong bg-sunken px-1.5 font-mono text-[12px]">Enter</kbd> to run</>}
        </p>
      </form>

      <div className="mt-5 border-t border-line pt-4">
        <p className="mb-2 text-[13px] font-medium uppercase tracking-wider text-ink-3">Guided demo</p>
        <ul className="flex flex-wrap gap-2" aria-label="Guided demo questions">
          {DEMO_SCENARIOS.map((s) => (
            <li key={s.id}>
              <button
                type="button" disabled={loading} data-testid={`demo-${s.id}`}
                onClick={() => { setValue(s.question); onSubmit(s.question); }}
                className="group inline-flex items-center gap-2 rounded-full border border-line-strong bg-white px-3.5 py-1.5 text-[14px] font-medium text-ink transition-colors hover:border-ink hover:bg-sunken disabled:opacity-50"
              >
                <span className="grid size-5 place-items-center rounded-full bg-sunken text-[11px] font-semibold text-ink-2 group-hover:bg-white">{s.step}</span>
                {s.label}
              </button>
            </li>
          ))}
        </ul>

        <button
          type="button" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll} aria-controls="all-examples"
          className="mt-3 rounded-md text-[14px] font-medium text-accent-ink underline-offset-4 hover:underline"
        >
          {showAll ? "Hide" : "Show"} all API examples{examples.data ? ` (${examples.data.examples.length})` : ""}
        </button>
        {showAll && (
          <div id="all-examples" className="mt-3">
            {examples.error && <p className="text-sm text-bad">Could not load examples: {examples.error.message}</p>}
            <ul className="grid gap-1.5 md:grid-cols-2">
              {examples.data?.examples.map((ex) => (
                <li key={ex.id}>
                  <button
                    type="button" disabled={loading}
                    onClick={() => { setValue(ex.question); onSubmit(ex.question); }}
                    className={clsx("flex w-full items-start justify-between gap-3 rounded-lg border border-line px-3 py-2 text-left text-[14px] leading-snug transition-colors hover:border-line-strong hover:bg-sunken disabled:opacity-50")}
                  >
                    <span className="min-w-0">{ex.question}</span>
                    <StatusBadge status={ex.expected_status} size="sm" className="shrink-0 opacity-90" />
                  </button>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-[12px] text-ink-3">Badges show the status the API documents as expected for each example, not a live result.</p>
          </div>
        )}
      </div>
    </section>
  );
});
