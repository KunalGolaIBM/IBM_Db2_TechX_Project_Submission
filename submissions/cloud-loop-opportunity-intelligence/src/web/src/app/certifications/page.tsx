"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { Search, Award, ShieldCheck, CheckCircle2 } from "lucide-react";
import { certifications, CertificationCard, Certification } from "@/features/certifications";
import { cn } from "@/lib/utils";

const providers = ["All", "MongoDB", "GeeksforGeeks", "Google", "Microsoft", "AWS", "IBM", "Meta"];
const difficulties = ["All", "Beginner", "Intermediate", "Advanced"];
const costs = ["All", "Free"];

export default function CertificationsPage() {
  const [search, setSearch] = useState("");
  const [provider, setProvider] = useState("All");
  const [difficulty, setDifficulty] = useState("All");
  const [cost, setCost] = useState("All");

  const filtered = useMemo(() => {
    return certifications.filter((c) => {
      const matchSearch =
        search === "" ||
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.provider.toLowerCase().includes(search.toLowerCase());
      const matchProv = provider === "All" || c.provider === provider;
      const matchDiff = difficulty === "All" || c.difficulty === difficulty;
      const matchCost = cost === "All" || c.cost === cost;
      return matchSearch && matchProv && matchDiff && matchCost;
    });
  }, [search, provider, difficulty, cost]);

  // Group certifications by company/provider
  const groupedByProvider = useMemo(() => {
    const groups: Record<string, Certification[]> = {};
    filtered.forEach((c) => {
      if (!groups[c.provider]) {
        groups[c.provider] = [];
      }
      groups[c.provider].push(c);
    });
    return groups;
  }, [filtered]);

  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-24 pb-16">
      <div className="container-narrow">
        
        {/* Header Section */}
        <div className="mb-10 flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
          <div>
            <span className="text-xs font-semibold uppercase tracking-widest text-primary mb-2 block">Certifications</span>
            <h1 className="text-4xl md:text-5xl font-bold text-text-primary dark:text-dark-text-primary mb-3">
              Free Verified Certifications
            </h1>
            <p className="text-text-secondary dark:text-dark-text-secondary max-w-xl">
              Google, Microsoft, AWS, IBM, Meta, and MongoDB. Learn for free and earn verified credentials to build your resume.
            </p>
          </div>
          <div className="shrink-0 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-bold shadow-sm">
            <ShieldCheck size={14} />
            <span>100% Free & Verified</span>
          </div>
        </div>

        {/* Filter controls */}
        <div className="mb-8 flex flex-col gap-4">
          <div className="relative">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-text-secondary" />
            <input 
              value={search} 
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search certifications, providers..."
              className="w-full pl-10 pr-4 py-3 rounded-xl border border-border dark:border-dark-border bg-white dark:bg-dark-card text-text-primary dark:text-dark-text-primary placeholder:text-text-secondary text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" 
            />
          </div>
          <div className="flex flex-wrap gap-4 items-center">
            <FilterGroup label="Provider" options={providers} value={provider} onChange={setProvider} />
            <FilterGroup label="Level" options={difficulties} value={difficulty} onChange={setDifficulty} />
            <FilterGroup label="Cost" options={costs} value={cost} onChange={setCost} />
          </div>
        </div>

        {/* Dynamic content rendering grouped by company */}
        <div className="space-y-12">
          {Object.keys(groupedByProvider).length === 0 ? (
            <div className="card-base p-12 text-center text-text-secondary dark:text-dark-text-secondary">
              No verified free certifications found matching your filters.
            </div>
          ) : (
            Object.entries(groupedByProvider).map(([providerName, certList], i) => (
              <motion.div 
                key={providerName}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
                className="card-base p-6 border border-border/80 dark:border-dark-border/80 bg-white/40 dark:bg-dark-card/40 backdrop-blur-sm shadow-md"
              >
                {/* Provider Section Title Bar */}
                <div className="flex items-center justify-between mb-6 pb-3 border-b border-border/60 dark:border-dark-border/60">
                  <div className="flex items-center gap-3">
                    {certList[0]?.providerLogo && (
                      <img 
                        src={certList[0].providerLogo} 
                        alt={providerName} 
                        className="w-8 h-8 rounded-lg object-contain bg-white dark:bg-neutral-800 p-1 border border-border/50" 
                      />
                    )}
                    <div>
                      <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
                        {providerName} Free Offerings
                      </h2>
                      <p className="text-[10px] text-text-secondary dark:text-dark-text-secondary font-medium uppercase tracking-wide">
                        Verified Credentials
                      </p>
                    </div>
                  </div>
                  <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-primary/10 text-primary border border-primary/15">
                    {certList.length} Certificate{certList.length !== 1 ? "s" : ""} Available
                  </span>
                </div>

                {/* Grid layout for Certificates of this provider */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                  {certList.map((cert) => (
                    <CertificationCard key={cert.id} cert={cert} />
                  ))}
                </div>
              </motion.div>
            ))
          )}
        </div>

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
