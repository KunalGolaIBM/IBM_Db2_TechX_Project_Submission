import type { ReactNode } from "react";

/* First-run guide: the three things a new visitor does, with where they are now. Shown until the first result,
   then replaced by a "try next" suggestion (studio-web product-ui §8: teach inside the real product). */
const STEPS = [
  { title: "Choose who you are", hint: "Each Db2 identity is allowed to see different advisories." },
  { title: "Ask a question", hint: "Pick a sample or paste a security message, then press Run triage." },
  { title: "Read the answer", hint: "Which services are affected, since when, and from which advisories." },
];

export default function Steps({ current, done1 }: { current: 1 | 2 | 3; done1?: ReactNode }) {
  return (
    <ol aria-label="Getting started" className="grid gap-px overflow-hidden rounded-[6px] border border-hair bg-hair sm:grid-cols-3" data-testid="steps">
      {STEPS.map((s, i) => {
        const n = i + 1;
        const state = n < current ? "done" : n === current ? "now" : "todo";
        return (
          <li key={s.title} aria-current={state === "now" ? "step" : undefined}
            className={`flex gap-3 px-4 py-3.5 ${state === "now" ? "bg-paper" : "bg-ground"}`}>
            <span aria-hidden className={`mt-px flex size-6 shrink-0 items-center justify-center rounded-full font-mono text-xs font-semibold ${
              state === "done" ? "bg-accent-text text-paper" : state === "now" ? "bg-ink text-paper" : "border border-rule text-mute"}`}>
              {state === "done" ? "✓" : n}
            </span>
            <span className="min-w-0">
              <span className={`block text-sm font-semibold ${state === "todo" ? "text-mute" : "text-ink"}`}>
                {s.title}<span className="sr-only"> ({state === "done" ? "done" : state === "now" ? "current step" : "next"})</span>
              </span>
              <span className="mt-0.5 block text-xs text-mute">{n === 1 && state === "done" && done1 ? done1 : s.hint}</span>
            </span>
          </li>
        );
      })}
    </ol>
  );
}
