"use client";

import { useState, useMemo, useEffect } from "react";
import { motion } from "framer-motion";
import { Search } from "lucide-react";
import { InternshipCard, Internship } from "@/features/internships";
import { useOpportunities } from "@/components/providers/OpportunitiesProvider";
import { cn } from "@/lib/utils";

const locationTypes = ["All", "Remote", "Hybrid", "Onsite"];
const payTypes = ["All", "Paid", "Unpaid"];
const ITEMS_PER_PAGE = 30;

export default function InternshipsPage() {
  const { internships: internList } = useOpportunities();
  const [search, setSearch] = useState("");
  const [locType, setLocType] = useState("All");
  const [payType, setPayType] = useState("All");

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);

  // Reset pagination to page 1 whenever filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [search, locType, payType]);


  const filtered = useMemo(() => {
    return internList.filter((i) => {
      const matchSearch =
        search === "" ||
        i.role.toLowerCase().includes(search.toLowerCase()) ||
        i.company.toLowerCase().includes(search.toLowerCase());
      const matchLoc = locType === "All" || i.locationType === locType.toLowerCase();
      const matchPay = payType === "All" || (payType === "Paid" ? i.isPaid : !i.isPaid);
      return matchSearch && matchLoc && matchPay;
    });
  }, [internList, search, locType, payType]);

  // Slice the filtered list for pagination
  const paginatedInternships = useMemo(() => {
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
          <span className="text-xs font-semibold uppercase tracking-widest text-primary mb-2 block">Internships</span>
          <h1 className="text-4xl md:text-5xl font-bold text-text-primary dark:text-dark-text-primary mb-3">
            Internship Openings
          </h1>
          <p className="text-text-secondary dark:text-dark-text-secondary max-w-xl">
            Paid and unpaid internships at top companies — Google, Amazon, Microsoft, ISRO, CERN and more.
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
          <div className="flex flex-wrap gap-4">
            <FilterGroup label="Location" options={locationTypes} value={locType} onChange={setLocType} />
            <FilterGroup label="Type" options={payTypes} value={payType} onChange={setPayType} />
          </div>
        </div>

        <div className="flex justify-between items-center mb-6">
          <p className="text-sm text-text-secondary">
            Showing {filtered.length > 0 ? (currentPage - 1) * ITEMS_PER_PAGE + 1 : 0}-
            {Math.min(currentPage * ITEMS_PER_PAGE, filtered.length)} of {filtered.length} internship{filtered.length !== 1 ? "s" : ""} found
          </p>
          {totalPages > 1 && (
            <p className="text-xs text-text-secondary font-medium">
              Page {currentPage} of {totalPages}
            </p>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {paginatedInternships.map((internship, i) => (
            <motion.div 
              key={internship.id} 
              initial={{ opacity: 0, y: 16 }} 
              animate={{ opacity: 1, y: 0 }} 
              transition={{ duration: 0.25, delay: Math.min(i * 0.015, 0.2) }}
            >
              <InternshipCard internship={internship} />
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
