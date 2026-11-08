"use client";

import { FileSearch, ListChecks, ShieldCheck } from "lucide-react";
import { useBackend } from "@/components/layout/BackendProvider";

const STEPS = [
  { icon: FileSearch, title: "Ask", text: "Plain-language questions about orders, revenue and refunds." },
  { icon: ListChecks, title: "Explore", text: "Governed metrics, charts and tables from IBM Db2." },
  { icon: ShieldCheck, title: "Inspect", text: "SQL, definitions and 11 checks behind every result." },
];

export function EmptyState() {
  const { health } = useBackend();
  const demo = health.data?.planner?.execution_mode === "DEMO_RULE_BASED";
  const llm = health.data?.planner?.execution_mode === "LLM";
  return (
    <div className="space-y-4" data-testid="empty-state">
      <ul className="grid gap-3 md:grid-cols-3">
        {STEPS.map((s, i) => (
          <li key={s.title} className="flex items-start gap-3 rounded-2xl border border-line bg-surface p-4">
            <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-sunken text-ink-2"><s.icon aria-hidden className="size-[18px]" /></span>
            <div><p className="font-semibold"><span className="mr-1.5 text-ink-3">{i + 1}</span>{s.title}</p><p className="text-[14px] leading-snug text-ink-3">{s.text}</p></div>
          </li>
        ))}
      </ul>
      {llm && (
        <p data-testid="pre-question-llm-note" className="rounded-xl border border-accent/25 bg-accent-soft px-4 py-3 text-[15px] text-ink-2">
          <span className="font-semibold text-accent-ink">AI planner active.</span> A language model plans each question; answers can take several seconds. SQL is generated and checked by deterministic code.
        </p>
      )}
      {demo && (
        <p data-testid="pre-question-demo-note" className="rounded-xl border border-warn/30 bg-warn-soft px-4 py-3 text-[15px] text-ink-2">
          <span className="font-semibold text-warn">Demo planner active.</span> Questions are interpreted by deterministic rules, not an LLM. SQL and results still come from IBM Db2.
        </p>
      )}
    </div>
  );
}
