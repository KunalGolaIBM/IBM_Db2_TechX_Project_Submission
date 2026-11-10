import type { ReactNode } from "react";
import type { Status } from "../api";

/* Status label in the TLP form (mono caps in a small ink box). The word always shows: colour never carries the
   state alone, and there is no "safe" state and no green. */
const STATUS_STYLE: Record<Status, string> = {
  AFFECTED: "bg-ink text-affected-ink",
  UNKNOWN_COVERAGE: "bg-ink text-amber-ink",
  NOT_CONFIRMED: "bg-ink text-[#c4c8ca]",
  PREVIOUSLY_AFFECTED: "border border-rule text-mute",
};
export function StatusLabel({ status, onInk = false }: { status: Status; onInk?: boolean }) {
  const cls = onInk && status === "PREVIOUSLY_AFFECTED" ? "border border-slab-rule text-slab-mute" : STATUS_STYLE[status];
  return (
    <span className={`inline-flex items-center rounded-[3px] px-1.5 py-[1px] font-mono text-[11px] font-semibold leading-4 tracking-[0.02em] whitespace-nowrap ${cls}`}>
      {status}
    </span>
  );
}

export function Tag({ children, tone = "plain", title }: { children: ReactNode; tone?: "plain" | "ink" | "red" | "amber" | "accent"; title?: string }) {
  const t = {
    plain: "bg-surface text-ink-2",
    ink: "bg-ink text-paper",
    red: "bg-ink text-affected-ink",
    amber: "bg-amber-wash text-amber",
    accent: "bg-accent-wash text-accent-strong",
  }[tone];
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded-[3px] px-1.5 py-[1px] font-mono text-[11px] font-semibold leading-4 whitespace-nowrap ${t}`}>
      {children}
    </span>
  );
}

export function Dot({ ok, label, detail }: { ok: boolean | null; label: string; detail?: string }) {
  const c = ok == null ? "bg-rule" : ok ? "bg-accent" : "bg-affected";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-mute" title={detail}>
      <span className={`size-2 rounded-full ${c} ${ok === false ? "ring-2 ring-affected/20" : ""}`} aria-hidden />
      <span className="hidden md:inline">{label}</span>
      <span className="sr-only md:hidden">{label} </span>
      <span className="sr-only">{ok == null ? "checking" : ok ? "available" : "unavailable"}</span>
    </span>
  );
}

export function Segmented<T extends string>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: ReactNode }[]; onChange: (v: T) => void; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-[6px] border border-rule bg-paper p-0.5">
      {options.map((o) => (
        <button key={o.value} role="radio" aria-checked={value === o.value} onClick={() => onChange(o.value)}
          className={`min-h-8 rounded-[4px] px-3 text-sm font-medium transition-colors duration-150 ${value === o.value ? "bg-ink text-paper" : "text-ink-2 hover:bg-surface"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function SectionHead({ title, note, right }: { title: ReactNode; note?: ReactNode; right?: ReactNode }) {
  return (
    <div className="mb-3 flex flex-wrap items-end justify-between gap-x-6 gap-y-2">
      <div className="min-w-0">
        <h2 className="text-lg font-semibold tracking-[-0.01em]">{title}</h2>
        {note && <p className="mt-0.5 text-sm text-mute">{note}</p>}
      </div>
      {right}
    </div>
  );
}

const ERROR_TITLE: Record<string, string> = {
  login: "Sign-in failed", db: "Db2 unavailable", ollama: "Ollama unavailable", sql: "Db2 query failed",
  api: "API not running", input: "Check the request",
};
const ERROR_HINT: Record<string, string> = {
  login: "Check the Db2 user ID and password. RCAC binds to exactly this identity.",
  db: "Is Db2 running at DB2_HOST and DB2_PORT from .env, and is the database VECDB active?",
  ollama: "Start Ollama (localhost:11434) and pull nomic-embed-text. Nothing is shown from a cache.",
  sql: "Db2 answered with an error. Nothing is shown from a cache.",
  api: "Start it from the needle/ folder: python -m needle.api",
};
export function ErrorState({ kind, message, onRetry }: { kind: string; message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="panel fade-in border-l-[3px] border-l-affected p-4">
      <p className="font-semibold">{ERROR_TITLE[kind] ?? "Something failed"}</p>
      <p className="mt-1 font-mono text-xs break-words text-ink-2">{message}</p>
      {ERROR_HINT[kind] && <p className="mt-2 text-sm text-mute">{ERROR_HINT[kind]}</p>}
      {onRetry && <button className="btn btn-quiet mt-3" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden />;
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded-[3px] border border-rule bg-paper px-1 font-mono text-[11px] text-mute">{children}</kbd>;
}
