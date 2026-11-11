"use client";

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from "react";
import { jobs as initialJobs, Job } from "@/features/jobs";
import { internships as initialInternships, Internship } from "@/features/internships";
import { events as initialEvents, Event } from "@/features/events";
import { programs as initialPrograms, Program } from "@/features/programs";
import { certifications as initialCertifications, Certification } from "@/features/certifications";

export interface ScraperStats {
  lastScraped?: string;
  totalScraped?: number;
  totalJobs?: number;
  totalInternships?: number;
  totalEvents?: number;
  totalPrograms?: number;
  uniqueCompaniesCount?: number;
  success?: boolean;
  sourceStats?: Record<string, any>;
}

interface OpportunitiesContextValue {
  jobs: Job[];
  internships: Internship[];
  events: Event[];
  programs: Program[];
  certifications: Certification[];
  stats: ScraperStats | null;
  isSyncing: boolean;
  lastSynced: Date | null;
  totalOpportunitiesCount: number;
  triggerSync: () => Promise<void>;
  getJobBySlug: (slug: string) => Job | undefined;
  getInternshipBySlug: (slug: string) => Internship | undefined;
  getEventBySlug: (slug: string) => Event | undefined;
  getProgramBySlug: (slug: string) => Program | undefined;
}

const OpportunitiesContext = createContext<OpportunitiesContextValue | null>(null);

export function OpportunitiesProvider({ children }: { children: React.ReactNode }) {
  const [jobs, setJobs] = useState<Job[]>(initialJobs);
  const [internships, setInternships] = useState<Internship[]>(initialInternships);
  const [events, setEvents] = useState<Event[]>(initialEvents);
  const [programs, setPrograms] = useState<Program[]>(initialPrograms);
  const [certifications] = useState<Certification[]>(initialCertifications);
  const [stats, setStats] = useState<ScraperStats | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastSynced, setLastSynced] = useState<Date | null>(null);

  // Helper to merge and deduplicate arrays by id & slug
  const mergeOpportunities = useCallback(<T extends { id: string; slug?: string }>(staticList: T[], dynamicList: T[]): T[] => {
    if (!dynamicList || dynamicList.length === 0) return staticList;
    const map = new Map<string, T>();
    // Add static items first
    for (const item of staticList) {
      map.set(item.id, item);
      if (item.slug) map.set(item.slug, item);
    }
    // Overlay dynamic/scraped items
    for (const item of dynamicList) {
      map.set(item.id, item);
      if (item.slug) map.set(item.slug, item);
    }
    return Array.from(new Set(map.values()));
  }, []);

  // Fetch dynamic scraped data from /api/scrape
  const fetchLiveFeed = useCallback(async (showLoading = false) => {
    if (showLoading) setIsSyncing(true);
    try {
      const res = await fetch("/api/scrape", { cache: "no-store" });
      if (!res.ok) throw new Error(`Scraper API returned ${res.status}`);
      const data = await res.json();

      if (data.scrapedJobs && data.scrapedJobs.length > 0) {
        setJobs((prev) => mergeOpportunities(prev, data.scrapedJobs));
      }
      if (data.scrapedInternships && data.scrapedInternships.length > 0) {
        setInternships((prev) => mergeOpportunities(prev, data.scrapedInternships));
      }
      if (data.scrapedEvents && data.scrapedEvents.length > 0) {
        setEvents((prev) => mergeOpportunities(prev, data.scrapedEvents));
      }
      if (data.scrapedPrograms && data.scrapedPrograms.length > 0) {
        setPrograms((prev) => mergeOpportunities(prev, data.scrapedPrograms));
      }
      if (data.stats) {
        setStats(data.stats);
      }
      setLastSynced(new Date());
    } catch (err) {
      console.warn("[OpportunitiesProvider] Live sync fallback to static state:", err);
    } finally {
      if (showLoading) setIsSyncing(false);
    }
  }, [mergeOpportunities]);

  // Initial fetch on mount + recurring background sync every 3 minutes
  useEffect(() => {
    fetchLiveFeed(false);

    const interval = setInterval(() => {
      // Only sync if document is visible
      if (document.visibilityState === "visible") {
        fetchLiveFeed(false);
      }
    }, 3 * 60 * 1000);

    return () => clearInterval(interval);
  }, [fetchLiveFeed]);

  // Manual sync trigger that calls POST /api/scrape and updates state immediately
  const triggerSync = useCallback(async () => {
    setIsSyncing(true);
    try {
      const res = await fetch("/api/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json();
      if (data.scrapedJobs && data.scrapedJobs.length > 0) {
        setJobs((prev) => mergeOpportunities(prev, data.scrapedJobs));
      }
      if (data.scrapedInternships && data.scrapedInternships.length > 0) {
        setInternships((prev) => mergeOpportunities(prev, data.scrapedInternships));
      }
      if (data.scrapedEvents && data.scrapedEvents.length > 0) {
        setEvents((prev) => mergeOpportunities(prev, data.scrapedEvents));
      }
      if (data.scrapedPrograms && data.scrapedPrograms.length > 0) {
        setPrograms((prev) => mergeOpportunities(prev, data.scrapedPrograms));
      }
      if (data.stats) {
        setStats(data.stats);
      }
      setLastSynced(new Date());
    } catch (error) {
      console.error("[OpportunitiesProvider] Trigger sync error:", error);
      // Fallback: re-fetch via GET
      await fetchLiveFeed(false);
    } finally {
      setIsSyncing(false);
    }
  }, [fetchLiveFeed, mergeOpportunities]);

  const totalOpportunitiesCount = useMemo(() => {
    return jobs.length + internships.length + events.length + programs.length + certifications.length;
  }, [jobs.length, internships.length, events.length, programs.length, certifications.length]);

  const getJobBySlug = useCallback((slug: string) => {
    return jobs.find((j) => j.slug === slug || j.id === slug);
  }, [jobs]);

  const getInternshipBySlug = useCallback((slug: string) => {
    return internships.find((i) => i.slug === slug || i.id === slug);
  }, [internships]);

  const getEventBySlug = useCallback((slug: string) => {
    return events.find((e) => e.slug === slug || e.id === slug);
  }, [events]);

  const getProgramBySlug = useCallback((slug: string) => {
    return programs.find((p) => p.slug === slug || p.id === slug);
  }, [programs]);

  const value = useMemo(() => ({
    jobs,
    internships,
    events,
    programs,
    certifications,
    stats,
    isSyncing,
    lastSynced,
    totalOpportunitiesCount,
    triggerSync,
    getJobBySlug,
    getInternshipBySlug,
    getEventBySlug,
    getProgramBySlug,
  }), [
    jobs,
    internships,
    events,
    programs,
    certifications,
    stats,
    isSyncing,
    lastSynced,
    totalOpportunitiesCount,
    triggerSync,
    getJobBySlug,
    getInternshipBySlug,
    getEventBySlug,
    getProgramBySlug,
  ]);

  return (
    <OpportunitiesContext.Provider value={value}>
      {children}
    </OpportunitiesContext.Provider>
  );
}

export function useOpportunities() {
  const context = useContext(OpportunitiesContext);
  if (!context) {
    throw new Error("useOpportunities must be used within an OpportunitiesProvider");
  }
  return context;
}
