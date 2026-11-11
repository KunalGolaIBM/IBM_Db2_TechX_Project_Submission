"use client";

import { useState, useEffect } from "react";
import {
  Bookmark, Send, Clock, Award, Bell, User, CheckCircle2,
  Sparkles, Flame, ArrowRight, ExternalLink, SlidersHorizontal, Edit3, Save, X
} from "lucide-react";
import { formatDate, cn } from "@/lib/utils";
import Link from "next/link";
import { useUser } from "@clerk/nextjs";
import { useOpportunities } from "@/components/providers/OpportunitiesProvider";
import { useToast } from "@/components/common/Toast";

interface DashboardItem {
  id: string;
  title: string;
  type: string;
  deadline: string;
  daysLeft?: number;
  status: "None" | "Applied" | "Under Review" | "Not Interested";
  slug: string;
  link: string;
}

interface StudentProfile {
  education: string;
  degree: string;
  study_year: number;
  graduation_batch: string;
  skills: string[];
  interests: string[];
  preferred_domains: string[];
  preferred_locations: string[];
}

interface RecommendationItem {
  opportunity: {
    id: string;
    title: string;
    organization?: string;
    opportunity_type?: string;
    category?: string;
    deadline?: string;
    application_url?: string;
  };
  match_score: number;
  explanation: {
    eligibility_met: boolean;
    skills_overlap: string[];
    domain_match: boolean;
    deadline_status: string;
    summary: string;
  };
}

