"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Clock, Users, Bookmark, Zap } from "lucide-react";
import { ProviderLogo } from "@/components/ui/ProviderLogo";
import { StatusSelector } from "@/components/ui/StatusSelector";
import { useAuth } from "@clerk/nextjs";
import { cn, getDeadlineLabel, getStatusColor, getDifficultyColor } from "@/lib/utils";
import { Program } from "../types/Program";

export function ProgramCard({ program, featured }: { program: Program; featured?: boolean }) {
  const { isSignedIn } = useAuth();
  const [isBookmarked, setIsBookmarked] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setIsBookmarked(localStorage.getItem(`bookmarked_${program.id}`) === "true");
    }
  }, [program.id]);

  const handleBookmark = async (e: React.MouseEvent) => {
    e.preventDefault();
    const next = !isBookmarked;
    localStorage.setItem(`bookmarked_${program.id}`, next ? "true" : "false");
    setIsBookmarked(next);

    if (isSignedIn) {
      try {
        await fetch("/api/opportunities/status", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ opportunityId: program.id, bookmarked: next }),
        });
      } catch (err) {
        console.error("Failed to sync bookmark to Supabase:", err);
      }
    }
  };

  return (
    <Link href={`/programs/${program.slug}`} className="block h-full">
      <div
        className={cn(
          "card-base p-5 h-full flex flex-col gap-4 cursor-pointer",
          featured && "border-primary/20 bg-gradient-card"
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <ProviderLogo
              src={program.providerLogo}
              alt={program.provider}
              fallback={program.provider}
              size="md"
            />
            <div>
              <p className="text-xs text-text-secondary dark:text-dark-text-secondary">{program.provider}</p>
              <p className="font-semibold text-sm text-text-primary dark:text-dark-text-primary leading-tight">{program.name}</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1.5 shrink-0">
            <span className={cn("text-[10px] font-semibold px-2 py-0.5 rounded-full uppercase tracking-wide", getStatusColor(program.status))}>
              {program.status}
            </span>
          </div>
        </div>

        {/* Description */}
        <p className="text-xs text-text-secondary dark:text-dark-text-secondary leading-relaxed line-clamp-2 flex-1">
          {program.keyBenefit}
        </p>

        {/* Meta */}
        <div className="flex flex-wrap gap-1.5">
          <span className={cn("text-[10px] font-medium px-2 py-0.5 rounded-full", getDifficultyColor(program.difficulty))}>
            {program.difficulty}
          </span>
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-text-secondary dark:text-dark-text-secondary flex items-center gap-1">
            <Clock size={9} /> {program.duration}
          </span>
          {program.applicants && (
            <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 text-text-secondary dark:text-dark-text-secondary flex items-center gap-1">
              <Users size={9} /> {(program.applicants / 1000).toFixed(0)}k+ applied
            </span>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-border dark:border-dark-border">
          <span className="text-xs text-text-secondary dark:text-dark-text-secondary flex items-center gap-1">
            <Zap size={11} className="text-amber-500" />
            {getDeadlineLabel(program.deadline)}
          </span>
          <div className="flex items-center gap-3">
            <button
              onClick={handleBookmark}
              aria-label="Bookmark"
              className={cn(
                "p-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 text-text-secondary transition-colors",
                isBookmarked ? "text-amber-500 fill-amber-500" : "text-text-secondary"
              )}
            >
              <Bookmark size={13} />
            </button>
            <StatusSelector id={program.id} />
          </div>
        </div>
      </div>
    </Link>
  );
}
