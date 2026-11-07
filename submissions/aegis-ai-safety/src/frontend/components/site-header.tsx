import Link from "next/link";
import { Database, ShieldCheck, Sparkles } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";
import type { DbHealth } from "@/lib/types";

interface SiteHeaderProps {
  apiOnline: boolean | null;
  db: DbHealth | null;
  provider?: string | null;
}

export function SiteHeader({ apiOnline, db, provider }: SiteHeaderProps) {
  const dbState =
    apiOnline === null
      ? { label: "Checking API", className: "text-muted border-border bg-panel-2" }
      : apiOnline === false
        ? { label: "API offline", className: "text-contradicted border-contradicted/30 bg-contradicted/10" }
        : db?.connected
          ? db.missing_tables.length === 0
            ? { label: "Db2 connected", className: "text-supported border-supported/30 bg-supported/10" }
            : { label: "Db2 schema incomplete", className: "text-insufficient border-insufficient/30 bg-insufficient/10" }
          : { label: "Db2 unavailable", className: "text-insufficient border-insufficient/30 bg-insufficient/10" };

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-[1400px] items-center justify-between gap-4 px-5 lg:px-8">
        <Link href="/" className="group flex items-center gap-3" aria-label="AEGIS home">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-accent/30 bg-accent-soft">
            <ShieldCheck className="h-5 w-5 text-accent" aria-hidden="true" />
          </span>
          <span className="leading-none">
            <span className="block text-[15px] font-semibold tracking-[0.2em] text-fg">AEGIS</span>
            <span className="mt-1 hidden font-mono text-[9px] uppercase tracking-[0.18em] text-muted sm:block">
              Verify before you trust.
            </span>
          </span>
        </Link>

        <nav className="hidden items-center gap-6 text-xs text-muted md:flex" aria-label="Primary">
          <a className="transition-colors hover:text-fg" href="#workspace">
            Workspace
          </a>
          <a className="transition-colors hover:text-fg" href="#results">
            Results
          </a>
          <a className="transition-colors hover:text-fg" href="#history">
            History
          </a>
          <a className="transition-colors hover:text-fg" href="#method">
            Method
          </a>
          <a className="transition-colors hover:text-fg" href="#evaluation">
            Evaluation
          </a>
        </nav>

        <div className="flex items-center gap-2">
          {provider ? (
            <span className="hidden items-center gap-1.5 rounded-full border border-border bg-panel-2 px-2.5 py-1 font-mono text-[10px] text-muted lg:flex">
              <Sparkles className="h-3 w-3 text-accent" aria-hidden="true" />
              {provider}
            </span>
          ) : null}
          <span
            className={cn(
              "flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px]",
              dbState.className
            )}
            title={db?.message ?? "IBM Db2 connection status"}
          >
            <Database className="h-3 w-3" aria-hidden="true" />
            {dbState.label}
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
