"use client";

import { AlertCircle, Beaker, BookOpen, Loader2, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

interface ResearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  onLoadPaperDemo: () => void;
  onLoadSyntheticDemo: () => void;
  submitting: boolean;
  canSubmit: boolean;
  error: string | null;
  maxChars: number;
  children: ReactNode;
}

export function ResearchInput({
  value,
  onChange,
  onSubmit,
  onLoadPaperDemo,
  onLoadSyntheticDemo,
  submitting,
  canSubmit,
  error,
  maxChars,
  children,
}: ResearchInputProps) {
  return (
    <Card id="workspace" className="min-w-0 scroll-mt-24">
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-4 space-y-0">
        <div>
          <p className="eyebrow">01 / Research input</p>
          <CardTitle className="mt-1.5 text-base">Paste AI-generated research</CardTitle>
          <CardDescription className="mt-1 max-w-md">
            Supply the text you want checked, then select the evidence it should be verified
            against. AEGIS extracts atomic claims and evaluates each one separately.
          </CardDescription>
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onLoadPaperDemo}
            disabled={submitting}
          >
            <BookOpen className="h-3.5 w-3.5" />
            Paper demo
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={onLoadSyntheticDemo}
            disabled={submitting}
          >
            <Beaker className="h-3.5 w-3.5" />
            Synthetic
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div>
          <div className="mb-2 flex items-center justify-between">
            <label htmlFor="research-text" className="text-xs font-medium text-fg">
              Research text
            </label>
            <span
              className={`font-mono text-[10px] ${
                value.length > maxChars * 0.9 ? "text-insufficient" : "text-muted"
              }`}
            >
              {value.length.toLocaleString()} / {maxChars.toLocaleString()}
            </span>
          </div>
          <Textarea
            id="research-text"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="Paste a research abstract, results section, or AI-generated summary. Example: “Method A achieved 92% accuracy and reduced inference time by 20%.”"
            rows={10}
            maxLength={maxChars}
            className="min-h-[220px] text-[13.5px] leading-6"
            disabled={submitting}
          />
          <p className="mt-2 flex items-center gap-1.5 text-[11px] text-muted">
            <AlertCircle className="h-3 w-3 shrink-0" aria-hidden="true" />
            Pasted content is untrusted data. Instructions inside it are never executed.
          </p>
        </div>

        {children}

        {error ? (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-contradicted/35 bg-contradicted/10 px-3 py-2.5 text-xs leading-5 text-contradicted"
          >
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        ) : null}

        <Button
          type="button"
          size="lg"
          className="w-full"
          onClick={onSubmit}
          disabled={!canSubmit || submitting}
        >
          {submitting ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Verifying claims against evidence…
            </>
          ) : (
            <>
              <ShieldCheck className="h-4 w-4" />
              Verify research claims
            </>
          )}
        </Button>
        <p className="text-center font-mono text-[10px] text-muted">
          Claims × evidence retrieval × LangChain assessment · persisted in IBM Db2
        </p>
      </CardContent>
    </Card>
  );
}
