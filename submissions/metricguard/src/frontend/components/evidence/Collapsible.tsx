"use client";

import { ChevronDown } from "lucide-react";
import { useId, useState } from "react";
import clsx from "clsx";

export function Collapsible({ title, meta, defaultOpen = false, children, testId }: {
  title: string; meta?: React.ReactNode; defaultOpen?: boolean; children: React.ReactNode; testId?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <section data-testid={testId} className="border-t border-ev-line first:border-t-0">
      <h3>
        <button
          type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center gap-3 px-5 py-3.5 text-left transition-colors hover:bg-white/[0.03]"
        >
          <span className="text-[15px] font-semibold text-ev-ink">{title}</span>
          {meta && <span className="min-w-0 truncate text-[13px] text-ev-ink-3">{meta}</span>}
          <ChevronDown aria-hidden className={clsx("ml-auto size-4 shrink-0 text-ev-ink-3 transition-transform", open && "rotate-180")} />
        </button>
      </h3>
      <div id={id} hidden={!open} className="px-5 pb-5">{open && children}</div>
    </section>
  );
}
