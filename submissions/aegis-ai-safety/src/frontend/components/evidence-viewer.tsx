"use client";

import { BookOpen, FileText, Info, Quote, Sigma } from "lucide-react";

import { ClassificationBadge, CLASSIFICATION_META } from "@/components/classification";
import { cn, formatDate, formatScore } from "@/lib/utils";
import type { Claim } from "@/lib/types";

function HighlightNumbers({ text }: { text: string }) {
  const parts = text.split(/(\d+(?:\.\d+)?%?)/g);
  return (
    <>
      {parts.map((part, index) =>
        /^\d/.test(part) ? (
          <span
            key={`${part}-${index}`}
            className="rounded bg-insufficient/15 px-1 font-mono text-[0.95em] font-medium text-insufficient"
          >
            {part}
          </span>
        ) : (
          part
        )
      )}
    </>
  );
}

function relationshipClass(relationship: string | null): string {
  if (relationship === "SUPPORTS") return "bg-supported/10 text-supported";
  if (relationship === "CONTRADICTS") return "bg-contradicted/10 text-contradicted";
  return "bg-panel-2 text-muted";
}

export function EvidenceViewer({ claim }: { claim: Claim | null }) {
  if (!claim) {
    return (
      <div className="flex h-full min-h-[340px] flex-col items-center justify-center px-8 text-center">
        <BookOpen className="h-6 w-6 text-muted" aria-hidden="true" />
        <p className="mt-3 text-sm font-medium text-fg">Select a claim</p>
        <p className="mt-1.5 max-w-xs text-xs leading-5 text-muted">
          Choose a claim from the inspector to see its evidence passage, source document, page
          reference, explanation, and stated limitations.
        </p>
      </div>
    );
  }

  const classification = claim.classification;
  const meta = classification ? CLASSIFICATION_META[classification] : null;

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-border p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ClassificationBadge classification={classification} />
            <span className="font-mono text-[10px] uppercase tracking-wider text-muted">
              {claim.claim_type}
            </span>
          </div>
          <span className="font-mono text-[10px] text-muted">CLAIM #{claim.claim_id}</span>
        </div>
        <blockquote className="mt-3 text-[15px] font-medium leading-6 text-fg">
          “{claim.original_claim}”
        </blockquote>
        {claim.normalized_claim && claim.normalized_claim !== claim.original_claim ? (
          <p className="mt-2 text-[11px] leading-5 text-muted">
            Normalized: {claim.normalized_claim}
          </p>
        ) : null}
      </div>

      <div className="flex-1 space-y-5 overflow-y-auto p-5">
        <section>
          <h4 className="eyebrow">Verification explanation</h4>
          <p className="mt-2 text-[13px] leading-6 text-fg/90">
            {claim.explanation ?? "No explanation was recorded for this claim."}
          </p>
        </section>

        {claim.numerical_analysis ? (
          <section>
            <h4 className="eyebrow">Deterministic numeric check</h4>
            <p className="mt-2 rounded-md border border-border bg-panel-2/40 px-3.5 py-3 text-[11.5px] leading-5 text-fg/85">
              <HighlightNumbers text={claim.numerical_analysis} />
            </p>
          </section>
        ) : null}

        <section>
          <div className="flex items-center justify-between">
            <h4 className="eyebrow">Evidence passages</h4>
            <span className="font-mono text-[10px] text-muted">
              {claim.evidence.length} linked
            </span>
          </div>

          {claim.evidence.length === 0 ? (
            <div className="mt-2 rounded-md border border-dashed border-border px-3.5 py-4">
              <p className="text-xs leading-5 text-fg">
                No evidence passage is linked to this judgment.
              </p>
              <p className="mt-1 text-[11px] leading-5 text-muted">
                {classification === "INSUFFICIENT_EVIDENCE"
                  ? "Retrieval found nothing that establishes or contradicts the claim. Missing evidence is not a contradiction and does not make the claim false."
                  : "No valid retrieved passage was available to ground this classification."}
              </p>
            </div>
          ) : (
            <div className="mt-2 space-y-3">
              {claim.evidence.map((evidence) => (
                <article
                  key={evidence.passage_id}
                  className="rounded-md border border-border bg-panel-2/50"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3.5 py-2">
                    <span className="flex min-w-0 items-center gap-1.5 text-[11px] text-fg">
                      <FileText className="h-3 w-3 shrink-0 text-accent" aria-hidden="true" />
                      <span className="truncate">{evidence.document_title}</span>
                    </span>
                    <span className="flex items-center gap-2 font-mono text-[9px] text-muted">
                      <span
                        className={cn(
                          "rounded px-1.5 py-0.5",
                          relationshipClass(evidence.evidence_relationship)
                        )}
                      >
                        {evidence.evidence_relationship ?? "CONTEXT"}
                      </span>
                      <span>PAGE {evidence.page_number ?? "—"}</span>
                      <span>·</span>
                      <span>PASSAGE {evidence.passage_id}</span>
                      <span>·</span>
                      <span className="flex items-center gap-1">
                        <Sigma className="h-2.5 w-2.5" />
                        {formatScore(evidence.relevance_score)}
                      </span>
                    </span>
                  </div>
                  <div className="relative px-3.5 py-3">
                    <Quote
                      className="absolute right-3 top-2 h-8 w-8 text-border"
                      aria-hidden="true"
                    />
                    <p className="prose-evidence relative">{evidence.passage_text}</p>
                    <p className="mt-2 font-mono text-[9px] text-muted">
                      {evidence.filename} · passage index {evidence.passage_index}
                    </p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section>
          <h4 className="eyebrow">Limitations</h4>
          <div className="mt-2 flex items-start gap-2 rounded-md border border-insufficient/25 bg-insufficient/5 px-3.5 py-3">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-insufficient" aria-hidden="true" />
            <p className="text-[11.5px] leading-5 text-fg/85">
              {claim.limitations ||
                "No limitations were recorded. Automated judgments should still be reviewed by a researcher."}
            </p>
          </div>
          <p className="mt-2 font-mono text-[9px] text-muted">
            Human review recommendation: researcher review required before relying on this judgment.
          </p>
        </section>

        <section className="border-t border-border pt-4">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 font-mono text-[10px]">
            <div>
              <dt className="text-muted">Method</dt>
              <dd className="mt-0.5 truncate text-fg">{claim.verification_method ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted">Recorded</dt>
              <dd className="mt-0.5 text-fg">{formatDate(claim.result_created_at)}</dd>
            </div>
            <div>
              <dt className="text-muted">Span</dt>
              <dd className="mt-0.5 text-fg">
                {claim.position_start !== null && claim.position_end !== null
                  ? `${claim.position_start}–${claim.position_end}`
                  : "not preserved"}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Human review</dt>
              <dd className="mt-0.5 text-fg">{claim.human_review_status}</dd>
            </div>
            <div>
              <dt className="text-muted">Evidence UUID</dt>
              <dd className={cn("mt-0.5 truncate", meta ? meta.textClass : "text-fg")}>
                {claim.evidence.map((item) => `P${item.passage_id}`).join(", ") || "none"}
              </dd>
            </div>
          </dl>
        </section>
      </div>
    </div>
  );
}
