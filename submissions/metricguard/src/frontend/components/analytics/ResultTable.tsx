import clsx from "clsx";
import type { ResultBlock, ResultColumn } from "@/lib/api/types";
import { UNDEFINED_VALUE, formatCategory, formatValue } from "@/lib/formatters";

export function formatCell(col: ResultColumn, v: string | number | null | undefined): string {
  if (col.role === "dimension") return formatCategory(v);
  return typeof v === "number" || v === null || v === undefined ? formatValue(v ?? null, col.unit, col.scale) : String(v);
}

export function ResultTable({ result, caption }: { result: ResultBlock; caption?: string }) {
  return (
    <div className="scroll-quiet overflow-x-auto rounded-xl border border-line" tabIndex={0} role="region" aria-label={caption ?? "Result table"}>
      <table className="w-full min-w-max border-collapse text-[15px]" data-testid="result-table">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-line bg-sunken/60 text-left text-[13px] font-medium text-ink-3">
            {result.columns.map((c) => (
              <th key={c.name} scope="col" className={clsx("px-4 py-2.5 font-medium", c.role === "metric" && "text-right")}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.rows.map((row, i) => (
            <tr key={i} className="border-b border-line last:border-0">
              {result.columns.map((c) => {
                const raw = row[c.name];
                const undef = c.role === "metric" && (raw === null || raw === undefined);
                return (
                  <td key={c.name} className={clsx("px-4 py-2.5", c.role === "metric" ? "tabular text-right font-medium" : "text-ink-2")} title={undef ? "Undefined (not zero)" : undefined}>
                    {formatCell(c, raw)}
                    {undef && <span className="sr-only"> (undefined)</span>}
                  </td>
                );
              })}
            </tr>
          ))}
          {result.rows.length === 0 && (
            <tr><td colSpan={result.columns.length} className="px-4 py-6 text-center text-ink-3">{UNDEFINED_VALUE} No rows returned.</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
