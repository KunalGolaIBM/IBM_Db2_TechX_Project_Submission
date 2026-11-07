"use client";

import { ArrowRight, Github, Play, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ClaimComposer } from "@/components/claim-composer";
import { HeroDemo } from "@/components/hero-demo";
import { HowItWorks } from "@/components/how-it-works";
import { RecentSessions } from "@/components/recent-sessions";
import { ResultsAudit } from "@/components/results-audit";
import { SiteHeader } from "@/components/site-header";
import { TrustSection } from "@/components/trust-section";
import { UploadZone } from "@/components/upload-zone";
import {
  ApiError,
  getDocuments,
  getHealth,
  getVerification,
  getVerifications,
  uploadDocument,
  verifyResearch,
} from "@/lib/api";
import { PAPER_DEMO_TITLES } from "@/lib/demo";
import { SHOWCASE_CLAIMS, SHOWCASE_VERIFICATION } from "@/lib/showcase";
import type { DocumentSummary, Verification, VerificationSummary } from "@/lib/types";

const MAX_CHARS = 30_000;
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const SHOWCASE_ONLY = process.env.NEXT_PUBLIC_SHOWCASE_ONLY === "1";

type Mode = "checking" | "live" | "demo";

export default function HomePage() {
  const [mode, setMode] = useState<Mode>(SHOWCASE_ONLY ? "demo" : "checking");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<number[]>([]);
  const [researchText, setResearchText] = useState(SHOWCASE_ONLY ? SHOWCASE_CLAIMS : "");
  const [verification, setVerification] = useState<Verification | null>(
    SHOWCASE_ONLY ? SHOWCASE_VERIFICATION : null
  );
  const [selectedClaimId, setSelectedClaimId] = useState<number | null>(
    SHOWCASE_ONLY ? SHOWCASE_VERIFICATION.claims[0]?.claim_id ?? null : null
  );
  const [history, setHistory] = useState<VerificationSummary[]>([]);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const live = mode === "live";

  const flash = useCallback((message: string) => {
    setNotice(message);
    if (noticeTimer.current) clearTimeout(noticeTimer.current);
    noticeTimer.current = setTimeout(() => setNotice(null), 6500);
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await getVerifications());
    } catch {
      // The live/demo state already communicates availability.
    }
  }, []);

  useEffect(() => {
    if (SHOWCASE_ONLY) return;
    let cancelled = false;
    async function bootstrap() {
      try {
        await getHealth();
        if (cancelled) return;
        setMode("live");
        const docs = await getDocuments().catch(() => []);
        if (cancelled) return;
        setDocuments(docs);
        await loadHistory();
      } catch {
        if (cancelled) return;
        setMode("demo");
        setVerification(SHOWCASE_VERIFICATION);
        setSelectedClaimId(SHOWCASE_VERIFICATION.claims[0]?.claim_id ?? null);
        setResearchText(SHOWCASE_CLAIMS);
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [loadHistory]);

  const loadExample = useCallback(() => {
    setError(null);
    setResearchText(SHOWCASE_CLAIMS);
    if (live) {
      const matches = documents.filter((document) =>
        PAPER_DEMO_TITLES.some((title) => document.title.startsWith(title))
      );
      if (matches.length > 0) {
        setSelectedDocumentIds(matches.map((document) => document.document_id));
        flash("BERT example loaded. The paper is selected as evidence.");
        document.getElementById("workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
      flash("No paper is indexed yet. Showing the recorded verification instead.");
    }
    setMode("demo");
    setVerification(SHOWCASE_VERIFICATION);
    setSelectedClaimId(SHOWCASE_VERIFICATION.claims[0]?.claim_id ?? null);
    flash("Recorded BERT verification loaded. This is not a live run.");
    requestAnimationFrame(() =>
      document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" })
    );
  }, [documents, flash, live]);

  const handleUpload = useCallback(
    async (file: File) => {
      if (!live) return;
      setError(null);
      const suffix = file.name.split(".").pop()?.toLowerCase();
      if (!suffix || !["pdf", "txt", "md"].includes(suffix)) {
        setError("Use a PDF, TXT, or Markdown paper.");
        return;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        setError("That file is larger than the 10 MB limit.");
        return;
      }
      setUploading(true);
      try {
        const uploaded = await uploadDocument(file, file.name.replace(/\.[^.]+$/, ""));
        setDocuments((current) => [
          uploaded,
          ...current.filter((item) => item.document_id !== uploaded.document_id),
        ]);
        setSelectedDocumentIds((current) =>
          current.includes(uploaded.document_id) ? current : [...current, uploaded.document_id]
        );
        flash(
          uploaded.already_existed
            ? "That paper is already in the library and is selected."
            : `Indexed ${uploaded.passage_count} passages from ${file.name}.`
        );
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "The paper could not be uploaded.");
      } finally {
        setUploading(false);
      }
    },
    [flash, live]
  );

  const canSubmit =
    live &&
    researchText.trim().length >= 10 &&
    !submitting &&
    !uploading &&
    selectedDocumentIds.length > 0;

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await verifyResearch({
        submitted_text: researchText,
        document_ids: selectedDocumentIds,
      });
      setVerification(result);
      setSelectedClaimId(result.claims[0]?.claim_id ?? null);
      await loadHistory();
      requestAnimationFrame(() =>
        document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" })
      );
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.detail ? `${caught.message} (${caught.detail})` : caught.message);
        if (!caught.status) setMode("demo");
      } else {
        setError("Verification failed unexpectedly.");
      }
    } finally {
      setSubmitting(false);
    }
  }, [canSubmit, loadHistory, researchText, selectedDocumentIds]);

  const handleOpenHistory = useCallback(async (sessionId: number) => {
    try {
      const detail = await getVerification(sessionId);
      setVerification(detail);
      setSelectedClaimId(detail.claims[0]?.claim_id ?? null);
      requestAnimationFrame(() =>
        document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" })
      );
    } catch {
      flash("That session could not be opened.");
    }
  }, [flash]);

  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader live={mode === "live" ? true : mode === "demo" ? false : null} />

      <main className="flex-1">
        <section className="relative overflow-hidden">
          <div
            className="pointer-events-none absolute inset-x-0 top-0 h-[520px] bg-[radial-gradient(ellipse_60%_60%_at_70%_0%,hsl(var(--accent)/0.07),transparent_70%)]"
            aria-hidden="true"
          />
          <div className="shell relative grid gap-12 pb-16 pt-16 sm:pb-20 sm:pt-20 lg:grid-cols-[1fr_0.82fr] lg:items-center lg:gap-16 lg:pb-24 lg:pt-24">
            <div>
              <p className="eyebrow flex items-center gap-2">
                <span className="h-1 w-1 rounded-full bg-accent" />
                Independent research verification
              </p>
              <h1 className="display mt-5 text-[42px] text-ink sm:text-[58px] lg:text-[64px]">
                The paper exists.
                <br />
                <span className="block text-muted">Does the evidence?</span>
              </h1>
              <p className="mt-6 max-w-lg text-[15px] leading-7 text-muted sm:text-[16px]">
                Check AI-generated research claims against actual scientific papers. See the
                exact passage, page, and source — or learn that the paper does not establish it.
              </p>
              <div className="mt-8 flex flex-wrap items-center gap-3">
                <a
                  href="#workspace"
                  className="inline-flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-[13px] font-medium text-canvas transition-transform hover:-translate-y-0.5 hover:bg-ink/90"
                >
                  Start verifying
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </a>
                <a
                  href="#how-it-works"
                  className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-5 py-3 text-[13px] font-medium text-ink transition-colors hover:border-accent/30 hover:text-accent"
                >
                  <Play className="h-3.5 w-3.5" aria-hidden="true" />
                  See how it works
                </a>
              </div>
              <div className="mt-9 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-[9.5px] uppercase tracking-[0.13em] text-muted">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="h-3 w-3 text-accent" aria-hidden="true" />
                  Evidence-linked
                </span>
                <span>IBM Db2</span>
                <span>LangChain</span>
                <span>Page-level provenance</span>
              </div>
            </div>
            <HeroDemo />
          </div>
        </section>

        <HowItWorks />

        <section id="workspace" className="scroll-mt-20 border-t border-line py-20 sm:py-24">
          <div className="shell">
            <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
              <div>
                <p className="eyebrow">Try AEGIS</p>
                <h2 className="display mt-3 text-[36px] text-ink sm:text-[46px]">
                  Verify a research claim
                </h2>
                <p className="mt-3 text-[14px] leading-6 text-muted">
                  Upload the paper. Paste the claim. See the evidence.
                </p>
              </div>
              <span className="inline-flex w-fit items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.12em] text-muted">
                <span className={mode === "live" ? "h-1 w-1 rounded-full bg-supported" : "h-1 w-1 rounded-full bg-muted"} />
                {mode === "checking" ? "Checking connection" : live ? "Live verification" : "Interactive demonstration"}
              </span>
            </div>

            {notice ? (
              <div
                role="status"
                className="mt-6 rounded-xl border border-accent/20 bg-accent-soft px-4 py-3 text-[12px] leading-5 text-ink"
              >
                {notice}
              </div>
            ) : null}

            <div className="mt-8 grid gap-px overflow-hidden rounded-2xl border border-line bg-line lg:grid-cols-2">
              <div className="bg-surface p-5 sm:p-7">
                <UploadZone
                  live={live}
                  documents={documents}
                  selectedIds={selectedDocumentIds}
                  uploading={uploading}
                  onUpload={handleUpload}
                  onToggle={(id) =>
                    setSelectedDocumentIds((current) =>
                      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
                    )
                  }
                />
                {live ? (
                  <RecentSessions
                    sessions={history}
                    activeId={verification?.session_id ?? null}
                    onOpen={handleOpenHistory}
                  />
                ) : null}
              </div>
              <div className="bg-surface p-5 sm:p-7">
                <ClaimComposer
                  value={researchText}
                  onChange={setResearchText}
                  onSubmit={handleSubmit}
                  onClear={() => {
                    setResearchText("");
                    setError(null);
                  }}
                  onExample={loadExample}
                  submitting={submitting}
                  canSubmit={canSubmit}
                  live={live}
                  error={error}
                  maxChars={MAX_CHARS}
                />
                {!live && mode === "demo" ? (
                  <div className="mt-4 rounded-xl border border-line bg-canvas px-4 py-3">
                    <p className="text-[11.5px] leading-5 text-muted">
                      <span className="font-medium text-ink">Public demonstration.</span> Live
                      verification requires the FastAPI backend, IBM Db2, and a local or hosted
                      inference service. The example above is a recorded Db2 session, clearly
                      labelled.
                    </p>
                    <button
                      type="button"
                      onClick={loadExample}
                      className="mt-2 inline-flex items-center gap-1.5 text-[11.5px] font-medium text-accent hover:underline"
                    >
                      Open the recorded example
                      <ArrowRight className="h-3 w-3" aria-hidden="true" />
                    </button>
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </section>

        {verification ? (
          <ResultsAudit
            verification={verification}
            demo={!live}
            selectedClaimId={selectedClaimId}
            onSelectClaim={setSelectedClaimId}
          />
        ) : null}

        <TrustSection />
      </main>

      <footer className="border-t border-line py-8">
        <div className="shell flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
          <div>
            <p className="text-[12px] font-semibold tracking-[0.14em] text-ink">AEGIS</p>
            <p className="mt-1 text-[11px] text-muted">The paper exists. Does the evidence?</p>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-[11px] text-muted">
            <a href="#how-it-works" className="hover:text-ink">
              How it works
            </a>
            <a href="https://github.com/sakethdonepudi/aegis-ai-safety" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 hover:text-ink">
              <Github className="h-3.5 w-3.5" aria-hidden="true" />
              Source
            </a>
            <span className="font-mono text-[9px] uppercase tracking-[0.1em]">
              Built with IBM Db2 · LangChain
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
