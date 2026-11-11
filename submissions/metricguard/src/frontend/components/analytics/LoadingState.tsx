import { Skeleton } from "@/components/common/Skeleton";
import { ANALYZE_TIMEOUT_MS } from "@/lib/api/client";

/** `llm`: the AI planner (a remote model call) is usually the slow step; Db2 execution and checks take well under 1 s. */
export function LoadingState({ question, elapsedMs, llm = false }: { question: string; elapsedMs: number; llm?: boolean }) {
  const slow = elapsedMs > 4000;
  const verySlow = elapsedMs > 30_000;
  const secs = Math.round(elapsedMs / 1000);
  return (
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,34rem)]" data-testid="loading-state" role="status" aria-live="polite">
      <div className="space-y-4">
        <div className="rounded-2xl border border-line bg-surface p-5 sm:p-6">
          <p className="text-[15px] text-ink-2">Analyzing <span className="font-medium text-ink">“{question}”</span></p>
          {slow && (
            <p className="mt-1 text-[14px] text-ink-3" data-testid="slow-hint">
              Still working · {secs} s. {verySlow
                ? `Longer than usual. It stops by itself after ${ANALYZE_TIMEOUT_MS / 1000} s, or cancel and retry.`
                : llm ? "The AI planner is usually the slow step." : "Planning, executing on Db2 and verifying."}
            </p>
          )}
          <Skeleton className="mt-5 h-14 w-56" /><Skeleton className="mt-4 h-4 w-full max-w-md" /><Skeleton className="mt-2 h-4 w-3/4 max-w-sm" />
        </div>
        <div className="rounded-2xl border border-line bg-surface p-6"><Skeleton className="h-60 w-full" /></div>
      </div>
      <div className="rounded-2xl bg-ev p-5"><Skeleton className="h-6 w-40 !bg-white/10" /><Skeleton className="mt-4 h-24 w-full !bg-white/10" /><Skeleton className="mt-4 h-40 w-full !bg-white/10" /></div>
    </div>
  );
}
