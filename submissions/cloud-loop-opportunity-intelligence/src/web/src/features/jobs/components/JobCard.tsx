"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { MapPin, Bookmark, Zap, ExternalLink } from "lucide-react";
import { ProviderLogo } from "@/components/ui/ProviderLogo";
import { StatusSelector } from "@/components/ui/StatusSelector";
import { useAuth } from "@clerk/nextjs";
import { cn, getDeadlineLabel } from "@/lib/utils";
import { Job } from "../types/Job";

const locationColors = {
  remote: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  hybrid: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  onsite: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

export function JobCard({ job }: { job: Job }) {
  const { isSignedIn } = useAuth();
  const [isBookmarked, setIsBookmarked] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsBookmarked(localStorage.getItem(`bookmarked_${job.id}`) === "true");
    }
  }, [job.id]);

  const handleBookmark = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const next = !isBookmarked;
    localStorage.setItem(`bookmarked_${job.id}`, next ? "true" : "false");
    setIsBookmarked(next);

    if (isSignedIn) {
      try {
        await fetch("/api/opportunities/status", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ opportunityId: job.id, bookmarked: next }),
        });
      } catch (err) {
        console.error("Failed to sync bookmark to Supabase:", err);
      }
    }
  };

  const handleApply = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    window.open(job.applyUrl, "_blank", "noopener,noreferrer");
  };

  return (
    <Link href={`/jobs/${job.slug}`} className="block h-full">
      <div className="card-base p-5 h-full flex flex-col gap-3 relative group">
        {/* Header */}
        <div className="flex items-start gap-3">
          <ProviderLogo
            src={job.companyLogo}
            alt={job.company}
            fallback={job.company}
            size="md"
          />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <p className="font-semibold text-sm text-text-primary dark:text-dark-text-primary truncate">{job.role}</p>
              {job.isEasyApply && (
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-primary/15 text-primary uppercase tracking-wide shrink-0">
                  Easy Apply
                </span>
              )}
              {job.id.startsWith("scraped-") && (
                <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-500 uppercase tracking-wide shrink-0 animate-pulse border border-amber-500/20">
                  ⚡ Live Scraped
                </span>
              )}
            </div>
            <p className="text-xs text-text-secondary dark:text-dark-text-secondary">{job.company}</p>
          </div>
          <div className="flex flex-col items-end gap-1 shrink-0">
            <span className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide", locationColors[job.locationType])}>
              {job.locationType}
            </span>
            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-500 uppercase tracking-wide">
              Open
            </span>
          </div>
        </div>

        {/* Meta */}
        <div className="flex flex-wrap gap-2 text-xs text-text-secondary dark:text-dark-text-secondary">
          <span className="flex items-center gap-1"><MapPin size={11} />{job.location}</span>
          <span className="flex items-center gap-1 font-medium text-emerald-600 dark:text-emerald-400">
            💰 {job.salaryRange}
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800">
            {job.experience}
          </span>
          {job.eligibleBatch && (
            <span className="bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded text-[10px]">
              Batch: {job.eligibleBatch}
            </span>
          )}
        </div>

        {/* Tags */}
        <div className="flex flex-wrap gap-1.5 flex-1">
          {job.tags.map((tag) => (
            <span key={tag} className="text-[10px] px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-text-secondary dark:text-dark-text-secondary">
              {tag}
            </span>
          ))}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-2 border-t border-border dark:border-dark-border gap-2">
          <span className="text-xs text-text-secondary dark:text-dark-text-secondary flex items-center gap-1">
            <Zap size={11} className="text-amber-500" />
            {getDeadlineLabel(job.deadline)}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={handleApply}
              className="inline-flex items-center gap-1 text-xs font-bold text-white bg-primary hover:bg-primary/95 px-3 py-1.5 rounded-lg shadow-sm transition-all"
            >
              Apply Now <ExternalLink size={10} />
            </button>
            <button
              onClick={handleBookmark}
              aria-label="Save"
              className={cn(
                "p-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 text-text-secondary transition-colors",
                isBookmarked ? "text-amber-500 fill-amber-500" : "text-text-secondary"
              )}
            >
              <Bookmark size={13} />
            </button>
            <StatusSelector id={job.id} />
          </div>
        </div>
      </div>
    </Link>
  );
}
