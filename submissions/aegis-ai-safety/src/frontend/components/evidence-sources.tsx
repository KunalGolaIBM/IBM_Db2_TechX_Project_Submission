"use client";

import { AlertCircle, FileText, Loader2, Upload } from "lucide-react";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { cn, formatDate } from "@/lib/utils";
import type { DocumentSummary } from "@/lib/types";

interface EvidenceSourcesProps {
  documents: DocumentSummary[];
  selectedIds: number[];
  onToggle: (documentId: number) => void;
  onUpload: (file: File) => void;
  uploading: boolean;
  tab: "library" | "paste";
  onTabChange: (value: "library" | "paste") => void;
  evidenceText: string;
  onEvidenceTextChange: (value: string) => void;
  evidenceTitle: string;
  onEvidenceTitleChange: (value: string) => void;
  maxChars: number;
}

export function EvidenceSources({
  documents,
  selectedIds,
  onToggle,
  onUpload,
  uploading,
  tab,
  onTabChange,
  evidenceText,
  onEvidenceTextChange,
  evidenceTitle,
  onEvidenceTitleChange,
  maxChars,
}: EvidenceSourcesProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="min-w-0 rounded-lg border border-border bg-panel-2/40 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-fg">Evidence sources</p>
          <p className="mt-0.5 font-mono text-[10px] text-muted">
            {selectedIds.length} selected · PDF / TXT / MD · max 10 MB
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => inputRef.current?.click()}
          disabled={uploading}
        >
          {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
          {uploading ? "Uploading" : "Upload"}
        </Button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onUpload(file);
            event.target.value = "";
          }}
        />
      </div>

      <Tabs value={tab} onValueChange={(value) => onTabChange(value as "library" | "paste")}>
        <TabsList className="w-full">
          <TabsTrigger value="library" className="flex-1">
            Library
          </TabsTrigger>
          <TabsTrigger value="paste" className="flex-1">
            Paste evidence
          </TabsTrigger>
        </TabsList>

        <TabsContent value="library">
          {documents.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-md border border-dashed border-border px-4 py-7 text-center">
              <FileText className="h-5 w-5 text-muted" aria-hidden="true" />
              <p className="mt-2 text-xs text-fg">No evidence documents yet</p>
              <p className="mt-1 max-w-[280px] text-[11px] leading-5 text-muted">
                Upload a text-based PDF or paste a source passage. AEGIS retrieves passages from
                these documents only.
              </p>
            </div>
          ) : (
            <ul className="max-h-[220px] min-w-0 space-y-1.5 overflow-y-auto pr-1">
              {documents.map((document) => {
                const selected = selectedIds.includes(document.document_id);
                return (
                  <li key={document.document_id} className="min-w-0">
                    <button
                      type="button"
                      onClick={() => onToggle(document.document_id)}
                      aria-pressed={selected}
                      className={cn(
                        "flex w-full min-w-0 items-start gap-3 rounded-md border px-3 py-2.5 text-left transition-colors",
                        selected
                          ? "border-accent/40 bg-accent-soft/60"
                          : "border-border bg-panel hover:bg-panel-2"
                      )}
                    >
                      <span
                        className={cn(
                          "mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border",
                          selected ? "border-accent bg-accent text-[hsl(220_16%_4%)]" : "border-border"
                        )}
                        aria-hidden="true"
                      >
                        {selected ? (
                          <svg viewBox="0 0 12 12" className="h-3 w-3" fill="none">
                            <path d="M2.5 6.2l2.2 2.2 4.8-5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        ) : null}
                      </span>
                      <span className="min-w-0 flex-1 overflow-hidden">
                        <span className="block truncate text-xs font-medium text-fg">{document.title}</span>
                        <span className="mt-0.5 block truncate font-mono text-[10px] text-muted">
                          {document.filename} · {document.passage_count} passages · {formatDate(document.created_at)}
                        </span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </TabsContent>

        <TabsContent value="paste">
          <div className="space-y-2">
            <Input
              value={evidenceTitle}
              onChange={(event) => onEvidenceTitleChange(event.target.value)}
              placeholder="Evidence title (optional)"
              maxLength={200}
              aria-label="Evidence title"
            />
            <Textarea
              value={evidenceText}
              onChange={(event) => onEvidenceTextChange(event.target.value)}
              placeholder="Paste a source passage or document text. This is treated as untrusted data, never as instructions."
              rows={6}
              maxLength={maxChars}
              className="min-h-[130px] font-mono text-[12px] leading-6"
            />
            <div className="flex items-center justify-between font-mono text-[10px] text-muted">
              <span className="flex items-center gap-1">
                <AlertCircle className="h-3 w-3" aria-hidden="true" />
                Stored once and reused by content hash
              </span>
              <span className={evidenceText.length > maxChars * 0.9 ? "text-insufficient" : undefined}>
                {evidenceText.length.toLocaleString()} / {maxChars.toLocaleString()}
              </span>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
