"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState } from "react";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Download,
  FileJson,
  FileText,
  Info,
  Quote,
  XCircle,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { Claim, Classification, Evidence, Verification } from "@/lib/types";

const META: Record<
  Classification,
  { label: string; short: string; tone: string; soft: string; icon: typeof CheckCircle2 }
> = {
  SUPPORTED: {
    label: "Supported",
    short: "Supported",
    tone: "text-supported",
    soft: "border-supported/25 bg-supported-soft",
    icon: CheckCircle2,
  },
  CONTRADICTED: {
    label: "Contradicted",
    short: "Contradicted",
    tone: "text-contradicted",
    soft: "border-contradicted/25 bg-contradicted-soft",
    icon: XCircle,
  },
  INSUFFICIENT_EVIDENCE: {
    label: "Insufficient evidence",
    short: "Insufficient",
    tone: "text-insufficient",
    soft: "border-insufficient/25 bg-insufficient-soft",
    icon: CircleHelp,
  },
  VERIFICATION_ERROR: {
    label: "Verification error",
    short: "Error",
    tone: "text-verror",
    soft: "border-verror/25 bg-verror-soft",
    icon: AlertTriangle,
  },
};

function Verdict({ value }: { value: Classification | null }) {
  if (!value) return null;
  const meta = META[value];
  const Icon = meta.icon;
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium",
        meta.soft,
        meta.tone
      )}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {meta.label}
    </span>
  );
}

function readableExcerpt(text: string): string {
  const lines = text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  // Figure labels and table cells produce long runs of one-word lines. Start at
  // the first line with several real words; the full passage remains available.
  const firstProse = lines.findIndex((line) => {
    const words = line.split(/\s+/).filter((word) => /[A-Za-z]{3,}/.test(word));
    return words.length >= 7;
  });
  const joined = lines.slice(firstProse >= 0 ? firstProse : 0).join(" ").replace(/\s+/g, " ");
  if (joined.length <= 720) return joined;
  const cut = joined.slice(0, 720);
  const lastSpace = cut.lastIndexOf(" ");
  return `${cut.slice(0, lastSpace > 480 ? lastSpace : 720).trimEnd()}…`;
}

function EvidenceBlock({ evidence }: { evidence: Evidence }) {
  const [full, setFull] = useState(false);
  const excerpt = readableExcerpt(evidence.passage_text);
  const truncated = excerpt !== evidence.passage_text.replace(/\s+/g, " ").trim();

  return (
    <article className="min-w-0 overflow-hidden rounded-xl border border-line bg-surface">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-2.5">
        <span className="flex min-w-0 items-center gap-1.5 text-[11.5px] font-medium text-ink">
          <FileText className="h-3.5 w-3.5 shrink-0 text-accent" aria-hidden="true" />
          <span className="truncate">{evidence.document_title}</span>
        </span>
        <span className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.1em] text-muted">
          <span className="rounded bg-surface-2 px-1.5 py-0.5">
            {evidence.evidence_relationship ?? "CONTEXT"}
          </span>
          <span>Page {evidence.page_number ?? "—"}</span>
          <span>Passage {evidence.passage_id}</span>
        </span>
      </div>
      <div className="relative px-4 py-3.5">
        <Quote className="absolute right-4 top-3 h-7 w-7 text-line" aria-hidden="true" />
        <p className="prose-evidence relative">
          {full ? evidence.passage_text : excerpt}
        </p>
        {truncated ? (
          <button
            type="button"
            onClick={() => setFull((value) => !value)}
            className="mt-2 font-mono text-[9px] uppercase tracking-[0.1em] text-accent hover:underline"
          >
            {full ? "Show excerpt" : "Show full passage"}
          </button>
        ) : null}
      </div>
    </article>
  );
}

