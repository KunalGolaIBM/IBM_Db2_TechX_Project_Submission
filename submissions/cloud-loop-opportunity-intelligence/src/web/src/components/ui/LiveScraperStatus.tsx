"use client";

import React, { useState } from "react";
import { RefreshCw, Zap, CheckCircle2 } from "lucide-react";
import { useOpportunities } from "@/components/providers/OpportunitiesProvider";
import { cn } from "@/lib/utils";

export function LiveScraperStatus({ className }: { className?: string }) {
  const { isSyncing, lastSynced, totalOpportunitiesCount, triggerSync } = useOpportunities();
  const [justSynced, setJustSynced] = useState(false);

  const handleSync = async () => {
    if (isSyncing) return;
    await triggerSync();
    setJustSynced(true);
    setTimeout(() => setJustSynced(false), 3000);
  };

  const timeLabel = lastSynced
    ? `Synced ${lastSynced.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`
    : "Live Auto-Sync Active";

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-border/80 dark:border-dark-border/80 bg-white/80 dark:bg-dark-card/80 backdrop-blur-md text-xs text-text-secondary dark:text-dark-text-secondary shadow-sm transition-all hover:border-primary/40",
        className
      )}
    >
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
      </span>

      <span className="font-semibold text-text-primary dark:text-dark-text-primary">
        {totalOpportunitiesCount.toLocaleString()}+ Live
      </span>

      <span className="hidden sm:inline-block text-border dark:text-dark-border">•</span>

      <span className="hidden sm:inline-block text-[11px] opacity-80">
        {timeLabel}
      </span>

      <button
        onClick={handleSync}
        disabled={isSyncing}
        title="Trigger live scraper re-sync"
        className={cn(
          "ml-1 p-1 rounded-md transition-colors text-text-secondary hover:text-primary hover:bg-primary/10 cursor-pointer disabled:opacity-50",
          isSyncing && "text-primary animate-spin"
        )}
      >
        {justSynced ? (
          <CheckCircle2 size={13} className="text-emerald-500" />
        ) : (
          <RefreshCw size={13} className={cn(isSyncing && "animate-spin")} />
        )}
      </button>
    </div>
  );
}
