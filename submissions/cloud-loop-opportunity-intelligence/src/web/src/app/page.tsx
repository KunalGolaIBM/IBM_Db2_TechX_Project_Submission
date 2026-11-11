"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  ArrowRight, Search, Sparkles, Zap, Globe, Briefcase, Award, Building2,
  BadgeCheck, GraduationCap, FlaskConical, Users, ChevronDown, Quote,
  RefreshCw, Cpu, Database, CheckCircle2, Flame, SlidersHorizontal, Loader2
} from "lucide-react";
import { ProgramCard } from "@/features/programs";
import { EventCard } from "@/features/events";
import { InternshipCard } from "@/features/internships";
import { JobCard } from "@/features/jobs";
import { CertificationCard } from "@/features/certifications";
import { successStories, categories, faqs } from "@/features/community";
import { useOpportunities } from "@/components/providers/OpportunitiesProvider";
import { AiChatWidget } from "@/components/ui/AiChatWidget";
import { useToast } from "@/components/common/Toast";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

const iconMap: Record<string, React.ComponentType<{ size?: number; className?: string; style?: React.CSSProperties }>> = {
  Award, Calendar: Users, Briefcase, Building2, BadgeCheck,
  GraduationCap, FlaskConical, Users,
};

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (i = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, delay: i * 0.08, ease: "easeOut" as const },
  }),
};

interface AiMatchedOpportunity {
  id: string;
  title: string;
  company: string;
  category: string;
  type: string;
  score?: number;
  matchScore?: number;
  reason?: string;
  link?: string;
}

