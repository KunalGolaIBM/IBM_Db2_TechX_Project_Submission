"use client";

import { WrapText } from "lucide-react";
import { useMemo, useState } from "react";
import clsx from "clsx";
import { tokenizeSql, type SqlTokenType } from "@/lib/sql-highlight";
import { CopyButton } from "@/components/common/CopyButton";

const COLOR: Record<SqlTokenType, string> = {
  keyword: "text-[var(--sql-keyword)] font-medium", string: "text-[var(--sql-string)]", number: "text-[var(--sql-number)]",
  comment: "italic text-[var(--sql-comment)]", param: "rounded bg-[#f0a0c0]/15 px-0.5 font-semibold text-[var(--sql-param)]",
  type: "text-[var(--sql-type)]", func: "text-[var(--sql-func)]", text: "text-[#e6e5df]",
};

/** Syntax-highlighted, scrollable SQL with line numbers and a copy action. Long lines scroll, never break the page. */
export function SqlBlock({ sql, sqlHash }: { sql: string; sqlHash?: string }) {
  const [wrap, setWrap] = useState(false);
  const lines = useMemo(() => {
    // Split tokens into lines so each line can carry its own number.
    const out: { type: SqlTokenType; value: string }[][] = [[]];
    for (const t of tokenizeSql(sql)) {
      const parts = t.value.split("\n");
      parts.forEach((part, i) => {
        if (i > 0) out.push([]);
        if (part) out[out.length - 1]!.push({ type: t.type, value: part });
      });
    }
    return out;
  }, [sql]);

  return (
    <div className="overflow-hidden rounded-xl border border-ev-line bg-[#0f1114]" data-testid="sql-block">
      <div className="flex items-center justify-between gap-2 border-b border-ev-line px-3 py-1.5">
        <span className="min-w-0 truncate font-mono text-[12px] text-ev-ink-3">IBM Db2 SQL{sqlHash ? ` · sha256 ${sqlHash.slice(0, 8)}` : ""}</span>
        <div className="flex items-center gap-1">
          <button
            type="button" onClick={() => setWrap((w) => !w)} aria-pressed={wrap}
            className={clsx("inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors", wrap ? "bg-white/15 text-white" : "text-ev-ink-2 hover:bg-white/10")}
          >
            <WrapText aria-hidden className="size-3.5" /> Wrap
          </button>
          <CopyButton text={sql} label="Copy SQL" copiedLabel="Copied" testId="copy-sql" className="text-ev-ink-2 hover:bg-white/10" />
        </div>
      </div>
      <pre
        tabIndex={0} aria-label="Executed SQL"
        className={clsx("scroll-quiet max-h-[26rem] overflow-auto py-3 font-mono text-[13px] leading-[1.65]", wrap ? "whitespace-pre-wrap break-words" : "whitespace-pre")}
      >
        <code data-testid="sql-text">
          {lines.map((line, i) => (
            <span key={i} className="flex">
              <span aria-hidden className="sticky left-0 w-9 shrink-0 select-none bg-[#0f1114] pr-3 text-right text-[#5b5a53]">{i + 1}</span>
              <span className="min-w-0 pr-4">
                {line.length === 0 ? "​" : line.map((t, j) => <span key={j} className={COLOR[t.type]}>{t.value}</span>)}
              </span>
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
}
