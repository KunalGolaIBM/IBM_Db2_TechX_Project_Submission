"use client";

import { ClipboardList, FileJson, FileSearch, FileText } from "lucide-react";

import { EvidenceViewer } from "@/components/evidence-viewer";
import { ClassificationBadge } from "@/components/classification";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { API_BASE } from "@/lib/api";
import { cn, truncate } from "@/lib/utils";
import type { Verification } from "@/lib/types";

interface ClaimInspectorProps {
  verification: Verification | null;
  selectedClaimId: number | null;
  onSelectClaim: (claimId: number) => void;
}

export function ClaimInspector({
  verification,
  selectedClaimId,
  onSelectClaim,
}: ClaimInspectorProps) {
  if (!verification) {
    return (
      <Card id="results" className="scroll-mt-24">
        <div className="flex min-h-[280px] flex-col items-center justify-center px-8 py-12 text-center">
          <span className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-panel-2">
            <FileSearch className="h-5 w-5 text-muted" aria-hidden="true" />
          </span>
          <h3 className="mt-4 text-sm font-medium text-fg">No verification results yet</h3>
          <p className="mt-1.5 max-w-md text-xs leading-5 text-muted">
            Submit research text with at least one evidence source. AEGIS will extract atomic
            claims, retrieve passages from IBM Db2, and record an evidence-linked judgment for
            each one.
          </p>
        </div>
      </Card>
    );
  }

  const claims = verification.claims;
  const selectedClaim = claims.find((claim) => claim.claim_id === selectedClaimId) ?? claims[0] ?? null;

  return (
    <Card id="results" className="scroll-mt-24 overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-4">
        <div className="flex items-center gap-2.5">
          <ClipboardList className="h-4 w-4 text-accent" aria-hidden="true" />
          <div>
            <h3 className="text-sm font-semibold">Claim inspector</h3>
            <p className="mt-0.5 font-mono text-[10px] text-muted">
              {claims.length} claims · session #{verification.session_id} · {verification.status}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-[11px] text-muted">Click a claim to inspect its evidence</p>
          <Button asChild variant="outline" size="sm">
            <a
              href={`${API_BASE}/api/verifications/${verification.session_id}/export?format=json`}
              download
              title="Download JSON report"
            >
              <FileJson className="h-3.5 w-3.5" />
              JSON
            </a>
          </Button>
          <Button asChild variant="secondary" size="sm">
            <a
              href={`${API_BASE}/api/verifications/${verification.session_id}/export?format=markdown`}
              download
              title="Download Markdown report"
            >
              <FileText className="h-3.5 w-3.5" />
              Markdown
            </a>
          </Button>
        </div>
      </div>

      {claims.length === 0 ? (
        <div className="flex min-h-[240px] flex-col items-center justify-center px-8 py-10 text-center">
          <p className="text-sm font-medium text-fg">No verifiable claims were extracted</p>
          <p className="mt-1.5 max-w-md text-xs leading-5 text-muted">
            {verification.error_message ??
              "The research text did not contain atomic factual claims that AEGIS could evaluate. Try a results section or abstract with specific statements."}
          </p>
        </div>
      ) : (
        <div className="grid lg:grid-cols-[minmax(320px,420px)_1fr]">
          <div className="max-h-[360px] overflow-y-auto border-b border-border lg:max-h-[720px] lg:border-b-0 lg:border-r">
            <ul className="divide-y divide-border">
              {claims.map((claim, index) => {
                const active = claim.claim_id === selectedClaim?.claim_id;
                return (
                  <li key={claim.claim_id}>
                    <button
                      type="button"
                      onClick={() => onSelectClaim(claim.claim_id)}
                      aria-current={active ? "true" : undefined}
                      className={cn(
                        "flex w-full gap-3 border-l-2 px-4 py-3.5 text-left transition-colors",
                        active
                          ? "border-l-accent bg-panel-2"
                          : "border-l-transparent hover:bg-panel-2/60"
                      )}
                    >
                      <span className="mt-0.5 font-mono text-[10px] text-muted">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="line-clamp-2 block text-[12.5px] leading-5 text-fg">
                          {truncate(claim.original_claim, 150)}
                        </span>
                        <span className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1">
                          <ClassificationBadge classification={claim.classification} />
                          <span className="font-mono text-[9px] text-muted">
                            {claim.evidence.length} evidence
                          </span>
                          <span className="font-mono text-[9px] text-muted">
                            {claim.claim_type}
                          </span>
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
          <div className="min-h-[420px] lg:max-h-[720px] lg:overflow-hidden">
            <EvidenceViewer claim={selectedClaim} />
          </div>
        </div>
      )}
    </Card>
  );
}