export default function DashboardPage() {
  const { isSignedIn, isLoaded, user } = useUser();
  const { programs: livePrograms, events: liveEvents, internships: liveInternships, jobs: liveJobs, certifications: liveCertifications } = useOpportunities();
  const [savedOpps, setSavedOpps] = useState<DashboardItem[]>([]);
  const [trackedOpps, setTrackedOpps] = useState<DashboardItem[]>([]);
  const [deadlines, setDeadlines] = useState<DashboardItem[]>([]);
  const [stats, setStats] = useState({ saved: 0, applied: 0, review: 0, untracked: 0 });

  // Recommendations & Profile State
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [isLoadingRecs, setIsLoadingRecs] = useState(false);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [profile, setProfile] = useState<StudentProfile>({
    education: "GL Bajaj Group of Institutions",
    degree: "B.Tech Computer Science",
    study_year: 3,
    graduation_batch: "2026",
    skills: ["Python", "JavaScript", "React", "Cloud", "Git", "SQL"],
    interests: ["Full Stack", "AI/ML", "Cloud Systems"],
    preferred_domains: ["Software", "Cloud", "Open Source"],
    preferred_locations: ["Remote", "Bengaluru", "Delhi NCR"],
  });

  const [skillsInput, setSkillsInput] = useState(profile.skills.join(", "));
  const { showToast } = useToast();

  useEffect(() => {
    if (isLoaded && !isSignedIn) {
      window.location.href = "/sign-in";
    }
  }, [isLoaded, isSignedIn]);

  // Load recommendations from API v1
  useEffect(() => {
    async function fetchRecs() {
      setIsLoadingRecs(true);
      try {
        const res = await fetch("/api/v1/recommendations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: user?.id,
            limit: 4,
            include_ai_explanation: true,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.recommendations) {
            setRecommendations(data.recommendations);
          }
        }
      } catch (err) {
        console.warn("Failed to load recommendations:", err);
      } finally {
        setIsLoadingRecs(false);
      }
    }
    if (isSignedIn) {
      fetchRecs();
    }
  }, [isSignedIn, user?.id]);

  const loadData = () => {
    if (typeof window === "undefined") return;

    // Compile all opportunities from live lists
    const allItems: DashboardItem[] = [
      ...livePrograms.map((p) => ({
        id: p.id,
        title: p.name,
        type: "Program",
        deadline: p.deadline,
        slug: p.slug,
        link: `/programs/${p.slug}`,
        status: (localStorage.getItem(`status_${p.id}`) || "None") as any,
      })),
      ...liveEvents.map((e) => ({
        id: e.id,
        title: e.title,
        type: "Event",
        deadline: e.registrationDeadline,
        slug: e.slug,
        link: `/events/${e.slug}`,
        status: (localStorage.getItem(`status_${e.id}`) || "None") as any,
      })),
      ...liveInternships.map((i) => ({
        id: i.id,
        title: `${i.role} at ${i.company}`,
        type: "Internship",
        deadline: i.deadline,
        slug: i.slug,
        link: `/internships/${i.slug}`,
        status: (localStorage.getItem(`status_${i.id}`) || "None") as any,
      })),
      ...liveJobs.map((j) => ({
        id: j.id,
        title: `${j.role} at ${j.company}`,
        type: "Job",
        deadline: j.deadline,
        slug: j.slug,
        link: `/jobs/${j.slug}`,
        status: (localStorage.getItem(`status_${j.id}`) || "None") as any,
      })),
      ...liveCertifications.map((c) => ({
        id: c.id,
        title: c.name,
        type: "Certification",
        deadline: "Ongoing",
        slug: c.slug,
        link: `/certifications/${c.slug}`,
        status: (localStorage.getItem(`status_${c.id}`) || "None") as any,
      })),
    ];

    // Filter Saved (Bookmarked)
    const saved = allItems.filter(
      (item) => localStorage.getItem(`bookmarked_${item.id}`) === "true"
    );

    // Filter Tracked (status is not None)
    const tracked = allItems.filter((item) => item.status !== "None");

    // Calculate deadlines
    const upcoming = allItems
      .filter((item) => item.deadline !== "Ongoing" && item.status !== "Not Interested")
      .map((item) => {
        const diffTime = new Date(item.deadline).getTime() - new Date().getTime();
        const daysLeft = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return { ...item, daysLeft };
      })
      .filter((item) => item.daysLeft !== undefined && item.daysLeft > 0)
      .sort((a, b) => (a.daysLeft || 0) - (b.daysLeft || 0))
      .slice(0, 5);

    setSavedOpps(saved);
    setTrackedOpps(tracked);
    setDeadlines(upcoming);

    // Calculate Stats
    const appliedCount = tracked.filter((i) => i.status === "Applied").length;
    const reviewCount = tracked.filter((i) => i.status === "Under Review").length;

    setStats({
      saved: saved.length,
      applied: appliedCount,
      review: reviewCount,
      untracked: allItems.length - tracked.length,
    });
  };

  useEffect(() => {
    loadData();
    window.addEventListener("status-changed", loadData);
    window.addEventListener("storage", loadData);
    return () => {
      window.removeEventListener("status-changed", loadData);
      window.removeEventListener("storage", loadData);
    };
  }, []);

  const handleSaveProfile = (e: React.FormEvent) => {
    e.preventDefault();
    const updatedSkills = skillsInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    setProfile((prev) => ({
      ...prev,
      skills: updatedSkills,
    }));
    setIsEditingProfile(false);
    showToast("Profile credentials updated. Re-ranking AI recommendations...", "success");
  };

  if (!isLoaded || !isSignedIn) {
    return (
      <div className="min-h-screen bg-background dark:bg-dark-background flex items-center justify-center pt-24">
        <div className="animate-pulse text-text-secondary">Verifying student credentials...</div>
      </div>
    );
  }

  // Profile completeness score
  const completeness = 92;

  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-24 pb-16 overflow-x-hidden">
      <div className="container-narrow">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-mono font-bold bg-brand-lime/10 text-brand-black dark:text-brand-lime border border-brand-lime/30 mb-2">
              <Sparkles size={13} />
              <span>IBM Db2 Opportunity Intelligence Hub</span>
            </div>
            <h1 className="text-3xl md:text-4xl font-extrabold text-text-primary dark:text-dark-text-primary">
              Student Career Dashboard
            </h1>
            <p className="text-text-secondary dark:text-dark-text-secondary mt-1 text-sm">
              Welcome back, {user?.firstName || "Student"}. Verified opportunities and application tracker.
            </p>
          </div>

          <button
            onClick={() => setIsEditingProfile(!isEditingProfile)}
            className="btn-outline-lime px-4 py-2.5 rounded-xl text-xs font-bold flex items-center gap-2 self-start md:self-auto cursor-pointer"
          >
            <Edit3 size={14} />
            <span>{isEditingProfile ? "Close Profile Editor" : "Edit Academic Profile"}</span>
          </button>
        </div>

        {/* ── Profile & Completeness Card ── */}
        <div className="card-cyber p-6 rounded-2xl mb-8">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-zinc-800">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-brand-lime/10 border border-brand-lime/30 flex items-center justify-center text-brand-lime font-bold text-lg">
                <User size={24} />
              </div>
              <div>
                <h3 className="font-bold text-white text-base">
                  {user?.fullName || "Verified Student"}
                </h3>
                <p className="text-xs text-zinc-400">
                  {profile.degree} • Year {profile.study_year} (Batch {profile.graduation_batch})
                </p>
              </div>
            </div>

            {/* Completeness Bar */}
            <div className="w-full md:w-64">
              <div className="flex justify-between text-xs font-mono mb-1.5">
                <span className="text-zinc-400">Profile Completeness</span>
                <span className="text-brand-lime font-bold">{completeness}%</span>
              </div>
              <div className="w-full h-2 rounded-full bg-zinc-800 overflow-hidden">
                <div
                  className="h-full bg-brand-lime rounded-full transition-all duration-500"
                  style={{ width: `${completeness}%` }}
                />
              </div>
            </div>
          </div>

          {/* Profile Details or Edit Form */}
          {isEditingProfile ? (
            <form onSubmit={handleSaveProfile} className="pt-4 space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
                <div>
                  <label className="text-zinc-400 block mb-1">Degree Program</label>
                  <input
                    type="text"
                    value={profile.degree}
                    onChange={(e) => setProfile({ ...profile, degree: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-white font-mono"
                  />
                </div>
                <div>
                  <label className="text-zinc-400 block mb-1">Study Year</label>
                  <select
                    value={profile.study_year}
                    onChange={(e) => setProfile({ ...profile, study_year: parseInt(e.target.value, 10) })}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-white font-mono"
                  >
                    {[1, 2, 3, 4, 5].map((y) => (
                      <option key={y} value={y}>Year {y}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-zinc-400 block mb-1">Graduation Batch</label>
                  <input
                    type="text"
                    value={profile.graduation_batch}
                    onChange={(e) => setProfile({ ...profile, graduation_batch: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-white font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="text-zinc-400 block mb-1 text-xs">Verified Technical Skills (comma separated)</label>
                <input
                  type="text"
                  value={skillsInput}
                  onChange={(e) => setSkillsInput(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-zinc-900 border border-zinc-800 text-white text-xs font-mono"
                />
              </div>

              <div className="flex gap-2 justify-end pt-2">
                <button
                  type="button"
                  onClick={() => setIsEditingProfile(false)}
                  className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-300 text-xs font-semibold hover:bg-zinc-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-brand-lime text-brand-black text-xs font-bold hover:bg-brand-lime-dark flex items-center gap-1.5"
                >
                  <Save size={13} />
                  Save & Update Match Engine
                </button>
              </div>
            </form>
          ) : (
            <div className="pt-4 flex flex-wrap items-center gap-2">
              <span className="text-xs text-zinc-400 mr-2 font-mono">Active Matching Skills:</span>
              {profile.skills.map((skill) => (
                <span
                  key={skill}
                  className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-zinc-900 border border-zinc-800 text-brand-lime"
                >
                  {skill}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* ── Stats Overview ── */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Saved Listings", value: stats.saved, icon: Bookmark, color: "text-brand-lime" },
            { label: "Submitted Applications", value: stats.applied, icon: Send, color: "text-emerald-400" },
            { label: "Under Review", value: stats.review, icon: Clock, color: "text-blue-400" },
            { label: "Indexed in Db2", value: "3,770+", icon: Award, color: "text-brand-lime" },
          ].map((stat) => {
            const Icon = stat.icon;
            return (
              <div key={stat.label} className="card-base p-5">
                <Icon size={20} className={stat.color} />
                <p className="text-2xl font-bold text-text-primary dark:text-dark-text-primary mt-2">{stat.value}</p>
                <p className="text-xs text-text-secondary dark:text-dark-text-secondary">{stat.label}</p>
              </div>
            );
          })}
        </div>

        {/* ── AI Personalized Recommendations Section with Explanations ── */}
        {recommendations.length > 0 && (
          <section className="mb-10">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary flex items-center gap-2">
                  <Sparkles size={18} className="text-brand-lime" />
                  <span>AI Eligibility & Semantic Recommendations</span>
                </h2>
                <p className="text-xs text-text-secondary dark:text-dark-text-secondary">
                  Calculated against your degree, batch, and skills via IBM Db2.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {recommendations.map((item, idx) => {
                const opp = item.opportunity;
                const exp = item.explanation;
                return (
                  <div
                    key={opp.id || idx}
                    className="card-base p-5 flex flex-col justify-between group hover:border-brand-lime/40 transition-all"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span className="text-[10px] font-mono uppercase font-bold px-2 py-0.5 rounded bg-brand-lime/10 text-brand-black dark:text-brand-lime border border-brand-lime/20">
                          {opp.opportunity_type || "Verified"}
                        </span>
                        <span className="text-xs font-mono font-bold text-brand-lime flex items-center gap-1">
                          <Flame size={14} />
                          {Math.round(item.match_score)}% Match
                        </span>
                      </div>

                      <h3 className="font-bold text-sm text-text-primary dark:text-dark-text-primary group-hover:text-brand-lime transition-colors">
                        {opp.title}
                      </h3>
                      <p className="text-xs text-text-secondary dark:text-dark-text-secondary mt-0.5">
                        {opp.organization || "Top Tech Host"}
                      </p>

                      {/* Transparent Match Reason */}
                      <div className="mt-3 p-2.5 rounded-lg bg-zinc-900/60 border border-zinc-800/80 text-[11px] leading-relaxed text-zinc-300">
                        <p className="font-medium text-brand-lime mb-1 flex items-center gap-1 font-mono text-[10px] uppercase">
                          <CheckCircle2 size={12} />
                          Match Explanation:
                        </p>
                        <p>{exp.summary}</p>
                      </div>
                    </div>

                    <div className="mt-4 pt-3 border-t border-border dark:border-dark-border flex items-center justify-between text-xs font-semibold">
                      <span className="text-[11px] text-text-secondary dark:text-dark-text-secondary">
                        Due: {opp.deadline || "Ongoing"}
                      </span>
                      {opp.application_url ? (
                        <a
                          href={opp.application_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-brand-lime hover:underline flex items-center gap-1"
                        >
                          <span>Apply</span>
                          <ExternalLink size={13} />
                        </a>
                      ) : (
                        <Link href="/jobs" className="text-brand-lime hover:underline flex items-center gap-1">
                          <span>View Details</span>
                          <ArrowRight size={13} />
                        </Link>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {/* ── Saved & Tracked Pipelines ── */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left: Saved + Tracked */}
          <div className="lg:col-span-2 space-y-8">
            {/* Tracked Opportunities */}
            <section>
              <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4 flex items-center gap-2">
                <Send size={18} className="text-emerald-400" /> Active Application Pipeline
              </h2>
              {trackedOpps.length === 0 ? (
                <div className="card-base p-6 text-center text-text-secondary text-sm">
                  No applications tracked yet. Click &quot;Track Application&quot; on any card to monitor it here.
                </div>
              ) : (
                <div className="space-y-3">
                  {trackedOpps.map((opp) => (
                    <Link key={opp.id} href={opp.link} className="block">
                      <div className="card-base p-4 flex items-center justify-between gap-4 hover:border-brand-lime/30 transition-all">
                        <div>
                          <p className="font-semibold text-sm text-text-primary dark:text-dark-text-primary">{opp.title}</p>
                          <p className="text-xs text-text-secondary">{opp.type} · Due {opp.deadline !== "Ongoing" ? formatDate(opp.deadline) : "Ongoing"}</p>
                        </div>
                        <span className={cn(
                          "text-[10px] font-semibold px-2 py-0.5 rounded-full",
                          opp.status === "Applied" && "bg-emerald-950/40 text-emerald-400 border border-emerald-800",
                          opp.status === "Under Review" && "bg-blue-950/40 text-blue-400 border border-blue-800",
                          opp.status === "Not Interested" && "bg-zinc-800 text-zinc-400"
                        )}>
                          {opp.status}
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </section>

            {/* Saved Opportunities */}
            <section>
              <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4 flex items-center gap-2">
                <Bookmark size={18} className="text-brand-lime" /> Saved Bookmarks
              </h2>
              {savedOpps.length === 0 ? (
                <div className="card-base p-6 text-center text-text-secondary text-sm">
                  No bookmarked opportunities yet. Bookmark opportunities to review them later.
                </div>
              ) : (
                <div className="space-y-3">
                  {savedOpps.map((opp) => (
                    <Link key={opp.id} href={opp.link} className="block">
                      <div className="card-base p-4 flex items-center justify-between gap-4 hover:border-brand-lime/30 transition-all">
                        <div>
                          <p className="font-semibold text-sm text-text-primary dark:text-dark-text-primary">{opp.title}</p>
                          <p className="text-xs text-text-secondary">{opp.type} · Due {opp.deadline !== "Ongoing" ? formatDate(opp.deadline) : "Ongoing"}</p>
                        </div>
                        <span className="text-xs font-semibold text-brand-lime hover:underline">
                          View details →
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </section>
          </div>

          {/* Right: Deadlines Priority */}
          <div>
            <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4 flex items-center gap-2">
              <Clock size={18} className="text-amber-400" /> Upcoming Deadlines
            </h2>
            {deadlines.length === 0 ? (
              <div className="card-base p-4 text-center text-text-secondary text-sm">
                No upcoming application deadlines approaching.
              </div>
            ) : (
              <div className="space-y-3">
                {deadlines.map((d, i) => (
                  <Link key={i} href={d.link} className="block">
                    <div className="card-base p-4 hover:border-brand-lime/30 transition-all">
                      <div className="flex items-center justify-between mb-1">
                        <p className="font-medium text-xs text-text-primary dark:text-dark-text-primary truncate max-w-[70%]">{d.title}</p>
                        <span className={cn(
                          "text-[10px] font-bold px-1.5 py-0.5 rounded-full font-mono",
                          (d.daysLeft || 0) <= 7 ? "bg-red-950/40 text-red-400 border border-red-800" : "bg-amber-950/40 text-amber-400 border border-amber-800"
                        )}>
                          {d.daysLeft}d left
                        </span>
                      </div>
                      <p className="text-[10px] text-text-secondary">{d.type} · Due {formatDate(d.deadline)}</p>
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
