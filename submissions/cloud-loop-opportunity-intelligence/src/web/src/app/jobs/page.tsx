"use client";

import { useState, useMemo, useEffect } from "react";
import { motion } from "framer-motion";
import { Search, RefreshCw } from "lucide-react";
import { JobCard, Job } from "@/features/jobs";
import { useOpportunities } from "@/components/providers/OpportunitiesProvider";
import { cn } from "@/lib/utils";

const categories = ["All", "Software", "AI/ML", "Cloud", "Frontend", "Backend", "Data", "DevOps"];
const locationTypes = ["All", "Remote", "Hybrid", "Onsite"];
const ITEMS_PER_PAGE = 30;

export default function JobsPage() {
  const { jobs: jobList, isSyncing, triggerSync } = useOpportunities();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [locType, setLocType] = useState("All");
  const [easyApply, setEasyApply] = useState(false);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);

  // Reset pagination to page 1 whenever filters or search query changes
  useEffect(() => {
    setCurrentPage(1);
  }, [search, category, locType, easyApply]);


  const filtered = useMemo(() => {
    return jobList.filter((j) => {
      const matchSearch =
        search === "" ||
        j.role.toLowerCase().includes(search.toLowerCase()) ||
        j.company.toLowerCase().includes(search.toLowerCase());
      const matchCat = category === "All" || j.category === category;
      const matchLoc = locType === "All" || j.locationType === locType.toLowerCase();
      const matchEasy = !easyApply || j.isEasyApply;
      return matchSearch && matchCat && matchLoc && matchEasy;
    });
  }, [jobList, search, category, locType, easyApply]);

  // Paginated subset of filtered items
  const paginatedJobs = useMemo(() => {
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    return filtered.slice(startIndex, startIndex + ITEMS_PER_PAGE);
  }, [filtered, currentPage]);

  const totalPages = useMemo(() => {
    return Math.ceil(filtered.length / ITEMS_PER_PAGE);
  }, [filtered]);

  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-24 pb-16">
      <div className="container-narrow">
        <div className="mb-10">
          <span className="text-xs font-semibold uppercase tracking-widest text-primary mb-2 block">Jobs</span>
          <h1 className="text-4xl md:text-5xl font-bold text-text-primary dark:text-dark-text-primary mb-3">
            Fresher & Entry-Level Jobs
          </h1>
          <p className="text-text-secondary dark:text-dark-text-secondary max-w-xl">
            Full-time roles at top companies across software, AI/ML, cloud, data, and more. Freshers welcome.
          </p>
        </div>

        <div className="mb-8 flex flex-col gap-4">
          <div className="relative">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary" />
            <input 
              value={search} 
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search roles, companies..."
              className="w-full pl-10 pr-4 py-3 rounded-xl border border-border dark:border-dark-border bg-white dark:bg-dark-card text-text-primary dark:text-dark-text-primary placeholder:text-text-secondary text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" 
            />
          </div>
          <div className="flex flex-wrap gap-4 items-center">
            <FilterGroup label="Category" options={categories} value={category} onChange={setCategory} />
            <FilterGroup label="Location" options={locationTypes} value={locType} onChange={setLocType} />
            <button 
              onClick={() => setEasyApply(!easyApply)}
              className={cn("text-xs px-3 py-1.5 rounded-full border transition-colors cursor-pointer",
                easyApply ? "bg-primary text-white border-primary" : "border-border text-text-secondary"
              )}
            >
              ⚡ Easy Apply only
            </button>
          </div>
        </div>

        <div className="flex justify-between items-center mb-6">
          <p className="text-sm text-text-secondary">
            Showing {filtered.length > 0 ? (currentPage - 1) * ITEMS_PER_PAGE + 1 : 0}-
            {Math.min(currentPage * ITEMS_PER_PAGE, filtered.length)} of {filtered.length} job{filtered.length !== 1 ? "s" : ""} found
          </p>
          {totalPages > 1 && (
            <p className="text-xs text-text-secondary font-medium">
              Page {currentPage} of {totalPages}
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {paginatedJobs.map((job, i) => (
            <motion.div 
              key={job.id} 
              initial={{ opacity: 0, y: 16 }} 
              animate={{ opacity: 1, y: 0 }} 
              transition={{ duration: 0.25, delay: Math.min(i * 0.015, 0.2) }}
            >
              <JobCard job={job} />
            </motion.div>
          ))}
        </div>

        {/* Premium Pagination Bar */}
        {totalPages > 1 && (
          <div className="mt-12 flex items-center justify-center gap-2">
            <button 
              onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
              disabled={currentPage === 1}
              className={cn("px-4 py-2 text-xs font-semibold rounded-lg border transition-all cursor-pointer select-none",
                currentPage === 1 
                  ? "opacity-50 cursor-not-allowed border-border dark:border-dark-border text-text-secondary"
                  : "border-border dark:border-dark-border hover:bg-secondary/15 hover:text-secondary dark:hover:text-primary dark:hover:border-primary text-text-primary dark:text-dark-text-primary bg-white dark:bg-dark-card"
              )}
            >
              ← Previous
            </button>

            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, index) => {
                let pageNum = index + 1;
                // Center the active page button
                if (currentPage > 3 && totalPages > 5) {
                  pageNum = currentPage - 3 + index;
                  if (pageNum + (4 - index) > totalPages) {
                    pageNum = totalPages - 4 + index;
                  }
                }
                if (pageNum <= 0 || pageNum > totalPages) return null;
                
                return (
                  <button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    className={cn("w-8 h-8 flex items-center justify-center text-xs font-bold rounded-lg border transition-all cursor-pointer",
                      currentPage === pageNum
                        ? "bg-secondary text-white border-secondary dark:bg-primary dark:text-dark-background dark:border-primary"
                        : "border-border dark:border-dark-border text-text-secondary dark:text-dark-text-secondary hover:bg-secondary/10 bg-white dark:bg-dark-card"
                    )}
                  >
                    {pageNum}
                  </button>
                );
              })}
              {totalPages > 5 && currentPage + 2 < totalPages && (
                <span className="text-text-secondary text-xs px-1 select-none">...</span>
              )}
              {totalPages > 5 && currentPage + 2 < totalPages && (
                <button
                  onClick={() => setCurrentPage(totalPages)}
                  className="w-8 h-8 flex items-center justify-center text-xs font-bold rounded-lg border border-border dark:border-dark-border text-text-secondary bg-white dark:bg-dark-card hover:bg-secondary/10 cursor-pointer"
                >
                  {totalPages}
                </button>
              )}
            </div>

            <button 
              onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
              disabled={currentPage === totalPages}
              className={cn("px-4 py-2 text-xs font-semibold rounded-lg border transition-all cursor-pointer select-none",
                currentPage === totalPages 
                  ? "opacity-50 cursor-not-allowed border-border dark:border-dark-border text-text-secondary"
                  : "border-border dark:border-dark-border hover:bg-secondary/15 hover:text-secondary dark:hover:text-primary dark:hover:border-primary text-text-primary dark:text-dark-text-primary bg-white dark:bg-dark-card"
              )}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function FilterGroup({ label, options, value, onChange }: { label: string; options: string[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-xs text-text-secondary dark:text-dark-text-secondary font-medium">{label}:</span>
      {options.map((opt) => (
        <button 
          key={opt} 
          onClick={() => onChange(opt)}
          className={cn("text-xs px-3 py-1.5 rounded-full border transition-colors cursor-pointer",
            value === opt 
              ? "bg-secondary text-white border-secondary dark:bg-primary dark:border-primary dark:text-dark-background font-semibold" 
              : "border-border dark:border-dark-border text-text-secondary dark:text-dark-text-secondary hover:border-secondary/40 dark:hover:border-primary/40"
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
