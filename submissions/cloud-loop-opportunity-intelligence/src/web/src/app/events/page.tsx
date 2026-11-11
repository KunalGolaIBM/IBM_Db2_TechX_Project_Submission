"use client";

import { useState, useMemo, useEffect } from "react";
import { motion } from "framer-motion";
import { Search } from "lucide-react";
import { EventCard, Event } from "@/features/events";
import { useOpportunities } from "@/components/providers/OpportunitiesProvider";
import { cn } from "@/lib/utils";

const types = ["All", "Hackathon", "Competition", "Bootcamp", "Workshop", "Conference"];
const formats = ["All", "Online", "In-person"];
const ITEMS_PER_PAGE = 15;

export default function EventsPage() {
  const { events: eventList } = useOpportunities();
  const [search, setSearch] = useState("");
  const [type, setType] = useState("All");
  const [format, setFormat] = useState("All");

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);

  // Reset pagination to page 1 whenever filters change
  useEffect(() => {
    setCurrentPage(1);
  }, [search, type, format]);


  const filtered = useMemo(() => {
    return eventList.filter((e) => {
      const matchSearch =
        search === "" ||
        e.title.toLowerCase().includes(search.toLowerCase()) ||
        e.organizer.toLowerCase().includes(search.toLowerCase());
      const matchType = type === "All" || e.type === type;
      const matchFormat = format === "All" || (format === "Online" ? e.isOnline : !e.isOnline);
      return matchSearch && matchType && matchFormat;
    });
  }, [eventList, search, type, format]);

  // Paginated events slice
  const paginatedEvents = useMemo(() => {
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
          <span className="text-xs font-semibold uppercase tracking-widest text-primary mb-2 block">Events</span>
          <h1 className="text-4xl md:text-5xl font-bold text-text-primary dark:text-dark-text-primary mb-3">
            Hackathons & Events
          </h1>
          <p className="text-text-secondary dark:text-dark-text-secondary max-w-xl">
            Competitions, bootcamps, workshops and conferences — find your next event to build, learn, and connect.
          </p>
        </div>

        <div className="mb-8 flex flex-col gap-4">
          <div className="relative">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary" />
            <input 
              value={search} 
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search events, organizers..."
              className="w-full pl-10 pr-4 py-3 rounded-xl border border-border dark:border-dark-border bg-white dark:bg-dark-card text-text-primary dark:text-dark-text-primary placeholder:text-text-secondary text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" 
            />
          </div>
          <div className="flex flex-wrap gap-4">
            <FilterGroup label="Type" options={types} value={type} onChange={setType} />
            <FilterGroup label="Format" options={formats} value={format} onChange={setFormat} />
          </div>
        </div>

        <div className="flex justify-between items-center mb-6">
          <p className="text-sm text-text-secondary">
            Showing {filtered.length > 0 ? (currentPage - 1) * ITEMS_PER_PAGE + 1 : 0}-
            {Math.min(currentPage * ITEMS_PER_PAGE, filtered.length)} of {filtered.length} event{filtered.length !== 1 ? "s" : ""} found
          </p>
          {totalPages > 1 && (
            <p className="text-xs text-text-secondary font-medium">Page {currentPage} of {totalPages}</p>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {paginatedEvents.map((event, i) => (
            <motion.div 
              key={event.id} 
              initial={{ opacity: 0, y: 16 }} 
              animate={{ opacity: 1, y: 0 }} 
              transition={{ duration: 0.25, delay: Math.min(i * 0.015, 0.2) }}
            >
              <EventCard event={event} />
            </motion.div>
          ))}
        </div>

        {/* Premium Pagination Bar */}
        {totalPages > 1 && (
          <div className="mt-12 flex items-center justify-center gap-2">
            <button 
              onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
              disabled={currentPage === 1}
              className={cn("px-4 py-2 text-xs font-semibold rounded-lg border transition-all cursor-pointer bg-white dark:bg-dark-card",
                currentPage === 1 ? "opacity-50 cursor-not-allowed border-border dark:border-dark-border text-text-secondary" : "border-border dark:border-dark-border hover:bg-secondary/15 hover:text-secondary dark:hover:text-primary dark:hover:border-primary text-text-primary dark:text-dark-text-primary"
              )}
            >
              ← Previous
            </button>
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, index) => {
                let pageNum = index + 1;
                if (currentPage > 3 && totalPages > 5) {
                  pageNum = currentPage - 3 + index;
                  if (pageNum + (4 - index) > totalPages) pageNum = totalPages - 4 + index;
                }
                if (pageNum <= 0 || pageNum > totalPages) return null;
                return (
                  <button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    className={cn("w-8 h-8 flex items-center justify-center text-xs font-bold rounded-lg border transition-all cursor-pointer",
                      currentPage === pageNum
                        ? "bg-secondary text-white border-secondary dark:bg-primary dark:text-dark-background dark:border-primary"
                        : "border-border dark:border-dark-border text-text-secondary bg-white dark:bg-dark-card hover:bg-secondary/10"
                    )}
                  >
                    {pageNum}
                  </button>
                );
              })}
            </div>
            <button 
              onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
              disabled={currentPage === totalPages}
              className={cn("px-4 py-2 text-xs font-semibold rounded-lg border transition-all cursor-pointer bg-white dark:bg-dark-card",
                currentPage === totalPages ? "opacity-50 cursor-not-allowed border-border dark:border-dark-border text-text-secondary" : "border-border dark:border-dark-border hover:bg-secondary/15 hover:text-secondary dark:hover:text-primary dark:hover:border-primary text-text-primary dark:text-dark-text-primary"
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
              : "border-border dark:border-dark-border text-text-secondary dark:text-dark-text-secondary hover:border-secondary/40"
          )}
        >
          {opt}
        </button>
      ))}
    </div>
  );
}
