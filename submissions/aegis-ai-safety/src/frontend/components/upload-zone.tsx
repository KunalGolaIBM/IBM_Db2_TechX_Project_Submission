"use client";

import { Check, FileText, Info, Loader2, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

import { cn } from "@/lib/utils";
import type { DocumentSummary } from "@/lib/types";

interface UploadZoneProps {
  live: boolean;
  documents: DocumentSummary[];
  selectedIds: number[];
  uploading: boolean;
  onUpload: (file: File) => void;
  onToggle: (id: number) => void;
}

function formatSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function UploadZone({
  live,
  documents,
  selectedIds,
  uploading,
  onUpload,
  onToggle,
}: UploadZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);

  function accept(next: File | undefined) {
    if (!next) return;
    setFile(next);
    onUpload(next);
  }

  return (
    <div>
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Step 1</p>
          <h3 className="mt-1.5 text-[17px] font-semibold tracking-[-0.01em]">Add your research paper</h3>
        </div>
        <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted">
          PDF · max 10 MB
        </span>
      </div>

      <button
        type="button"
        onClick={() => live && inputRef.current?.click()}
        onDragOver={(event) => {
          if (!live) return;
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          if (!live) return;
          event.preventDefault();
          setDragging(false);
          accept(event.dataTransfer.files?.[0]);
        }}
        disabled={!live || uploading}
        className={cn(
          "group relative flex w-full flex-col items-center justify-center rounded-xl border border-dashed px-5 py-8 text-center transition-all",
          dragging
            ? "border-accent bg-accent-soft"
            : "border-line bg-surface hover:border-accent/40 hover:bg-accent-soft/40",
          !live && "cursor-default opacity-80"
        )}
        aria-label="Upload a research paper"
      >
        <span className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-canvas">
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin text-accent" aria-hidden="true" />
          ) : (
            <UploadCloud className="h-4 w-4 text-accent" aria-hidden="true" />
          )}
        </span>
        <span className="mt-3 text-[13px] font-medium text-ink">
          {uploading ? "Reading the paper…" : file ? file.name : "Drop a PDF here, or choose a file"}
        </span>
        <span className="mt-1 text-[11.5px] text-muted">
          {file
            ? `${formatSize(file.size)} · ${uploading ? "extracting text and passages" : "indexed in IBM Db2"}`
            : live
              ? "Searchable PDF. Scanned images without OCR are not supported."
              : "Live upload is disabled in the public demonstration."}
        </span>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt,.md,application/pdf,text/plain,text/markdown"
          className="hidden"
          onChange={(event) => {
            accept(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </button>

      {documents.length > 0 ? (
        <div className="mt-3 space-y-1.5">
          <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-muted">
            Evidence library
          </p>
          <ul className="max-h-[150px] space-y-1 overflow-y-auto pr-1">
            {documents.slice(0, 6).map((document) => {
              const selected = selectedIds.includes(document.document_id);
              return (
                <li key={document.document_id}>
                  <button
                    type="button"
                    onClick={() => onToggle(document.document_id)}
                    aria-pressed={selected}
                    className={cn(
                      "flex w-full items-center gap-2.5 rounded-lg border px-3 py-2 text-left transition-colors",
                      selected
                        ? "border-accent/30 bg-accent-soft"
                        : "border-line bg-surface hover:bg-surface-2"
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded-[5px] border",
                        selected ? "border-accent bg-accent text-white" : "border-line bg-canvas"
                      )}
                    >
                      {selected ? <Check className="h-3 w-3" aria-hidden="true" /> : null}
                    </span>
                    <FileText className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
                    <span className="min-w-0 flex-1 truncate text-[12px] text-ink">{document.title}</span>
                    <span className="shrink-0 font-mono text-[9px] text-muted">
                      {document.passage_count} passages
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}

      <details className="group mt-3 rounded-lg border border-line bg-surface px-3.5 py-3">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 text-[11.5px] font-medium text-ink">
          <Info className="h-3.5 w-3.5 text-muted" aria-hidden="true" />
          What should I upload?
          <span className="ml-auto text-muted transition-transform group-open:rotate-45">+</span>
        </summary>
        <div className="mt-3 grid gap-2 border-t border-line pt-3 text-[11.5px] leading-5 text-muted sm:grid-cols-2">
          <p>
            <span className="font-medium text-ink">Research paper</span>
            <br />
            The original source. This becomes evidence.
          </p>
          <p>
            <span className="font-medium text-ink">AI summary or claim</span>
            <br />
            The text you want checked. This becomes the claim.
          </p>
        </div>
      </details>
    </div>
  );
}