function ClaimCard({
  claim,
  index,
  open,
  onToggle,
}: {
  claim: Claim;
  index: number;
  open: boolean;
  onToggle: () => void;
}) {
  const reduce = useReducedMotion();
  const meta = claim.classification ? META[claim.classification] : null;
  const conflicting =
    claim.evidence.some((item) => item.evidence_relationship === "SUPPORTS") &&
    claim.evidence.some((item) => item.evidence_relationship === "CONTRADICTS");

  return (
    <motion.li
      initial={reduce ? false : { opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.4, delay: Math.min(index * 0.07, 0.25) }}
      className="surface overflow-hidden"
    >
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-4 py-4 text-left transition-colors hover:bg-surface-2/50 sm:px-5"
      >
        <span className="mt-1 font-mono text-[10px] text-muted">{String(index + 1).padStart(2, "0")}</span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <Verdict value={claim.classification} />
            {claim.numerical_analysis ? (
              <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-insufficient">
                numeric check
              </span>
            ) : null}
          </span>
          <span className="mt-2 block text-[14px] font-medium leading-6 text-ink">
            “{claim.original_claim}”
          </span>
          <span className="mt-1 block text-[12px] leading-5 text-muted">
            {claim.explanation ?? "No explanation was recorded."}
          </span>
        </span>
        <span className="mt-1 flex items-center gap-1.5 shrink-0 font-mono text-[9px] uppercase tracking-[0.1em] text-muted">
          {open ? "Close" : "Inspect"}
          <ChevronDown
            className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")}
            aria-hidden="true"
          />
        </span>
      </button>

      <AnimatePresence initial={false}>
        {open ? (
          <motion.div
            initial={reduce ? false : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduce ? undefined : { height: 0, opacity: 0 }}
            transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}
            className="overflow-hidden border-t border-line"
          >
            <div className="grid min-w-0 gap-0 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="min-w-0 space-y-5 p-4 sm:p-5 lg:border-r lg:border-line">
                <div>
                  <p className="eyebrow">The claim</p>
                  <p className="mt-2 text-[15px] font-medium leading-6 text-ink">
                    “{claim.original_claim}”
                  </p>
                </div>
                <div>
                  <p className="eyebrow">Why this verdict</p>
                  <p className="mt-2 text-[13px] leading-6 text-ink/80">
                    {claim.explanation ?? "No explanation was recorded."}
                  </p>
                </div>
                {claim.numerical_analysis ? (
                  <div>
                    <p className="eyebrow">Numeric consistency</p>
                    <p className="mt-2 rounded-lg border border-insufficient/20 bg-insufficient-soft px-3.5 py-3 text-[12px] leading-6 text-ink/80">
                      {claim.numerical_analysis}
                    </p>
                  </div>
                ) : null}
                <div
                  className={cn(
                    "flex items-start gap-2 rounded-lg border px-3.5 py-3",
                    meta?.soft ?? "border-line bg-surface-2"
                  )}
                >
                  <Info className={cn("mt-0.5 h-3.5 w-3.5 shrink-0", meta?.tone ?? "text-muted")} aria-hidden="true" />
                  <div>
                    <p className={cn("text-[11.5px] font-medium", meta?.tone ?? "text-muted")}>
                      {claim.classification === "INSUFFICIENT_EVIDENCE"
                        ? "Not enough evidence — not a claim that this is false."
                        : claim.classification === "CONTRADICTED"
                          ? "The source conflicts with this statement."
                          : claim.classification === "SUPPORTED"
                            ? "The source explicitly supports this statement."
                            : "The check could not be completed reliably."}
                    </p>
                    <p className="mt-1 text-[11px] leading-5 text-muted">
                      {claim.limitations || "Researcher review is still recommended."}
                    </p>
                  </div>
                </div>
                {conflicting ? (
                  <div className="flex items-start gap-2 rounded-lg border border-insufficient/25 bg-insufficient-soft px-3.5 py-3 text-[11.5px] leading-5 text-ink/80">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-insufficient" aria-hidden="true" />
                    Sources report incompatible findings. Human review is recommended.
                  </div>
                ) : null}
              </div>

              <div className="min-w-0 space-y-3 bg-surface-2/40 p-4 sm:p-5">
                <div className="flex items-center justify-between">
                  <p className="eyebrow">Actual source evidence</p>
                  <span className="font-mono text-[9px] text-muted">
                    {claim.evidence.length} passage{claim.evidence.length === 1 ? "" : "s"}
                  </span>
                </div>
                {claim.evidence.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-line bg-surface px-4 py-6 text-center">
                    <p className="text-[12.5px] font-medium text-ink">No passage establishes this claim.</p>
                    <p className="mx-auto mt-1 max-w-sm text-[11.5px] leading-5 text-muted">
                      The selected paper does not contain enough evidence. That does not make the claim
                      false; it means the source cannot verify it.
                    </p>
                  </div>
                ) : (
                  claim.evidence.map((item) => <EvidenceBlock key={item.passage_id} evidence={item} />)
                )}

                <details className="rounded-lg border border-line bg-surface px-3.5 py-3">
                  <summary className="flex cursor-pointer list-none items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.1em] text-muted">
                    Advanced details
                    <ChevronDown className="h-3 w-3" aria-hidden="true" />
                  </summary>
                  <dl className="mt-3 grid gap-2 border-t border-line pt-3 font-mono text-[9.5px] sm:grid-cols-2">
                    <div>
                      <dt className="text-muted">Method</dt>
                      <dd className="mt-0.5 break-all text-ink">{claim.verification_method ?? "—"}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Claim ID</dt>
                      <dd className="mt-0.5 text-ink">#{claim.claim_id}</dd>
                    </div>
                    <div>
                      <dt className="text-muted">Evidence IDs</dt>
                      <dd className="mt-0.5 text-ink">
                        {claim.evidence.map((item) => `P${item.passage_id}`).join(", ") || "none"}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted">Human review</dt>
                      <dd className="mt-0.5 text-ink">{claim.human_review_status}</dd>
                    </div>
                  </dl>
                </details>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.li>
  );
}

