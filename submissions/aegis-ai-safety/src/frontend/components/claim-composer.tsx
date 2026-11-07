"use client";

import { ArrowRight, Loader2, Sparkles, X } from "lucide-react";

import { cn } from "@/lib/utils";

interface ClaimComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onClear: () => void;
  onExample: () => void;
  submitting: boolean;
  canSubmit: boolean;
  live: boolean;
  error: string | null;
  maxChars: number;
}

export function ClaimComposer({
  value,
  onChange,
  onSubmit,
  onClear,
  onExample,
  submitting,
  canSubmit,
  live,
  error,
  maxChars,
}: ClaimComposerProps) {
  return (
    <div>
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Step 2</p>
          <h3 className="mt-1.5 text-[17px] font-semibold tracking-[-0.01em]">What should we verify?</h3>
        </div>
        <button
          type="button"
          onClick={onExample}
          className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-[11.5px] text-ink transition-colors hover:border-accent/30 hover:text-accent"
        >
          <Sparkles className="h-3 w-3 text-accent" aria-hidden="true" />
          Try an example
        </button>
      </div>

      <div className="relative">
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder="Paste an AI-generated research summary or scientific claim…"
          rows={9}
          maxLength={maxChars}
          disabled={submitting}
          aria-label="Claims to verify"
          className="min-h-[210px] w-full resize-y rounded-xl border border-line bg-surface px-4 py-3.5 text-[14px] leading-7 text-ink placeholder:text-muted/70 focus:border-accent/50 focus:outline-none focus:ring-4 focus:ring-accent/5 disabled:opacity-60"
        />
        <div className="pointer-events-none absolute bottom-3 right-3 font-mono text-[9px] text-muted">
          {value.length.toLocaleString()} / {maxChars.toLocaleString()}
        </div>
      </div>

      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 font-mono text-[9px] uppercase tracking-[0.1em] text-muted">
        <span>One claim or a full summary</span>
        <span>Untrusted text · never executed</span>
      </div>

      {error ? (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-contradicted/25 bg-contradicted-soft px-3.5 py-3 text-[12px] leading-5 text-contradicted"
        >
          {error}
        </div>
      ) : null}

      <div className="mt-4 flex items-center gap-2">
        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSubmit || submitting}
          className={cn(
            "inline-flex flex-1 items-center justify-center gap-2 rounded-full bg-ink px-5 py-3 text-[13px] font-medium text-canvas transition-all",
            canSubmit && !submitting
              ? "hover:-translate-y-0.5 hover:bg-ink/90"
              : "cursor-not-allowed opacity-40"
          )}
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              Verifying claims…
            </>
          ) : (
            <>
              Verify claims
              <ArrowRight className="h-4 w-4" aria-hidden="true" />
            </>
          )}
        </button>
        {value ? (
          <button
            type="button"
            onClick={onClear}
            disabled={submitting}
            className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3.5 py-3 text-[12px] text-muted transition-colors hover:text-ink"
            aria-label="Clear claims"
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
            Clear
          </button>
        ) : null}
      </div>

      <p className="mt-3 text-center text-[10.5px] leading-5 text-muted">
        {live
          ? "Local inference can take 2–4 minutes. Nothing is submitted twice."
          : "This public page is an interactive demonstration. Live verification runs locally with Db2 and LangChain."}
      </p>
    </div>
  );
}
