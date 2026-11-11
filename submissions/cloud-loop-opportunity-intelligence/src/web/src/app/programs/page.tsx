"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { ProgramCard } from "@/features/programs";
import { useOpportunities } from "@/components/providers/OpportunitiesProvider";
import { cn } from "@/lib/utils";

const categories = ["All", "Cloud", "Ambassador", "Open Source", "AI/ML", "Technology", "Networking", "Community"];
const difficulties = ["All", "Beginner", "Intermediate", "Advanced"];
const statuses = ["All", "Open", "Closed"];

export default function ProgramsPage() {
  const { programs: programList } = useOpportunities();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("All");
  const [difficulty, setDifficulty] = useState("All");
  const [status, setStatus] = useState("All");

  const filtered = useMemo(() => {
    return programList.filter((p) => {
      const matchSearch = search === "" ||
        p.name.toLowerCase().includes(search.toLowerCase()) ||
        p.provider.toLowerCase().includes(search.toLowerCase());
      const matchCategory = category === "All" || p.category === category;
      const matchDifficulty = difficulty === "All" || p.difficulty === difficulty;
      const matchStatus = status === "All" || p.status === status.toLowerCase();
      return matchSearch && matchCategory && matchDifficulty && matchStatus;
    });
  }, [programList, search, category, difficulty, status]);


  const activeFilters = [
    category !== "All" && category,
    difficulty !== "All" && difficulty,
    status !== "All" && status,
  ].filter(Boolean) as string[];

  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-24 pb-16">
      <div className="container-narrow">
        {/* Header */}
        <div className="mb-10">
          <span className="text-xs font-semibold uppercase tracking-widest text-primary mb-2 block">Programs</span>
          <h1 className="text-4xl md:text-5xl font-bold text-text-primary dark:text-dark-text-primary mb-3">
            Student Programs
          </h1>
          <p className="text-text-secondary dark:text-dark-text-secondary max-w-xl">
            Ambassador programs, learning programs, open source initiatives — hand-picked from Google, Microsoft, GitHub, AWS and more.
          </p>
        </div>

        {/* Search + Filters */}
        <div className="mb-8 flex flex-col gap-4">
          <div className="relative">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search programs, providers..."
              className="w-full pl-10 pr-4 py-3 rounded-xl border border-border dark:border-dark-border bg-white dark:bg-dark-card text-text-primary dark:text-dark-text-primary placeholder:text-text-secondary text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>

          {/* Filter pills */}
          <div className="flex flex-wrap gap-2">
            <FilterGroup label="Category" options={categories} value={category} onChange={setCategory} />
            <FilterGroup label="Level" options={difficulties} value={difficulty} onChange={setDifficulty} />
            <FilterGroup label="Status" options={statuses} value={status} onChange={setStatus} />
          </div>

          {activeFilters.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-text-secondary">Active filters:</span>
              {activeFilters.map((f) => (
                <span key={f} className="flex items-center gap-1 text-xs px-2.5 py-1 rounded-full bg-secondary/10 text-secondary dark:bg-primary/10 dark:text-primary font-medium">
                  {f}
                  <button onClick={() => { setCategory("All"); setDifficulty("All"); setStatus("All"); }}>
                    <X size={10} />
                  </button>
                </span>
              ))}
              <button onClick={() => { setCategory("All"); setDifficulty("All"); setStatus("All"); setSearch(""); }}
                className="text-xs text-text-secondary hover:text-text-primary underline">
                Clear all
              </button>
            </div>
          )}
        </div>

        {/* Results count */}
        <p className="text-sm text-text-secondary dark:text-dark-text-secondary mb-6">
          {filtered.length} program{filtered.length !== 1 ? "s" : ""} found
        </p>

        {/* Grid */}
        {filtered.length === 0 ? (
          <div className="text-center py-20 text-text-secondary dark:text-dark-text-secondary">
            <p className="text-lg font-medium mb-2">No programs found</p>
            <p className="text-sm">Try adjusting your filters or search term.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((program, i) => (
              <motion.div
                key={program.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: i * 0.04 }}
              >
                <ProgramCard program={program} featured={program.featured} />
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FilterGroup({ label, options, value, onChange }: {
  label: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-xs text-text-secondary dark:text-dark-text-secondary font-medium">{label}:</span>
      {options.map((opt) => (
        <button
          key={opt}
          onClick={() => onChange(opt)}
          className={cn(
            "text-xs px-3 py-1.5 rounded-full border transition-colors cursor-pointer",
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