export function ResultsAudit({
  verification,
  demo,
  selectedClaimId,
  onSelectClaim,
}: {
  verification: Verification;
  demo: boolean;
  selectedClaimId: number | null;
  onSelectClaim: (id: number | null) => void;
}) {
  const counts = verification.counts;
  const total = Math.max(counts.total, 1);
  const segments = [
    { key: "supported", value: counts.supported, color: "bg-supported", label: "Supported" },
    { key: "contradicted", value: counts.contradicted, color: "bg-contradicted", label: "Contradicted" },
    {
      key: "insufficient",
      value: counts.insufficient_evidence,
      color: "bg-insufficient",
      label: "Insufficient",
    },
    { key: "error", value: counts.verification_error, color: "bg-verror", label: "Error" },
  ].filter((item) => item.value > 0);

  return (
    <section id="results" className="scroll-mt-20 border-t border-line py-20 sm:py-24">
      <div className="shell">
        <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow">Verification complete</p>
            <h2 className="display mt-3 text-[34px] text-ink sm:text-[44px]">
              {counts.total} claim{counts.total === 1 ? "" : "s"} reviewed.
            </h2>
            <p className="mt-3 max-w-xl text-[14px] leading-6 text-muted">
              “{verification.submitted_text.slice(0, 160)}
              {verification.submitted_text.length > 160 ? "…" : ""}”
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {demo ? (
              <span className="rounded-full border border-line bg-surface px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.12em] text-muted">
                Recorded Db2 session #{verification.session_id}
              </span>
            ) : (
              <span className="rounded-full border border-supported/25 bg-supported-soft px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.12em] text-supported">
                Stored in IBM Db2
              </span>
            )}
            {!demo ? (
              <a
                href={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/verifications/${verification.session_id}/export?format=markdown`}
                download
                className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1.5 text-[11px] text-ink transition-colors hover:border-accent/30 hover:text-accent"
              >
                <Download className="h-3 w-3" aria-hidden="true" />
                Report
              </a>
            ) : null}
          </div>
        </div>

        <div className="mt-9 surface p-4 sm:p-5">
          <div className="flex h-2 w-full gap-1 overflow-hidden rounded-full bg-surface-2">
            {segments.map((segment) => (
              <motion.span
                key={segment.key}
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                style={{ width: `${(segment.value / total) * 100}%`, transformOrigin: "left" }}
                className={cn("h-full rounded-full", segment.color)}
                title={`${segment.label}: ${segment.value}`}
              />
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2">
            {segments.map((segment) => (
              <span key={segment.key} className="flex items-center gap-1.5 text-[11.5px] text-muted">
                <span className={cn("h-1.5 w-1.5 rounded-full", segment.color)} />
                {segment.label}
                <span className="font-mono text-[10px] text-ink">{segment.value}</span>
              </span>
            ))}
            <span className="ml-auto font-mono text-[9px] uppercase tracking-[0.1em] text-muted">
              {verification.model_provider}
            </span>
          </div>
        </div>

        <ul className="mt-5 space-y-3">
          {verification.claims.map((claim, index) => (
            <ClaimCard
              key={claim.claim_id}
              claim={claim}
              index={index}
              open={selectedClaimId === claim.claim_id}
              onToggle={() =>
                onSelectClaim(selectedClaimId === claim.claim_id ? null : claim.claim_id)
              }
            />
          ))}
        </ul>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line bg-surface px-4 py-3">
          <p className="max-w-xl text-[11px] leading-5 text-muted">
            AEGIS assists research verification. It does not replace expert review. Insufficient
            evidence is never reported as false.
          </p>
          {!demo ? (
            <div className="flex gap-2">
              <a
                href={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/verifications/${verification.session_id}/export?format=json`}
                download
                className="inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.1em] text-muted hover:text-ink"
              >
                <FileJson className="h-3 w-3" aria-hidden="true" />
                JSON
              </a>
              <a
                href={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/verifications/${verification.session_id}/export?format=markdown`}
                download
                className="inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.1em] text-muted hover:text-ink"
              >
                <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
                Markdown
              </a>
            </div>
          ) : (
            <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-muted">
              Demo record · exports available in the local app
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
