"use client";

import { useRef } from "react";
import { useAnalyze } from "@/hooks/useAnalyze";
import { QuestionForm, type QuestionFormHandle } from "@/components/analytics/QuestionForm";
import { AnalysisView } from "@/components/analytics/AnalysisView";
import { LoadingState } from "@/components/analytics/LoadingState";
import { EmptyState } from "@/components/analytics/EmptyState";
import { TransportError } from "@/components/analytics/TransportError";
import { useBackend } from "@/components/layout/BackendProvider";

export default function WorkspacePage() {
  const a = useAnalyze();
  const form = useRef<QuestionFormHandle>(null);
  const llm = useBackend().health.data?.planner?.execution_mode === "LLM";

  const ask = (q: string) => { form.current?.setQuestion(q, false); void a.submit(q); window.scrollTo({ top: 0, behavior: "smooth" }); };

  return (
    <div className="space-y-6">
      <QuestionForm ref={form} loading={a.phase === "loading"} onSubmit={(q) => void a.submit(q)} onCancel={a.cancel} />

      <div aria-live="polite" className="min-h-8">
        {a.phase === "idle" && <EmptyState />}
        {a.phase === "loading" && <LoadingState question={a.question} elapsedMs={a.elapsedMs} llm={llm} />}
        {a.phase === "error" && a.error && <TransportError error={a.error} onRetry={() => void a.submit(a.question)} />}
        {a.phase === "done" && a.response && <AnalysisView r={a.response} onAsk={ask} onEdit={() => form.current?.focus()} />}
      </div>
    </div>
  );
}