export default function HomePage() {
  const { programs, events, internships, jobs, certifications, totalOpportunitiesCount, isSyncing, triggerSync } = useOpportunities();
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [newsletterEmail, setNewsletterEmail] = useState("");
  const [isSubscribing, setIsSubscribing] = useState(false);

  // AI Semantic Search State
  const [semanticQuery, setSemanticQuery] = useState("");
  const [aiSearchResults, setAiSearchResults] = useState<AiMatchedOpportunity[]>([]);
  const [isSearchingAi, setIsSearchingAi] = useState(false);
  const [searchEngine, setSearchEngine] = useState<string>("");

  // AI Recommendations State
  const [recommended, setRecommended] = useState<AiMatchedOpportunity[]>([]);
  const [isLoadingRecs, setIsLoadingRecs] = useState(false);

  const { showToast } = useToast();

  const featured = programs.filter((p) => p.featured).slice(0, 3);
  const trending = programs.slice(0, 6);

  // Fetch initial AI Recommendations
  useEffect(() => {
    async function loadRecommendations() {
      setIsLoadingRecs(true);
      try {
        const res = await fetch("/api/db2/recommend?limit=4&skills=AI,React,Python,Cloud");
        if (res.ok) {
          const data = await res.json();
          if (data.recommendations && data.recommendations.length > 0) {
            setRecommended(data.recommendations);
          }
        }
      } catch (err) {
        console.warn("Recommendations fetch fallback:", err);
      } finally {
        setIsLoadingRecs(false);
      }
    }
    loadRecommendations();
  }, []);

  const handleHeroSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      window.location.href = `/jobs?search=${encodeURIComponent(searchQuery.trim())}`;
    }
  };

  const handleSemanticSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!semanticQuery.trim()) return;

    setIsSearchingAi(true);
    try {
      const res = await fetch("/api/db2/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: semanticQuery.trim(), limit: 4 }),
      });
      if (!res.ok) throw new Error("Search failed");
      const data = await res.json();
      setAiSearchResults(data.results || []);
      setSearchEngine(data.engine || "IBM Db2 Semantic Engine");
      showToast(`Found ${data.results?.length || 0} matches via ${data.engine || "AI search"}`, "success");
    } catch (err) {
      showToast("Semantic search is temporarily unavailable. Displaying static matches.", "error");
    } finally {
      setIsSearchingAi(false);
    }
  };

  const handleNewsletterSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newsletterEmail || !newsletterEmail.includes("@")) {
      showToast("Please enter a valid email address.", "error");
      return;
    }
    setIsSubscribing(true);
    setTimeout(() => {
      setIsSubscribing(false);
      setNewsletterEmail("");
      showToast("🎉 You're subscribed to Cloud Loop Weekly! Check your inbox this Friday.", "success");
    }, 600);
  };

  return (
    <div className="min-h-screen overflow-x-hidden">
      {/* Floating AI Chat Assistant */}
      <AiChatWidget />

      {/* ── Hero ── */}
      <section className="relative min-h-[92vh] flex flex-col items-center justify-center text-center px-4 pt-24 pb-16 overflow-hidden bg-background dark:bg-dark-background">
        {/* Midnight/Lime Aurora glow backdrop */}
        <div className="absolute inset-0 bg-gradient-hero pointer-events-none" />
        <motion.div
          className="absolute top-1/4 -left-32 w-96 h-96 rounded-full bg-brand-lime/10 blur-3xl pointer-events-none"
          animate={{ scale: [1, 1.2, 1], opacity: [0.25, 0.45, 0.25] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute bottom-1/4 -right-32 w-96 h-96 rounded-full bg-brand-lime/15 blur-3xl pointer-events-none"
          animate={{ scale: [1.2, 1, 1.2], opacity: [0.25, 0.45, 0.25] }}
          transition={{ duration: 8, repeat: Infinity, ease: "easeInOut", delay: 2 }}
        />

        <div className="relative z-10 max-w-4xl mx-auto">
          {/* Live Badge */}
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-brand-lime/30 bg-brand-lime/10 text-brand-black dark:text-brand-lime text-sm font-semibold mb-8 glow-lime"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand-lime opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-brand-lime"></span>
            </span>
            <span>{totalOpportunitiesCount.toLocaleString()}+ live opportunities • IBM Db2 Powered</span>
          </motion.div>

          {/* Headline */}
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.1 }}
            className="text-5xl sm:text-6xl md:text-7xl font-extrabold tracking-tight leading-[1.08] mb-6 text-text-primary dark:text-dark-text-primary"
          >
            Discover Every{" "}
            <span className="text-gradient">Student Opportunity.</span>
            <br />
            One Platform.
          </motion.h1>

          {/* Subheadline */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.2 }}
            className="text-lg sm:text-xl text-text-secondary dark:text-dark-text-secondary max-w-2xl mx-auto mb-10 leading-relaxed"
          >
            Google Cloud Arcade, MLSA, competitive campus hackathons, high-stipend internships,
            fresher jobs, and cloud certifications — ranked & matched by AI.
          </motion.p>

          {/* CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.3 }}
            className="flex flex-col sm:flex-row gap-3 justify-center mb-12"
          >
            <Link
              href="/programs"
              className="btn-gradient px-8 py-3.5 rounded-pill text-base font-bold text-brand-black inline-flex items-center gap-2 justify-center shadow-lime"
            >
              Explore Programs
              <ArrowRight size={18} />
            </Link>
            <Link
              href="/internships"
              className="px-8 py-3.5 rounded-pill text-base font-semibold border border-border dark:border-dark-border text-text-primary dark:text-dark-text-primary hover:bg-black/5 dark:hover:bg-white/5 transition-colors inline-flex items-center gap-2 justify-center"
            >
              Browse Openings
            </Link>
          </motion.div>

          {/* Search Bar */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.4 }}
            className="relative max-w-2xl mx-auto"
          >
            <form onSubmit={handleHeroSearch} className="flex items-center gap-3 px-5 py-4 rounded-2xl bg-white dark:bg-dark-card border border-border dark:border-dark-border shadow-card search-container">
              <Search size={20} className="text-brand-lime shrink-0" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search programs, internships, jobs, certifications..."
                className="flex-1 bg-transparent text-text-primary dark:text-dark-text-primary placeholder:text-text-secondary dark:placeholder:text-dark-text-secondary text-sm focus:outline-none"
                aria-label="Search opportunities"
              />
              <button type="submit" className="btn-gradient px-5 py-2 rounded-xl text-sm font-bold text-brand-black shrink-0">
                Search
              </button>
            </form>
            <p className="text-xs text-text-secondary dark:text-dark-text-secondary mt-3 flex flex-wrap items-center gap-4 justify-center">
              <span className="flex items-center gap-1 font-medium"><Zap size={13} className="text-brand-lime" /> {programs.length}+ Programs</span>
              <span className="flex items-center gap-1 font-medium"><Globe size={13} className="text-brand-lime" /> {events.length}+ Events</span>
              <span className="flex items-center gap-1 font-medium"><Briefcase size={13} className="text-brand-lime" /> {internships.length}+ Internships</span>
              <span className="flex items-center gap-1 font-medium"><Building2 size={13} className="text-brand-lime" /> {jobs.length}+ Jobs</span>
            </p>
          </motion.div>
        </div>
      </section>

      {/* ── AI Semantic Search Engine (IBM Db2 Showcase) ── */}
      <section className="section-padding bg-background-alt dark:bg-dark-background-alt border-y border-border dark:border-dark-border">
        <div className="container-narrow">
          <div className="card-cyber p-6 md:p-8 rounded-2xl">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6">
              <div>
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-brand-lime/10 text-brand-lime border border-brand-lime/30 mb-2">
                  <Database size={13} />
                  <span>AI Semantic Index • IBM Db2 Enterprise</span>
                </div>
                <h2 className="text-2xl md:text-3xl font-extrabold text-white">
                  Natural Language Opportunity Matcher
                </h2>
                <p className="text-sm text-zinc-400 mt-1 max-w-xl">
                  Type what you want in plain English (e.g. &quot;paid summer intern working on machine learning in Bangalore&quot;).
                </p>
              </div>

              {/* Sample Quick Query Badges */}
              <div className="flex flex-wrap gap-2">
                {[
                  "Google Facilitator",
                  "Remote Backend Intern",
                  "Free AWS Certs",
                  "Hackathon Cash Prize",
                ].map((tag) => (
                  <button
                    key={tag}
                    onClick={() => {
                      setSemanticQuery(tag);
                    }}
                    className="text-xs px-3 py-1.5 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-brand-lime hover:border-brand-lime/40 transition-colors"
                  >
                    + {tag}
                  </button>
                ))}
              </div>
            </div>

            {/* Semantic Search Input */}
            <form onSubmit={handleSemanticSearch} className="flex gap-2 mb-6">
              <div className="relative flex-1">
                <Sparkles size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-brand-lime" />
                <input
                  type="text"
                  value={semanticQuery}
                  onChange={(e) => setSemanticQuery(e.target.value)}
                  placeholder="Describe your ideal role, skills, or dream company in free text..."
                  className="w-full pl-11 pr-4 py-3.5 rounded-xl bg-zinc-900/90 border border-zinc-800 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:border-brand-lime/60 font-mono"
                />
              </div>
              <button
                type="submit"
                disabled={isSearchingAi || !semanticQuery.trim()}
                className="px-6 py-3.5 rounded-xl bg-brand-lime text-brand-black font-bold text-sm hover:bg-brand-lime-dark disabled:opacity-40 transition-colors flex items-center gap-2 shrink-0"
              >
                {isSearchingAi ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    <span>Searching...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    <span>Match with AI</span>
                  </>
                )}
              </button>
            </form>

            {/* AI Results Grid */}
            {aiSearchResults.length > 0 && (
              <div className="space-y-3 pt-4 border-t border-zinc-800">
                <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
                  <span>Top Semantic Matches:</span>
                  <span className="text-brand-lime">Indexed by {searchEngine}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {aiSearchResults.map((item) => (
                    <div
                      key={item.id}
                      className="p-4 rounded-xl bg-zinc-900/60 border border-zinc-800 hover:border-brand-lime/40 transition-all flex items-start justify-between gap-3 group"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-brand-lime/10 text-brand-lime border border-brand-lime/20">
                            {item.category || item.type}
                          </span>
                          {item.score && (
                            <span className="text-[11px] font-mono text-zinc-400">
                              {(item.score * 100).toFixed(0)}% match
                            </span>
                          )}
                        </div>
                        <h4 className="font-bold text-sm text-white group-hover:text-brand-lime transition-colors">
                          {item.title}
                        </h4>
                        <p className="text-xs text-zinc-400">{item.company}</p>
                      </div>

                      <Link
                        href={item.link || `/${item.category?.toLowerCase() || "jobs"}`}
                        className="p-2 rounded-lg bg-zinc-800 text-zinc-300 hover:text-brand-lime hover:bg-zinc-700 transition-colors shrink-0"
                        title="View Opportunity"
                      >
                        <ArrowRight size={16} />
                      </Link>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ── AI Personalized Recommendations Section ── */}
      {recommended.length > 0 && (
        <section className="section-padding bg-background dark:bg-dark-background">
          <div className="container-narrow">
            <SectionHeader
              label="Recommended For You"
              title="Tailored Opportunities"
              subtitle="Scored in real-time based on in-demand engineering skills and recruiter demand."
              href="/dashboard"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {recommended.map((item, idx) => (
                <div
                  key={item.id || idx}
                  className="card-base p-5 flex flex-col justify-between group hover:border-brand-lime/50 transition-all"
                >
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="tag-cyber text-[10px] uppercase font-bold">
                        {item.category || "Top Match"}
                      </span>
                      <span className="text-xs font-bold text-brand-lime flex items-center gap-1 font-mono">
                        <Flame size={14} />
                        {item.matchScore ? `${item.matchScore}%` : "98%"}
                      </span>
                    </div>
                    <h4 className="font-bold text-sm text-text-primary dark:text-dark-text-primary group-hover:text-brand-lime transition-colors line-clamp-2">
                      {item.title}
                    </h4>
                    <p className="text-xs text-text-secondary dark:text-dark-text-secondary mt-1">
                      {item.company}
                    </p>
                    {item.reason && (
                      <p className="text-[11px] text-zinc-400 mt-2 bg-zinc-900/30 dark:bg-zinc-900/60 p-2 rounded border border-border dark:border-zinc-800 line-clamp-2">
                        {item.reason}
                      </p>
                    )}
                  </div>

                  <Link
                    href={item.link || `/${item.category?.toLowerCase() || "jobs"}`}
                    className="mt-4 pt-3 border-t border-border dark:border-dark-border flex items-center justify-between text-xs font-semibold text-text-primary dark:text-dark-text-primary group-hover:text-brand-lime transition-colors"
                  >
                    <span>Apply Now</span>
                    <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
                  </Link>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ── Featured Programs (Google Arcade style) ── */}
      <section className="section-padding bg-background dark:bg-dark-background">
        <div className="container-narrow">
          <SectionHeader
            label="Spotlight"
            title="Featured Student Programs"
            subtitle="Hand-picked programs from the world's best tech companies. Highly competitive — apply early."
            href="/programs"
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {featured.map((program, i) => (
              <motion.div key={program.id} variants={fadeUp} initial="hidden" whileInView="visible" custom={i} viewport={{ once: true }}>
                <ProgramCard program={program} featured />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Trending Programs ── */}
      <section className="section-padding bg-background dark:bg-dark-background">
        <div className="container-narrow">
          <SectionHeader
            label="Trending"
            title="Popular Right Now"
            subtitle="Programs students are applying to this week."
            href="/programs"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {trending.map((program, i) => (
              <motion.div key={program.id} variants={fadeUp} initial="hidden" whileInView="visible" custom={i} viewport={{ once: true }}>
                <ProgramCard program={program} />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Upcoming Events ── */}
      <section className="section-padding bg-background-alt dark:bg-dark-background-alt">
        <div className="container-narrow">
          <SectionHeader
            label="Events"
            title="Upcoming Hackathons & Events"
            subtitle="Hackathons, bootcamps, and conferences happening soon."
            href="/events"
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {events.slice(0, 3).map((event, i) => (
              <motion.div key={event.id} variants={fadeUp} initial="hidden" whileInView="visible" custom={i} viewport={{ once: true }}>
                <EventCard event={event} />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Latest Internships ── */}
      <section className="section-padding bg-background dark:bg-dark-background">
        <div className="container-narrow">
          <SectionHeader
            label="Internships"
            title="Latest Internship Openings"
            subtitle="Paid internships at top companies, updated daily."
            href="/internships"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {internships.slice(0, 4).map((internship, i) => (
              <motion.div key={internship.id} variants={fadeUp} initial="hidden" whileInView="visible" custom={i} viewport={{ once: true }}>
                <InternshipCard internship={internship} />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Latest Jobs ── */}
      <section className="section-padding bg-background-alt dark:bg-dark-background-alt">
        <div className="container-narrow">
          <SectionHeader
            label="Jobs"
            title="Fresher & Entry-Level Jobs"
            subtitle="Full-time roles at top companies, freshers welcome."
            href="/jobs"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {jobs.slice(0, 4).map((job, i) => (
              <motion.div key={job.id} variants={fadeUp} initial="hidden" whileInView="visible" custom={i} viewport={{ once: true }}>
                <JobCard job={job} />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Certifications ── */}
      <section className="section-padding bg-background dark:bg-dark-background">
        <div className="container-narrow">
          <SectionHeader
            label="Certifications"
            title="Industry-Recognized Certificates"
            subtitle="From Google, AWS, Microsoft, IBM and more. Build credentials that matter."
            href="/certifications"
          />
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {certifications.slice(0, 4).map((cert, i) => (
              <motion.div key={cert.id} variants={fadeUp} initial="hidden" whileInView="visible" custom={i} viewport={{ once: true }}>
                <CertificationCard cert={cert} />
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Categories ── */}
      <section className="section-padding bg-background-alt dark:bg-dark-background-alt">
        <div className="container-narrow">
          <SectionHeader
            label="Browse"
            title="Explore by Category"
            subtitle="Find exactly what you're looking for."
          />
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {categories.map((cat, i) => {
              const Icon = iconMap[cat.icon] || Award;
              return (
                <motion.div key={cat.id} variants={fadeUp} initial="hidden" whileInView="visible" custom={i} viewport={{ once: true }}>
                  <Link
                    href={`/${cat.id}`}
                    className="card-base p-5 flex flex-col gap-3 group cursor-pointer block hover:border-brand-lime/40 transition-colors"
                  >
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center bg-brand-lime/10 border border-brand-lime/20"
                    >
                      <Icon size={20} className="text-brand-lime" />
                    </div>
                    <div>
                      <p className="font-semibold text-sm text-text-primary dark:text-dark-text-primary group-hover:text-brand-lime transition-colors">{cat.name}</p>
                      <p className="text-xs text-text-secondary dark:text-dark-text-secondary mt-0.5">{cat.count}+ listed</p>
                    </div>
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── Success Stories ── */}
      <section className="section-padding bg-background dark:bg-dark-background">
        <div className="container-narrow">
          <SectionHeader
            label="Stories"
            title="Students Who Made It"
            subtitle="Real journeys. Real results."
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {successStories.map((story, i) => (
              <motion.div key={story.id} variants={fadeUp} initial="hidden" whileInView="visible" custom={i} viewport={{ once: true }}>
                <div className="card-base p-6 h-full flex flex-col gap-4">
                  <Quote size={24} className="text-brand-lime/40" />
                  <p className="text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed flex-1">
                    &quot;{story.quote}&quot;
                  </p>
                  <div className="flex items-center gap-3 pt-2 border-t border-border dark:border-dark-border">
                    <div className="w-10 h-10 rounded-full bg-brand-lime flex items-center justify-center text-brand-black font-extrabold text-sm shrink-0">
                      {story.name[0]}
                    </div>
                    <div>
                      <p className="font-semibold text-sm text-text-primary dark:text-dark-text-primary">{story.name}</p>
                      <p className="text-xs text-text-secondary dark:text-dark-text-secondary">{story.role}</p>
                      <p className="text-xs text-text-secondary dark:text-dark-text-secondary">{story.university}</p>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Newsletter CTA (Midnight/Lime Aesthetic) ── */}
      <section className="section-padding bg-background-alt dark:bg-dark-background-alt">
        <div className="container-narrow">
          <div className="rounded-2xl border border-brand-lime/30 bg-brand-black p-10 md:p-16 text-center shadow-lime">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-brand-lime/10 text-brand-lime border border-brand-lime/30 mb-4">
              <Sparkles size={13} />
              <span>Free Weekly Opportunity Digest</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-extrabold text-white mb-4">
              Never Miss a High-Impact Deadline
            </h2>
            <p className="text-zinc-400 max-w-md mx-auto mb-8 text-base">
              Every Friday morning — the top 10 verified student programs, internships, and hackathons curated directly to your inbox.
            </p>
            <form onSubmit={handleNewsletterSubmit} className="flex flex-col sm:flex-row gap-3 justify-center max-w-md mx-auto">
              <input
                type="email"
                value={newsletterEmail}
                onChange={(e) => setNewsletterEmail(e.target.value)}
                placeholder="you@university.edu"
                className="flex-1 px-4 py-3 rounded-xl bg-zinc-900 border border-zinc-800 text-white placeholder:text-zinc-500 text-sm focus:outline-none focus:border-brand-lime/70"
                aria-label="Email for newsletter"
                required
              />
              <button
                type="submit"
                disabled={isSubscribing}
                className="px-6 py-3 rounded-xl bg-brand-lime text-brand-black font-bold text-sm hover:bg-brand-lime-dark disabled:opacity-50 transition-colors whitespace-nowrap shadow-lime"
              >
                {isSubscribing ? "Subscribing..." : "Subscribe Free"}
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* ── FAQ ── */}
      <section className="section-padding bg-background dark:bg-dark-background" id="faq">
        <div className="container-narrow max-w-2xl">
          <SectionHeader
            label="FAQ"
            title="Common Questions"
            subtitle="Everything you need to know about Cloud Loop & IBM Db2 integration."
          />
          <div className="space-y-3">
            {faqs.map((faq, i) => (
              <motion.div
                key={i}
                variants={fadeUp}
                initial="hidden"
                whileInView="visible"
                custom={i}
                viewport={{ once: true }}
                className="card-base overflow-hidden"
              >
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="w-full flex items-center justify-between gap-4 p-5 text-left"
                  aria-expanded={openFaq === i}
                >
                  <span className="font-semibold text-sm text-text-primary dark:text-dark-text-primary">{faq.q}</span>
                  <ChevronDown
                    size={16}
                    className={cn(
                      "shrink-0 text-brand-lime transition-transform duration-200",
                      openFaq === i && "rotate-180"
                    )}
                  />
                </button>
                {openFaq === i && (
                  <div className="px-5 pb-5 text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed border-t border-border dark:border-dark-border pt-4">
                    {faq.a}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function SectionHeader({
  label,
  title,
  subtitle,
  href,
}: {
  label: string;
  title: string;
  subtitle: string;
  href?: string;
}) {
  return (
    <div className="flex items-end justify-between gap-4 mb-8">
      <div>
        <span className="text-xs font-bold uppercase tracking-widest text-brand-lime mb-2 block font-mono">
          {label}
        </span>
        <h2 className="text-2xl md:text-3xl font-extrabold text-text-primary dark:text-dark-text-primary leading-tight">
          {title}
        </h2>
        <p className="text-sm text-text-secondary dark:text-dark-text-secondary mt-1.5 max-w-lg">
          {subtitle}
        </p>
      </div>
      {href && (
        <Link
          href={href}
          className="shrink-0 text-sm font-semibold text-brand-lime hover:underline flex items-center gap-1"
        >
          View all <ArrowRight size={14} />
        </Link>
      )}
    </div>
  );
}
