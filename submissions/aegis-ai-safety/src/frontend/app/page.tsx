"use client";

import {
  AlertCircle,
  ArrowRight,
  Beaker,
  Database,
  Fingerprint,
  Layers,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ClaimInspector } from "@/components/claim-inspector";
import { EvaluationSection } from "@/components/evaluation-section";
import { EvidenceSources } from "@/components/evidence-sources";
import { HistoryPanel } from "@/components/history-panel";
import { MethodSection } from "@/components/method-section";
import { ResearchInput } from "@/components/research-input";
import { SiteHeader } from "@/components/site-header";
import { VerificationOverview } from "@/components/verification-overview";
import { Button } from "@/components/ui/button";
import { API_BASE, ApiError, getDbHealth, getDocuments, getEvaluation, getHealth, getVerification, getVerifications, uploadDocument, verifyResearch } from "@/lib/api";
import {
  DEMO_EVIDENCE_TEXT,
  DEMO_EVIDENCE_TITLE,
  DEMO_RESEARCH_TEXT,
  PAPER_DEMO_RESPONSE,
  PAPER_DEMO_TITLES,
} from "@/lib/demo";
import type {
  DbHealth,
  DocumentSummary,
  EvaluationData,
  Verification,
  VerificationSummary,
} from "@/lib/types";

const MAX_CHARS = 30_000;
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

const PIPELINE = [
  { step: "01", label: "Atomic claim extraction", detail: "LangChain structured output" },
  { step: "02", label: "Evidence retrieval", detail: "Db2 lexical search · BM25" },
  { step: "03", label: "Evidence-grounded judgment", detail: "Validated passage references" },
  { step: "04", label: "Provenance persistence", detail: "IBM Db2 · six tables" },
];

