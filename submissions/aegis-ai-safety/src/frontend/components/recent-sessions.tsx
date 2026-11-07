"use client";

import { ChevronRight, History } from "lucide-react";

import type { VerificationSummary } from "@/lib/types";

export function RecentSessions({
  sessions,
  activeId,
  onOpen,
}: {
  sessions: VerificationSummary[];
  activeId: number | null;
  onOpen: (id: number) => void;
}) {
  if (sessions.length === 0) return null;
  return (
    <div className="mt-7">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.14em] text-muted">
          <History className="h-3 w-3" aria-hidden="true" />
          Recent verifications
        </p>
        <span className="font-mono text-[9px] text-muted">stored in IBM Db2</span>
      </div>
      <ul className="mt-2 space-y-1">
        {sessions.slice(0, 3).map((session) => (
          <li key={session.session_id}>
            <button
              type="button"
              onClick={() => onOpen(session.session_id)}
              className="flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-surface-2"
            >
              <span className="font-mono text-[9px] text-muted">#{session.session_id}</span>
              <span className="min-w-0 flex-1 truncate text-[11.5px] text-ink">{session.preview}</span>
              <span className="font-mono text-[9px] text-muted">
                {session.counts.total} claims
              </span>
              <ChevronRight className="h-3 w-3 text-muted" aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
