"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database } from "lucide-react";
import { useBackend } from "./BackendProvider";
import { formatDate } from "@/lib/formatters";
import type { AsyncState } from "@/hooks/useAsync";
import type { HealthResponse, PlannerInfo } from "@/lib/api/types";
import { llmLabel } from "@/components/analytics/ModeDisclosure";

function Logo() {
  return (
    <svg aria-hidden viewBox="0 0 28 28" className="size-7 shrink-0">
      <rect width="28" height="28" rx="7" fill="#14130f" />
      <path d="M14 5.5 21.5 8.4v5.3c0 4.3-2.9 7.5-7.5 9.1-4.6-1.6-7.5-4.8-7.5-9.1V8.4L14 5.5Z" fill="none" stroke="#fff" strokeWidth="1.7" strokeLinejoin="round" />
      <path d="m10.8 14.2 2.3 2.3 4.3-4.6" fill="none" stroke="#6bd0a3" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

type Conn = { tone: "ok" | "warn" | "bad" | "idle"; label: string; title: string };

export function connectionState(h: AsyncState<HealthResponse>): Conn {
  if (h.loading && !h.data) return { tone: "idle", label: "Checking Db2…", title: "Waiting for GET /api/health" };
  if (h.error && !h.data) return { tone: "bad", label: "API offline", title: h.error.message };
  const d = h.data?.database;
  if (!d) return { tone: "bad", label: "API offline", title: "No health response" };
  if (d.status !== "up") return { tone: "bad", label: "Db2 unreachable", title: d.error?.message ?? "Database is down" };
  const level = d.service_level?.replace(/^DB2 /, "Db2 ") ?? "IBM Db2";
  if (h.data?.status !== "ok") return { tone: "warn", label: `${level} · degraded`, title: "Db2 is up but a health check did not pass (tables or registry hash)." };
  return { tone: "ok", label: `${level} · connected`, title: `${d.database} · ${d.latency_ms ?? "?"} ms` };
}

const DOT: Record<Conn["tone"], string> = { ok: "bg-ok", warn: "bg-warn", bad: "bg-bad", idle: "bg-ink-3" };

export function Header() {
  const path = usePathname();
  const { health, catalog } = useBackend();
  const conn = connectionState(health);
  const coverage = catalog.data?.data_coverage;
  const mode = health.data?.planner?.execution_mode;

  const nav = [
    { href: "/", label: "Workspace", active: path === "/" },
    { href: "/audit", label: "Audit history", active: path.startsWith("/audit") },
  ];

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/90 backdrop-blur supports-[backdrop-filter]:bg-bg/80">
      <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5 rounded-md" aria-label="MetricGuard home">
          <Logo />
          <span className="text-[17px] font-semibold tracking-tight">MetricGuard</span>
          <span className="hidden text-[13px] text-ink-3 lg:inline">Trustworthy AI analytics on IBM Db2</span>
        </Link>

        <nav aria-label="Primary" className="flex items-center gap-1 sm:ml-2">
          {nav.map((n) => (
            <Link
              key={n.href} href={n.href} aria-current={n.active ? "page" : undefined}
              className={clsx("rounded-lg px-3 py-1.5 text-[15px] font-medium transition-colors", n.active ? "bg-ink text-white" : "text-ink-2 hover:bg-sunken")}
            >
              {n.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {mode === "DEMO_RULE_BASED" && (
            <span data-testid="header-mode" className="inline-flex items-center rounded-full border border-warn/30 bg-warn-soft px-2.5 py-1 text-[13px] font-medium text-warn">
              Demo planner
            </span>
          )}
          {mode === "LLM" && (
            <span data-testid="header-mode" className="inline-flex items-center rounded-full border border-accent/25 bg-accent-soft px-2.5 py-1 text-[13px] font-medium text-accent-ink">
              {llmLabel({ name: health.data?.planner.provider ?? "llm", model: health.data?.planner.model, provider: health.data?.planner.provider as PlannerInfo["provider"] }, true)}
            </span>
          )}
          <span
            data-testid="db2-status" data-tone={conn.tone} title={conn.title}
            className="inline-flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1 text-[13px] font-medium text-ink-2"
          >
            <span aria-hidden className={clsx("size-2 rounded-full", DOT[conn.tone])} />
            <Database aria-hidden className="size-3.5 text-ink-3" />
            {conn.label}
          </span>
          {coverage && (
            <span data-testid="coverage" className="hidden text-[13px] text-ink-3 md:inline">
              Data {formatDate(coverage.start_date)} – {formatDate(coverage.end_date)}
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
