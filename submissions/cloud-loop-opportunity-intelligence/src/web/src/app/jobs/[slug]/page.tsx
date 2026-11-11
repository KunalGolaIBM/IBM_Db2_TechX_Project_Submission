"use client";

import { notFound } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { useState, useEffect, use } from "react";
import {
  ExternalLink, Clock, MapPin, Calendar, CheckCircle2,
  Gift, Globe, Bookmark, Zap, ArrowLeft, Star
} from "lucide-react";
import { jobs } from "@/features/jobs";
import { JobCard } from "@/features/jobs/components/JobCard";
import { ProviderLogo } from "@/components/ui/ProviderLogo";
import { StatusSelector } from "@/components/ui/StatusSelector";
import { useAuth } from "@clerk/nextjs";
import { useOpportunities } from "@/components/providers/OpportunitiesProvider";
import { cn, formatDate, getDeadlineLabel } from "@/lib/utils";

const locationColors = {
  remote: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  hybrid: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  onsite: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

export default function JobDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { getJobBySlug, jobs: liveJobs } = useOpportunities();
  const job = getJobBySlug(slug) || jobs.find((j) => j.slug === slug || j.id === slug);
  const { isSignedIn } = useAuth();
  const [isBookmarked, setIsBookmarked] = useState(false);

  useEffect(() => {
    if (job && typeof window !== "undefined") {
      setIsBookmarked(localStorage.getItem(`bookmarked_${job.id}`) === "true");
    }
  }, [job]);

  if (!job) notFound();

  const related = (liveJobs.length > 0 ? liveJobs : jobs)
    .filter((j) => j.id !== job.id && (j.company === job.company || j.locationType === job.locationType))
    .slice(0, 2);


  const handleBookmark = async () => {
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

  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-20">
      <div className="bg-gradient-hero border-b border-border dark:border-dark-border py-14 px-4">
        <div className="container-narrow">
          <Link href="/jobs" className="inline-flex items-center gap-2 text-xs font-semibold text-text-secondary hover:text-primary mb-6 transition-colors">
            <ArrowLeft size={14} /> Back to Jobs
          </Link>
          <div className="flex items-start gap-5 mb-6">
            <ProviderLogo src={job.companyLogo} alt={job.company} fallback={job.company} size="lg" />
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-500 uppercase tracking-wide">
                  Open
                </span>
                <span className={cn("text-xs font-semibold px-2.5 py-0.5 rounded-full uppercase", locationColors[job.locationType])}>
                  {job.locationType}
                </span>
                {job.isEasyApply && (
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-primary/15 text-primary uppercase tracking-wide">
                    Easy Apply
                  </span>
                )}
              </div>
              <h1 className="text-3xl md:text-4xl font-bold text-text-primary dark:text-dark-text-primary leading-tight">{job.role}</h1>
              <p className="text-text-secondary dark:text-dark-text-secondary mt-1">at {job.company}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-6 text-sm text-text-secondary dark:text-dark-text-secondary mb-8">
            <span className="flex items-center gap-1.5"><MapPin size={14} /> {job.location}</span>
            <span className="flex items-center gap-1.5 font-medium text-emerald-600 dark:text-emerald-400">💰 {job.salaryRange}</span>
            <span className="flex items-center gap-1.5"><Calendar size={14} /> Posted: {formatDate(job.posted)}</span>
          </div>
          <div className="flex flex-wrap gap-3 items-center">
            <a href={job.applyUrl} target="_blank" rel="noopener noreferrer"
              className="btn-gradient px-6 py-3 rounded-pill text-sm font-semibold text-white inline-flex items-center gap-2 shadow-lg hover:scale-[1.02] transition-transform">
              Apply Now <ExternalLink size={15} />
            </a>
            <button
              onClick={handleBookmark}
              className={cn(
                "p-3 rounded-full border border-border dark:border-dark-border text-text-primary dark:text-dark-text-primary hover:bg-black/5 dark:hover:bg-white/5 transition-all",
                isBookmarked ? "text-amber-500 bg-amber-50 dark:bg-amber-950/20 border-amber-300" : ""
              )}
              aria-label="Bookmark this job"
            >
              <Bookmark size={16} className={isBookmarked ? "fill-amber-500" : ""} />
            </button>
            <StatusSelector id={job.id} />
          </div>
        </div>
      </div>

      <div className="container-narrow py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
          <div className="lg:col-span-2 space-y-10">
            <div>
              <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4 pb-2 border-b border-border dark:border-dark-border">
                Job Description
              </h2>
              <p className="text-text-secondary dark:text-dark-text-secondary leading-relaxed">{job.description}</p>
            </div>
            <div>
              <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4 pb-2 border-b border-border dark:border-dark-border">
                Required Skills
              </h2>
              <div className="flex flex-wrap gap-2">
                {job.skills.map((skill) => (
                  <span key={skill} className="text-xs px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-800 text-text-primary dark:text-dark-text-primary font-medium">
                    {skill}
                  </span>
                ))}
              </div>
            </div>
            {job.eligibleBatch && (
              <div>
                <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4 pb-2 border-b border-border dark:border-dark-border">
                  Eligible Batches
                </h2>
                <div className="p-4 rounded-xl border border-border dark:border-dark-border bg-gray-50 dark:bg-dark-card/50 text-sm text-text-secondary dark:text-dark-text-secondary">
                  Batches: <span className="font-semibold text-text-primary dark:text-dark-text-primary">{job.eligibleBatch}</span>
                </div>
              </div>
            )}
          </div>

          <div className="space-y-5">
            <div className="card-base p-5 space-y-4">
              <h3 className="font-semibold text-sm text-text-primary dark:text-dark-text-primary">Quick Summary</h3>
              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">Company</span>
                  <span className="font-medium text-text-primary dark:text-dark-text-primary">{job.company}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">Location Type</span>
                  <span className="font-medium text-text-primary dark:text-dark-text-primary capitalize">{job.locationType}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">Salary Range</span>
                  <span className="font-medium text-emerald-600 dark:text-emerald-400">{job.salaryRange}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">Experience</span>
                  <span className="font-medium text-text-primary dark:text-dark-text-primary">{job.experience}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-text-secondary">Deadline</span>
                  <span className="font-medium text-text-primary dark:text-dark-text-primary">{getDeadlineLabel(job.deadline)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {related.length > 0 && (
          <div className="mt-14 pt-10 border-t border-border dark:border-dark-border">
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-6">Related Jobs</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {related.map((j) => <JobCard key={j.id} job={j} />)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
