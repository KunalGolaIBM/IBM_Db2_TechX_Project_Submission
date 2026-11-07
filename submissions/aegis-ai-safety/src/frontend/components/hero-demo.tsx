"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowDown, CheckCircle2, FileText, RotateCcw, Sparkles, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

const CLAIM = "The original Transformer has 8 encoder layers.";
const EVIDENCE =
  "The encoder is composed of a stack of N = 6 identical layers.";
const PAPER = "Attention Is All You Need · page 3 · passage 129";

const steps = ["claim", "search", "evidence", "verdict"] as const;
type Step = (typeof steps)[number];

export function HeroDemo() {
  const reduce = useReducedMotion();
  const [step, setStep] = useState<Step>(reduce ? "verdict" : "claim");

  useEffect(() => {
    if (reduce) return;
    const timings: Record<Step, number> = {
      claim: 1900,
      search: 1200,
      evidence: 2400,
      verdict: 4200,
    };
    const timer = window.setTimeout(() => {
      const index = steps.indexOf(step);
      setStep(steps[(index + 1) % steps.length]);
    }, timings[step]);
    return () => window.clearTimeout(timer);
  }, [step, reduce]);

  const replay = () => setStep("claim");
  const showEvidence = step === "evidence" || step === "verdict";
  const showVerdict = step === "verdict";

  return (
    <div className="relative">
      <div className="surface relative overflow-hidden p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.18em] text-muted">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Recorded example · session #501
          </span>
          <button
            type="button"
            onClick={replay}
            className="flex items-center gap-1 rounded-full px-2 py-1 font-mono text-[9px] uppercase tracking-[0.12em] text-muted transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <RotateCcw className="h-2.5 w-2.5" aria-hidden="true" />
            Replay
          </button>
        </div>

        <div className="mt-6">
          <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted">
            Claim under review
          </p>
          <AnimatePresence mode="wait" initial={false}>
            <motion.p
              key="claim"
              initial={false}
              className="mt-2 text-[20px] font-medium leading-[1.35] tracking-[-0.02em] text-ink sm:text-[22px]"
            >
              “{CLAIM}”
            </motion.p>
          </AnimatePresence>
        </div>

        <div className="relative my-5 flex items-center justify-center">
          <motion.div
            className="h-12 w-px origin-top bg-gradient-to-b from-line via-accent/50 to-line"
            animate={step === "search" ? { scaleY: [0.2, 1], opacity: 1 } : { scaleY: 1, opacity: 0.65 }}
            transition={{ duration: reduce ? 0 : 0.5, ease: [0.22, 1, 0.36, 1] }}
          />
          <motion.span
            className="absolute flex h-6 w-6 items-center justify-center rounded-full border border-line bg-surface text-muted"
            animate={
              step === "search"
                ? { scale: [0.9, 1.08, 1], borderColor: "hsl(var(--accent))" }
                : { scale: 1 }
            }
            transition={{ duration: reduce ? 0 : 1, repeat: step === "search" ? Infinity : 0 }}
          >
            <ArrowDown className="h-3 w-3" aria-hidden="true" />
          </motion.span>
        </div>

        <AnimatePresence initial={false}>
          {showEvidence ? (
            <motion.div
              initial={reduce ? false : { opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.16em] text-muted">
                  <FileText className="h-3 w-3 text-accent" aria-hidden="true" />
                  Source evidence
                </span>
                <span className="truncate font-mono text-[9px] text-muted">{PAPER}</span>
              </div>
              <p className="mt-2 border-l-2 border-accent/40 pl-3 text-[13px] leading-[1.7] text-ink/80">
                “{EVIDENCE}”
              </p>
            </motion.div>
          ) : (
            <div className="flex h-[86px] items-center justify-center rounded-xl border border-dashed border-line">
              <span className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.14em] text-muted">
                <Sparkles className="h-3 w-3" aria-hidden="true" />
                {step === "search" ? "Searching the paper…" : "Waiting for evidence"}
              </span>
            </div>
          )}
        </AnimatePresence>

        <AnimatePresence initial={false}>
          {showVerdict ? (
            <motion.div
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: reduce ? 0 : 0.15 }}
              className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4"
            >
              <span className="inline-flex items-center gap-1.5 rounded-full border border-contradicted/25 bg-contradicted-soft px-2.5 py-1 text-[11px] font-medium text-contradicted">
                <XCircle className="h-3.5 w-3.5" aria-hidden="true" />
                Contradicted
              </span>
              <span className="font-mono text-[10px] text-muted">
                6 layers reported · 8 layers claimed
              </span>
            </motion.div>
          ) : (
            <div className="mt-5 h-[37px] border-t border-line pt-4">
              <span className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.14em] text-muted">
                <CheckCircle2 className="h-3 w-3" aria-hidden="true" />
                Evidence appears before the judgment
              </span>
            </div>
          )}
        </AnimatePresence>
      </div>

      <p className="mt-3 text-center font-mono text-[9px] uppercase tracking-[0.14em] text-muted">
        A real stored verification. Not a live run.
      </p>
    </div>
  );
}