export default function HomePage() {
  const [researchText, setResearchText] = useState("");
  const [evidenceText, setEvidenceText] = useState("");
  const [evidenceTitle, setEvidenceTitle] = useState("");
  const [evidenceTab, setEvidenceTab] = useState<"library" | "paste">("library");
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocumentIds, setSelectedDocumentIds] = useState<number[]>([]);
  const [verification, setVerification] = useState<Verification | null>(null);
  const [selectedClaimId, setSelectedClaimId] = useState<number | null>(null);
  const [history, setHistory] = useState<VerificationSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [dbHealth, setDbHealth] = useState<DbHealth | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationData | null>(null);
  const [provider, setProvider] = useState<string | null>(null);
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const flashNotice = useCallback((message: string) => {
    setNotice(message);
    if (noticeTimer.current) clearTimeout(noticeTimer.current);
    noticeTimer.current = setTimeout(() => setNotice(null), 5_000);
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      setHistory(await getVerifications());
    } catch {
      // The connection banner already explains API failures.
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      try {
        const health = await getHealth();
        if (cancelled) return;
        setApiOnline(true);
        setProvider(health.llm_provider ? `${health.llm_provider}/${health.llm_model}` : null);
        const [dbResult, docsResult, evaluationResult] = await Promise.allSettled([
          getDbHealth(),
          getDocuments(),
          getEvaluation(),
        ]);
        if (cancelled) return;
        if (dbResult.status === "fulfilled") setDbHealth(dbResult.value);
        if (docsResult.status === "fulfilled") setDocuments(docsResult.value);
        if (evaluationResult.status === "fulfilled") setEvaluation(evaluationResult.value);
      } catch {
        if (!cancelled) setApiOnline(false);
      } finally {
        if (!cancelled) await loadHistory();
      }
    }
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [loadHistory]);

  const canSubmit =
    researchText.trim().length >= 10 &&
    !submitting &&
    (selectedDocumentIds.length > 0 ||
      (evidenceTab === "paste" && evidenceText.trim().length > 0));

  const handleUpload = useCallback(
    async (file: File) => {
      setError(null);
      const suffix = file.name.split(".").pop()?.toLowerCase();
      if (!suffix || !["pdf", "txt", "md"].includes(suffix)) {
        setError("Only .pdf, .txt, and .md evidence files are accepted.");
        return;
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        setError("The evidence file exceeds the 10 MB limit.");
        return;
      }
      setUploading(true);
      try {
        const uploaded = await uploadDocument(file, file.name.replace(/\.[^.]+$/, ""));
        setDocuments((current) => {
          const others = current.filter((item) => item.document_id !== uploaded.document_id);
          return [uploaded, ...others];
        });
        setSelectedDocumentIds((current) =>
          current.includes(uploaded.document_id) ? current : [...current, uploaded.document_id]
        );
        setEvidenceTab("library");
        flashNotice(
          uploaded.already_existed
            ? "That document is already in the evidence library and was selected."
            : `Parsed ${uploaded.passage_count} evidence passages from ${file.name}.`
        );
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Upload failed.");
      } finally {
        setUploading(false);
      }
    },
    [flashNotice]
  );

  const handleSyntheticDemo = useCallback(() => {
    setResearchText(DEMO_RESEARCH_TEXT);
    setEvidenceText(DEMO_EVIDENCE_TEXT);
    setEvidenceTitle(DEMO_EVIDENCE_TITLE);
    setEvidenceTab("paste");
    setError(null);
    flashNotice("Synthetic demo loaded. It contains fictional evidence and no expected answers.");
    document.getElementById("workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [flashNotice]);

  const handlePaperDemo = useCallback(() => {
    const matches = documents.filter((document) =>
      PAPER_DEMO_TITLES.some((title) => document.title.startsWith(title))
    );
    if (matches.length < PAPER_DEMO_TITLES.length) {
      setError(
        "Paper demo evidence is not in the Db2 library yet. Run `make demo-papers` to download the two arXiv PDFs and ingest them, then refresh this page."
      );
      return;
    }
    setResearchText(PAPER_DEMO_RESPONSE);
    setSelectedDocumentIds(matches.map((document) => document.document_id));
    setEvidenceTab("library");
    setError(null);
    flashNotice(
      "Paper demo loaded: real arXiv PDFs are selected as evidence. The summary claims are synthetic."
    );
    document.getElementById("workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [documents, flashNotice]);

  const handleSubmit = useCallback(async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      const result = await verifyResearch({
        submitted_text: researchText,
        document_ids: selectedDocumentIds,
        ...(evidenceTab === "paste" && evidenceText.trim()
          ? { evidence_text: evidenceText, evidence_title: evidenceTitle || undefined }
          : {}),
      });
      setVerification(result);
      setSelectedClaimId(result.claims[0]?.claim_id ?? null);
      setApiOnline(true);
      await loadHistory();
      void getDocuments()
        .then(setDocuments)
        .catch(() => undefined);
      requestAnimationFrame(() =>
        document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" })
      );
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.detail ? `${caught.message} (${caught.detail})` : caught.message);
        if (!caught.status) setApiOnline(false);
      } else {
        setError("Verification failed unexpectedly.");
      }
    } finally {
      setSubmitting(false);
    }
  }, [canSubmit, evidenceTab, evidenceText, evidenceTitle, loadHistory, researchText, selectedDocumentIds]);

  const handleOpenHistory = useCallback(async (sessionId: number) => {
    try {
      const detail = await getVerification(sessionId);
      setVerification(detail);
      setSelectedClaimId(detail.claims[0]?.claim_id ?? null);
      requestAnimationFrame(() =>
        document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" })
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not load that session.");
    }
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader apiOnline={apiOnline} db={dbHealth} provider={provider} />

      {apiOnline === false ? (
        <div className="border-b border-contradicted/25 bg-contradicted/5">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-2 px-5 py-2.5 text-[11px] text-contradicted lg:px-8">
            <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
            <span>The AEGIS API is unreachable at {API_BASE}.</span>
            <code className="rounded border border-contradicted/20 bg-panel px-1.5 py-0.5 font-mono text-[10px]">
              cd backend &amp;&amp; uvicorn app.main:app --reload
            </code>
          </div>
        </div>
      ) : null}

      <section className="relative overflow-hidden border-b border-border">
        <div className="pointer-events-none absolute inset-0 grid-fade" aria-hidden="true" />
        <div className="relative mx-auto grid max-w-[1400px] gap-10 px-5 py-12 lg:grid-cols-[1.15fr_0.85fr] lg:items-end lg:px-8 lg:py-16">
          <div>
            <p className="eyebrow flex items-center gap-2">
              <ShieldCheck className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
              Independent AI safety &amp; research verification
            </p>
            <h1 className="mt-5 max-w-2xl text-balance text-[42px] font-semibold leading-[1.02] tracking-[-0.035em] sm:text-6xl">
              Verify before you <span className="text-accent">trust.</span>
            </h1>
            <p className="mt-5 max-w-xl text-[13.5px] leading-6 text-muted">
              AEGIS examines AI-generated research claims against your evidence. Every judgment is
              evidence-linked, classification-validated, and preserved in IBM Db2 — so a confident
              sentence is never mistaken for a verified fact.
            </p>
            <div className="mt-6 flex flex-wrap gap-2">
              {["Atomic claims", "Retrieved passages", "Traceable judgments", "Reproducible sessions"].map(
                (label) => (
                  <span
                    key={label}
                    className="rounded-full border border-border bg-panel/70 px-2.5 py-1 font-mono text-[10px] text-muted"
                  >
                    {label}
                  </span>
                )
              )}
            </div>
          </div>

          <div className="panel p-5">
            <div className="flex items-center justify-between">
              <p className="eyebrow">Verification pipeline</p>
              <span className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-wider text-muted">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    apiOnline && dbHealth?.connected ? "bg-supported" : "bg-insufficient"
                  }`}
                />
                {apiOnline === null
                  ? "Checking"
                  : apiOnline && dbHealth?.connected
                    ? "Operational"
                    : "Degraded"}
              </span>
            </div>
            <ol className="mt-4 space-y-3">
              {PIPELINE.map((item) => (
                <li key={item.step} className="flex items-start gap-3">
                  <span className="mt-0.5 font-mono text-[9px] text-accent">{item.step}</span>
                  <span className="flex-1">
                    <span className="flex items-center justify-between gap-3 text-[11.5px] text-fg">
                      {item.label}
                      <ArrowRight className="h-3 w-3 text-border" aria-hidden="true" />
                    </span>
                    <span className="mt-0.5 block font-mono text-[9px] text-muted">{item.detail}</span>
                  </span>
                </li>
              ))}
            </ol>
            <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-4">
              {[
                { icon: Database, label: "DB2", value: "12.1.5" },
                { icon: Sparkles, label: "LANGCHAIN", value: "LLM" },
                { icon: Layers, label: "TABLES", value: "6" },
              ].map(({ icon: Icon, label, value }) => (
                <div key={label} className="rounded-md border border-border bg-panel-2/50 px-2.5 py-2">
                  <Icon className="h-3 w-3 text-muted" aria-hidden="true" />
                  <p className="mt-1.5 font-mono text-[8.5px] tracking-wider text-muted">{label}</p>
                  <p className="font-mono text-[11px] text-fg">{value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <main className="mx-auto w-full max-w-[1400px] flex-1 space-y-8 px-5 py-8 lg:px-8 lg:py-10">
        {notice ? (
          <div
            role="status"
            className="flex items-center gap-2 rounded-md border border-accent/25 bg-accent-soft px-3.5 py-2.5 text-[11.5px] text-accent"
          >
            <Beaker className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            {notice}
          </div>
        ) : null}

        <div className="grid gap-5 lg:grid-cols-[1.12fr_0.88fr] lg:items-stretch">
          <ResearchInput
            value={researchText}
            onChange={setResearchText}
            onSubmit={handleSubmit}
            onLoadPaperDemo={handlePaperDemo}
            onLoadSyntheticDemo={handleSyntheticDemo}
            submitting={submitting}
            canSubmit={canSubmit}
            error={error}
            maxChars={MAX_CHARS}
          >
            <EvidenceSources
              documents={documents}
              selectedIds={selectedDocumentIds}
              onToggle={(documentId) =>
                setSelectedDocumentIds((current) =>
                  current.includes(documentId)
                    ? current.filter((id) => id !== documentId)
                    : [...current, documentId]
                )
              }
              onUpload={handleUpload}
              uploading={uploading}
              tab={evidenceTab}
              onTabChange={setEvidenceTab}
              evidenceText={evidenceText}
              onEvidenceTextChange={setEvidenceText}
              evidenceTitle={evidenceTitle}
              onEvidenceTitleChange={setEvidenceTitle}
              maxChars={MAX_CHARS}
            />
          </ResearchInput>

          <VerificationOverview verification={verification} loading={submitting} />
        </div>

        <section className="space-y-3">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="eyebrow">03 / Results</p>
              <h2 className="mt-1.5 text-lg font-semibold tracking-tight">Claim-level judgments</h2>
            </div>
            <p className="max-w-md text-right text-[11px] leading-5 text-muted">
              Each claim carries its own classification and source link. Open a claim to inspect the
              exact passage, page reference, explanation, and limitations.
            </p>
          </div>
          <ClaimInspector
            verification={verification}
            selectedClaimId={selectedClaimId}
            onSelectClaim={setSelectedClaimId}
          />
        </section>

        <div className="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
          <HistoryPanel
            sessions={history}
            activeSessionId={verification?.session_id ?? null}
            loading={historyLoading}
            onOpen={handleOpenHistory}
          />
          <MethodSection />
        </div>

        <EvaluationSection evaluation={evaluation} />

        <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-panel-2/40 px-5 py-4">
          <div className="flex items-start gap-2.5">
            <Fingerprint className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
            <p className="max-w-2xl text-[11px] leading-5 text-muted">
              AEGIS produces transparent, evidence-linked assessments. It does not guarantee that a
              claim is true, and insufficient evidence is never reported as contradiction. Automated
              judgments require researcher review.
            </p>
          </div>
          <Button asChild variant="outline" size="sm">
            <a href={`${API_BASE}/docs`} target="_blank" rel="noreferrer">
              API documentation
              <ArrowRight className="h-3.5 w-3.5" />
            </a>
          </Button>
        </div>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 px-5 py-5 font-mono text-[10px] text-muted lg:px-8">
          <span>AEGIS v0.2 · Verify before you trust.</span>
          <span className="flex items-center gap-2">
            <span className="h-1 w-1 rounded-full bg-accent" />
            Next.js · FastAPI · LangChain · IBM Db2
          </span>
        </div>
      </footer>
    </div>
  );
}
