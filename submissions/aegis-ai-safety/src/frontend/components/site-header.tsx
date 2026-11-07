"use client";

import { Github, Play } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/utils";

interface SiteHeaderProps {
  live: boolean | null;
}

export function SiteHeader({ live }: SiteHeaderProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-line/80 bg-canvas/90 backdrop-blur-xl">
      <div className="shell flex h-[68px] items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2.5" aria-label="AEGIS home">
          <span className="relative flex h-7 w-7 items-center justify-center rounded-[9px] bg-ink text-[12px] font-semibold text-canvas">
            A
            <span className="absolute -right-0.5 -top-0.5 h-1.5 w-1.5 rounded-full bg-accent ring-2 ring-canvas" />
          </span>
          <span className="text-[15px] font-semibold tracking-[0.16em] text-ink">AEGIS</span>
          <span
            className={cn(
              "ml-1 hidden items-center gap-1.5 rounded-full border px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] sm:flex",
              live
                ? "border-supported/25 bg-supported-soft text-supported"
                : "border-line bg-surface text-muted"
            )}
          >
            <span className={cn("h-1 w-1 rounded-full", live ? "bg-supported" : "bg-muted")} />
            {live ? "Live" : "Demo"}
          </span>
        </Link>

        <nav className="flex items-center gap-1.5 sm:gap-4" aria-label="Primary">
          <a
            href="#how-it-works"
            className="hidden rounded-full px-3 py-2 text-[13px] text-muted transition-colors hover:text-ink sm:block"
          >
            How it works
          </a>
          <a
            href="#workspace"
            className="inline-flex items-center gap-1.5 rounded-full bg-ink px-3.5 py-2 text-[12.5px] font-medium text-canvas transition-transform hover:-translate-y-0.5 hover:bg-ink/90"
          >
            <Play className="h-3 w-3" aria-hidden="true" />
            Try AEGIS
          </a>
          <a
            href="https://github.com/sakethdonepudi/aegis-ai-safety"
            target="_blank"
            rel="noreferrer"
            aria-label="AEGIS on GitHub"
            className="rounded-full p-2 text-muted transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <Github className="h-4 w-4" aria-hidden="true" />
          </a>
        </nav>
      </div>
    </header>
  );
}
