"use client";

import { notFound } from "next/navigation";
import Image from "next/image";
import { programs, ProgramCard } from "@/features/programs";
import { formatDate, getStatusColor, getDifficultyColor, cn } from "@/lib/utils";
import {
  ExternalLink, Clock, Users, Calendar, CheckCircle2,
  Gift, Globe, Copy, Check, X,
  BookOpen, Zap, AlertCircle, ChevronRight,
  Smartphone, Tablet, Headphones, FileText, Shield, Sparkles, ArrowLeft, Star, ShoppingBag
} from "lucide-react";
import { ProviderLogo } from "@/components/ui/ProviderLogo";
import { useOpportunities } from "@/components/providers/OpportunitiesProvider";
import { useState, use } from "react";


// ─────────────────────────────────────────
// Google Cloud Arcade Custom Page
// ─────────────────────────────────────────

function ArcadeFacilitatorPage({ program }: { program: typeof programs[0] & { registrationForm?: string; facilitatorCode?: string } }) {
  const [copied, setCopied] = useState(false);
  const [showToast, setShowToast] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(program.facilitatorCode ?? "GCAF26-IN-MGG-3E2");
    setCopied(true);
    setShowToast(true);
    setTimeout(() => setCopied(false), 2000);
    setTimeout(() => setShowToast(false), 3000);
  };

  return (
    <div className="min-h-screen bg-background dark:bg-dark-background">
      {/* Toast Notification */}
      <div
        className={cn(
          "fixed top-20 right-4 z-50 transition-all duration-300",
          showToast ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-2 pointer-events-none"
        )}
      >
        <div className="flex items-center gap-2 bg-gray-900 dark:bg-white text-white dark:text-gray-900 px-4 py-3 rounded-xl shadow-xl text-sm font-medium">
          <Check size={15} className="text-emerald-400 dark:text-emerald-600" />
          Facilitator Code Copied Successfully.
        </div>
      </div>



      {/* ── HERO ── */}
      <div className="bg-gradient-to-br from-blue-950 via-indigo-950 to-purple-950 border-b border-white/10 pt-24 pb-14 px-4 relative overflow-hidden">
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {[2,3,4,2,3,4,2,3,4,2,3,4,2,3,4,2,3,4,2,3].map((size, i) => (
            <div
              key={i}
              className="absolute rounded-full opacity-20"
              style={{
                width: size + "px",
                height: size + "px",
                background: i % 3 === 0 ? "#4ade80" : i % 3 === 1 ? "#f472b6" : "#60a5fa",
                left: ((i * 53) % 100) + "%",
                top: ((i * 77) % 100) + "%",
              }}
            />
          ))}
        </div>
        <div className="container-narrow relative">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6 mb-8">
            <div className="shrink-0">
              <Image
                src="/arcade-logo.png"
                alt="Google Cloud Arcade Facilitator"
                width={100}
                height={100}
                className="rounded-full ring-4 ring-white/20 shadow-2xl"
              />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="text-xs font-bold px-3 py-1 rounded-full bg-red-500/20 text-red-300 border border-red-500/30 uppercase tracking-wide">
                  CLOSED
                </span>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  Beginner
                </span>
                <span className="text-xs px-2.5 py-1 rounded-full bg-white/10 text-white/70 border border-white/10">
                  Cloud
                </span>
              </div>
              <h1 className="text-3xl md:text-4xl font-black text-white leading-tight mb-1">
                Google Cloud Arcade Facilitator Program
              </h1>
              <p className="text-white/60 text-sm mt-1">by Google</p>
            </div>
          </div>

          <div className="flex flex-wrap gap-5 text-sm text-white/70 mb-8">
            <span className="flex items-center gap-2">
              <Calendar size={14} className="text-yellow-400" />
              13 July 2026 at 5:00 PM IST – 14 September 2026 at 11:59 PM IST
            </span>
            <span className="flex items-center gap-2">
              <Globe size={14} className="text-blue-400" />
              <a href="https://rsvp.withgoogle.com/events/arcade-facilitator/" target="_blank" rel="noopener noreferrer" className="hover:text-white underline underline-offset-2 transition-colors">
                Official Program Website
              </a>
            </span>
          </div>

          <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-5 py-3 mb-6 inline-flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-red-400" />
            <p className="text-red-300 text-sm font-medium">
              Registrations are now <span className="font-bold text-red-200">CLOSED!</span>
            </p>
          </div>

          <div className="flex flex-wrap gap-3 items-center">
            <button
              disabled
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-bold text-white bg-gray-500/50 cursor-not-allowed opacity-75"
            >
              Registration Closed <X size={14} />
            </button>
            <a
              href="https://tinyurl.com/Arcade-Progress-Report"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-400 hover:to-indigo-500 shadow-lg shadow-blue-500/30 transition-all duration-200 hover:scale-105"
            >
              View Progress Report <ExternalLink size={14} />
            </a>
          </div>

          <p className="text-white/40 text-xs mt-3">
            Registrations closed on 20 July 2026. The Progress Report is updated daily by 6:00 PM IST.
          </p>
        </div>
      </div>

      {/* ── CONTENT ── */}
      <div className="container-narrow py-12 space-y-6">

        {/* ── FACILITATOR CODE ── */}
        <div
          onClick={handleCopy}
          className="group cursor-pointer rounded-2xl border border-blue-500/30 hover:border-blue-400/60 bg-white dark:bg-dark-card overflow-hidden transition-all duration-200 hover:shadow-xl hover:shadow-blue-500/5"
        >
          <div className="flex items-center gap-3 px-6 py-4 border-b border-blue-200 dark:border-blue-500/30 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400">
            <span className="p-1.5 rounded-lg border border-blue-200 dark:border-blue-500/30"><Copy size={18} /></span>
            <h2 className="font-bold text-base">Facilitator Code</h2>
          </div>
          <div className="px-6 py-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <p className="text-sm text-text-secondary dark:text-dark-text-secondary">
                Click anywhere on this card to automatically copy the code.
              </p>
              <code className="block font-mono text-2xl font-black text-text-primary dark:text-dark-text-primary tracking-widest mt-1">
                GCAF26-IN-MGG-3E2
              </code>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); handleCopy(); }}
              className={cn(
                "inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold transition-all duration-200",
                copied
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                  : "bg-primary text-white border border-primary"
              )}
            >
              {copied ? <Check size={12} /> : <Copy size={12} />}
              {copied ? "Copied Successfully!" : "Copy Code"}
            </button>
          </div>
        </div>

        {/* ── WELCOME TO CLOUD LOOP ── */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6 md:p-8 space-y-6">
          <div>
            <h2 className="text-xl md:text-2xl font-black text-text-primary dark:text-dark-text-primary flex items-center gap-2">
              Welcome to Cloud Loop! ☁️
            </h2>
            <p className="text-sm text-text-secondary dark:text-dark-text-secondary mt-2 leading-relaxed">
              Cloud Loop is your one-stop community for everything related to Google Cloud Arcade.
              Whether you're a beginner or an experienced learner, you'll find all the resources, updates, and guidance needed to complete your Arcade journey successfully.
            </p>
          </div>
          <div className="border-t border-border dark:border-dark-border pt-6">
            <h3 className="font-bold text-sm text-text-primary dark:text-dark-text-primary mb-3">
              📌 What You'll Find Here
            </h3>
            <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm text-text-secondary dark:text-dark-text-secondary">
              {[
                { label: "📢 Official Arcade announcements" },
                { label: "🎮 Monthly Games updates" },
                { label: "🏅 Skill Badges" },
                { label: "📚 Guides & Resources" },
                { label: "📊 Progress Reports" },
                { label: "💡 Tips & Best Practices" },
                { label: "⏰ Important reminders & deadlines" },
              ].map((item, index) => (
                <li key={index} className="flex items-center gap-2">
                  <span className="text-xs">•</span>
                  {item.label}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* ── PROGRESS REPORT ── */}
        <ArcadeSection icon={<FileText size={18} />} title="Progress Report" accent="blue">
          <div className="space-y-4">
            <p className="text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed">
              Check your Google Cloud Arcade game progress and skill badge milestones. The Progress Report is updated daily by 6:00 PM IST.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <a
                href="https://tinyurl.com/Arcade-Progress-Report"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-400 hover:to-indigo-500 shadow-md shadow-blue-500/20 transition-all duration-200 hover:scale-105"
              >
                Open Progress Report <ExternalLink size={13} />
              </a>
              <span className="text-xs px-2.5 py-1.5 rounded-lg bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20 font-semibold animate-pulse">
                Updated daily by 6:00 PM IST
              </span>
            </div>
          </div>
        </ArcadeSection>

        {/* ── IMPORTANT RESOURCES ── */}
        <ArcadeSection icon={<Globe size={18} />} title="Important Resources" accent="purple">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {[
              {
                name: "📝 Subscription Form (Mandatory)",
                href: "https://forms.gle/2h6xCvY3sW29pw4p7",
                desc: "Fill this mandatory form to link your progress"
              },
              {
                name: "☁️ Arcade Website",
                href: "https://go.cloudskillsboost.google/arcade",
                desc: "Official Google Cloud Arcade portal"
              },
              {
                name: "🎮 Monthly Games",
                href: "https://tinyurl.com/Arcade-Monthly-Games",
                desc: "Access monthly games and trivia quests"
              },
              {
                name: "🏅 Skill Badges",
                href: "https://tinyurl.com/Arcade-Skill-Badges",
                desc: "Complete skill badges to earn points"
              },
              {
                name: "💳 Credits Guide",
                href: "https://tinyurl.com/759-Credits",
                desc: "Step-by-step guide to claim free credits"
              },
              {
                name: "📚 Master Sheet",
                href: "https://tinyurl.com/Arcade-Master-Sheet",
                desc: "All labs and badge solutions list"
              },
              {
                name: "📖 Kick-off Deck Guide",
                href: "https://tinyurl.com/Arcade-Guide-2026-C1",
                desc: "Official kick-off deck and guidelines"
              },
              {
                name: "📘 Ultimate Guide (A–Z)",
                href: "https://tinyurl.com/Ultimate-Guide-Arcade",
                desc: "Comprehensive A to Z guide for Arcade"
              },
              {
                name: "🗺️ Monthly Roadmap",
                href: "https://tinyurl.com/Arcade-Roadmap",
                desc: "Monthly milestone tracker and updates"
              },
              {
                name: "🏆 Prize Counter Guide",
                href: "https://tinyurl.com/Arcade-Prize-Counter-Guide",
                desc: "Check rewards and swag redemption details"
              },
              {
                name: "📧 Arcade Support",
                href: "mailto:arcade-facilitator@google.com",
                desc: "Contact official support team"
              },
              {
                name: "🌐 Cloud Loop Platform",
                href: "https://cloud-loop.vercel.app/",
                desc: "This platform homepage link"
              }
            ].map((resource) => (
              <a
                key={resource.name}
                href={resource.href}
                target="_blank"
                rel="noopener noreferrer"
                className="p-4 rounded-xl border border-border dark:border-dark-border bg-gray-50 dark:bg-dark-card hover:border-purple-300 dark:hover:border-purple-500/50 hover:shadow-md transition-all duration-200 group flex flex-col justify-between"
              >
                <div>
                  <h3 className="font-bold text-sm text-text-primary dark:text-dark-text-primary group-hover:text-purple-600 dark:group-hover:text-purple-400 transition-colors">
                    {resource.name}
                  </h3>
                  <p className="text-xs text-text-secondary dark:text-dark-text-secondary mt-1">
                    {resource.desc}
                  </p>
                </div>
                <div className="flex justify-end mt-3">
                  <ExternalLink size={12} className="text-text-secondary group-hover:text-text-primary dark:group-hover:text-dark-text-primary transition-colors" />
                </div>
              </a>
            ))}
          </div>
        </ArcadeSection>

        {/* ── ABOUT THE PROGRAM ── */}
        <ArcadeSection icon={<BookOpen size={18} />} title="About the Program" accent="purple">
          <div className="space-y-4 text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed">
            <p>
              The Google Cloud Arcade Facilitator Program is Google&apos;s official learning initiative designed for students who want to learn Google Cloud, Artificial Intelligence, Machine Learning, Data Analytics, Generative AI, and modern cloud technologies through hands-on learning.
            </p>
            <p>
              Participants complete Arcade Games, Skill Badges, Labs, and Quests while earning Arcade Points and milestone rewards. The program also provides free Google Cloud credits and access to an active learning community for guidance and support.
            </p>
            <div className="flex items-center gap-2 mt-2 px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 font-medium">
              <CheckCircle2 size={16} className="shrink-0" />
              The program is completely free to join.
            </div>
          </div>
        </ArcadeSection>

        {/* ── AFTER REGISTRATION ── */}
        <ArcadeSection icon={<CheckCircle2 size={18} />} title="After Registration" accent="emerald">
          <p className="text-sm text-text-secondary dark:text-dark-text-secondary mb-4">
            Within <span className="font-semibold text-text-primary dark:text-dark-text-primary">24–48 hours</span>, you&apos;ll receive an email titled:
          </p>
          <div className="bg-gray-950 dark:bg-black border border-emerald-500/30 rounded-xl p-4 mb-6 font-mono text-sm text-emerald-400 leading-relaxed font-bold">
            Congratulations, you&apos;re now enrolled in the Google Cloud Arcade Facilitator Program 2026
          </div>
          <ul className="space-y-3 mb-6">
            {[
              "Read the email carefully.",
              "Complete every required step.",
              "Claim your FREE 750 Google Cloud Credits.",
            ].map((item, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-text-secondary dark:text-dark-text-secondary">
                <CheckCircle2 size={16} className="text-emerald-500 shrink-0 mt-0.5" />
                {item}
              </li>
            ))}
          </ul>
          <a
            href="https://tinyurl.com/759-Credits"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 shadow-md shadow-emerald-500/20 transition-all duration-200 hover:scale-105"
          >
            Claim 750 Credits Guide <ExternalLink size={13} />
          </a>
        </ArcadeSection>

        {/* ── NOW YOU'RE READY ── */}
        <ArcadeSection icon={<Zap size={18} />} title="You're All Set!" accent="yellow">
          <p className="text-sm text-text-secondary dark:text-dark-text-secondary mb-5">
            After successfully claiming your Google Cloud Credits, start playing Google Cloud Arcade Games and complete Skill Badges to earn Arcade Points and milestone rewards.
          </p>
          <a
            href="https://go.cloudskillsboost.google/arcade"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-bold text-gray-900 bg-gradient-to-r from-yellow-400 to-amber-400 hover:from-yellow-300 hover:to-amber-300 shadow-lg shadow-yellow-500/20 transition-all duration-200 hover:scale-105"
          >
            🚀 Start Google Cloud Arcade <ExternalLink size={13} />
          </a>
        </ArcadeSection>

        {/* ── DAILY LAB LIMIT ── */}
        <ArcadeSection icon={<AlertCircle size={18} />} title="Daily Lab Limit" accent="orange">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-500/30 rounded-xl p-4 text-center hover:scale-[1.02] transition-transform duration-200">
              <div className="text-3xl font-black text-orange-600 dark:text-orange-400 mb-1">15 Labs</div>
              <div className="text-xs text-text-secondary dark:text-dark-text-secondary font-semibold">Maximum every 24 hours</div>
            </div>
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-500/30 rounded-xl p-4 text-center hover:scale-[1.02] transition-transform duration-200">
              <div className="text-3xl font-black text-blue-600 dark:text-blue-400 mb-1">2 Hours</div>
              <div className="text-xs text-text-secondary dark:text-dark-text-secondary font-semibold">One lab quota restores</div>
            </div>
            <div className="bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-500/30 rounded-xl p-4 text-center hover:scale-[1.02] transition-transform duration-200">
              <div className="text-3xl font-black text-purple-600 dark:text-purple-400 mb-1">24 Hours</div>
              <div className="text-xs text-text-secondary dark:text-dark-text-secondary font-semibold">Full window refresh cycle</div>
            </div>
          </div>
          <p className="text-sm text-text-secondary dark:text-dark-text-secondary mt-5 leading-relaxed">
            Maximum <span className="font-semibold text-text-primary dark:text-dark-text-primary">15 labs</span> every <span className="font-semibold text-text-primary dark:text-dark-text-primary">24 hours</span>. Every <span className="font-semibold text-text-primary dark:text-dark-text-primary">2 hours</span>, one lab quota is automatically restored. Once your daily lab limit is exhausted, continue completing Skill Badges until your lab quota resets.
          </p>
        </ArcadeSection>

        {/* ── SKILL BADGES ── */}
        <ArcadeSection icon={<Gift size={18} />} title="Skill Badges" accent="indigo">
          <p className="text-sm text-text-secondary dark:text-dark-text-secondary mb-5">
            There are approximately <span className="font-bold text-text-primary dark:text-dark-text-primary">104 Skill Badges</span> worth around <span className="font-bold text-text-primary dark:text-dark-text-primary">52 Arcade Points</span>.
          </p>
          <a
            href="https://tinyurl.com/Arcade-Skill-Badges"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-400 hover:to-purple-500 shadow-md shadow-indigo-500/20 transition-all duration-200 hover:scale-105"
          >
            Open Skill Badges Sheet <ExternalLink size={13} />
          </a>
        </ArcadeSection>

        {/* ── COMMUNITY ── */}
        <ArcadeSection icon={<Users size={18} />} title="Need Help?" accent="teal">
          <p className="text-sm text-text-secondary dark:text-dark-text-secondary mb-5">
            Join our official communities for announcements, guidance, doubt solving, discussions, updates, and support throughout the program.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              {
                name: "Cloud Loop WhatsApp Channel",
                href: "https://www.whatsapp.com/channel/0029VbAiEFzAe5VikdanX42e",
                icon: "💬",
                color: "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-500/30 hover:border-green-400/60",
                textColor: "text-green-700 dark:text-green-400",
                desc: "Official Channel updates"
              },
              {
                name: "Cloud Loop Telegram Channel",
                href: "https://t.me/cloudloopupdates",
                icon: "📢",
                color: "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-500/30 hover:border-blue-400/60",
                textColor: "text-blue-700 dark:text-blue-400",
                desc: "Announcements & Alerts"
              },
              {
                name: "Telegram Discussion Group",
                href: "https://t.me/cloudloopp",
                icon: "🗣️",
                color: "bg-sky-50 dark:bg-sky-900/20 border-sky-200 dark:border-sky-500/30 hover:border-sky-400/60",
                textColor: "text-sky-700 dark:text-sky-400",
                desc: "Guidance & Doubt Solving"
              },
              {
                name: "WhatsApp Community",
                href: "https://chat.whatsapp.com/BvkoxWY8KZd1m3xTpdp2WX",
                icon: "🤝",
                color: "bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-500/30 hover:border-emerald-400/60",
                textColor: "text-emerald-700 dark:text-emerald-400",
                desc: "Peer Support community"
              },
            ].map((community) => (
              <a
                key={community.name}
                href={community.href}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  "flex items-center gap-4 p-4 rounded-xl border transition-all duration-200 hover:scale-[1.02] hover:shadow-md group",
                  community.color
                )}
              >
                <div className="text-2xl shrink-0">{community.icon}</div>
                <div className="flex-1 min-w-0">
                  <p className={cn("font-bold text-sm", community.textColor)}>{community.name}</p>
                  <p className="text-xs text-text-secondary dark:text-dark-text-secondary">{community.desc}</p>
                </div>
                <ExternalLink size={14} className="shrink-0 text-text-secondary group-hover:text-text-primary dark:group-hover:text-dark-text-primary transition-colors" />
              </a>
            ))}
          </div>
        </ArcadeSection>

        {/* ── FACILITATORS ── */}
        <ArcadeSection icon={<Users size={18} />} title="Program Facilitators" accent="purple">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {[
              { name: "Ayush Sharma", linkedin: "https://www.linkedin.com/in/ayushh-sharmaa/", image: "/ayush-sharma.png" },
              { name: "Hitansh Sharma", linkedin: "https://www.linkedin.com/in/hitansh-sharma/", initial: "H" },
            ].map((facilitator) => (
              <div
                key={facilitator.name}
                className="flex flex-col items-center gap-4 p-6 rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card hover:border-purple-300 dark:hover:border-purple-500/50 hover:shadow-lg hover:shadow-purple-500/10 transition-all duration-200"
              >
                <div className="w-20 h-20 rounded-full overflow-hidden bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-3xl font-black shadow-lg relative">
                  {facilitator.image ? (
                    <Image
                      src={facilitator.image}
                      alt={facilitator.name}
                      fill
                      className="object-cover"
                    />
                  ) : (
                    facilitator.initial
                  )}
                </div>
                <div className="text-center">
                  <p className="font-bold text-text-primary dark:text-dark-text-primary text-base">{facilitator.name}</p>
                  <p className="text-xs text-text-secondary dark:text-dark-text-secondary mt-1">Google Cloud Arcade Facilitator</p>
                </div>
                <a
                  href={facilitator.linkedin}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold bg-[#0077b5]/10 hover:bg-[#0077b5]/20 text-[#0077b5] dark:text-[#4fa3d1] border border-[#0077b5]/20 hover:border-[#0077b5]/40 transition-all duration-200"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                  </svg>
                  LinkedIn
                </a>
              </div>
            ))}
          </div>
        </ArcadeSection>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Shared Section Wrapper for Arcade page
// ─────────────────────────────────────────

function ArcadeSection({
  title,
  icon,
  children,
  accent = "blue",
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  accent?: string;
}) {
  const accentMap: Record<string, string> = {
    blue: "text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-500/30",
    purple: "text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/20 border-purple-200 dark:border-purple-500/30",
    emerald: "text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 border-emerald-200 dark:border-emerald-500/30",
    yellow: "text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-500/30",
    orange: "text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-500/30",
    indigo: "text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/20 border-indigo-200 dark:border-indigo-500/30",
    teal: "text-teal-600 dark:text-teal-400 bg-teal-50 dark:bg-teal-900/20 border-teal-200 dark:border-teal-500/30",
  };
  return (
    <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card overflow-hidden">
      <div className={cn("flex items-center gap-3 px-6 py-4 border-b border-border dark:border-dark-border", accentMap[accent])}>
        <span className={cn("p-1.5 rounded-lg border", accentMap[accent])}>{icon}</span>
        <h2 className="font-bold text-base">{title}</h2>
      </div>
      <div className="px-6 py-5">{children}</div>
    </div>
  );
}

// ─────────────────────────────────────────
// Generic Program Detail Page
// ─────────────────────────────────────────

function GenericProgramPage({ program, related }: {
  program: typeof programs[0];
  related: typeof programs;
}) {
  const benefits = [
    program.keyBenefit,
    "Access to exclusive workshops and webinars",
    "Certificate of completion and digital badge",
    "Networking with professionals from top tech companies",
    "Priority consideration for internships and full-time roles",
  ];

  const eligibilityPoints = [
    program.eligibility,
    "Basic understanding of the relevant technology domain",
    "Commitment to complete the program requirements",
    "Active student enrollment at an accredited institution",
  ];

  let timeline: { label: string; date: string; done: boolean; description?: string }[] = [
    { label: "Applications Open", date: "Ongoing", done: true },
    { label: "Application Deadline", date: formatDate(program.deadline), done: false },
    { label: "Selection Announcement", date: "4–6 weeks after deadline", done: false },
    { label: "Program Start", date: "Rolling basis", done: false },
    { label: "Completion & Certificate", date: `After ${program.duration}`, done: false },
  ];

  if (program.slug === "girlscript-summer-of-code") {
    timeline = [
      {
        label: "Launch Event + Applications Open",
        date: "24th March 2026",
        description: "GSSoC 2026 kicks off live! Attend the launch event for a walkthrough of the program, track guide, and the Cloudinary bonus session.",
        done: true
      },
      {
        label: "Selections",
        date: "End of March / Early April 2026",
        description: "Applications are reviewed and participants are selected. Contributors, mentors, project admins, and ambassadors are confirmed for the program.",
        done: true
      },
      {
        label: "Onboarding and Kick-off",
        date: "April 2026",
        description: "Selected participants are onboarded. Projects go live, contributors pick their issues, mentors are assigned, and the building begins.",
        done: true
      },
      {
        label: "Contribution Period",
        date: "May to June 2026",
        description: "The main program period. Contributors work on projects, submit PRs, build agents, earn points, and climb the leaderboard.",
        done: true
      },
      {
        label: "Final Evaluations and Results",
        date: "June to July 2026",
        description: "All contributions are evaluated, leaderboards are finalized, and top contributors across both tracks are recognized and rewarded.",
        done: false
      }
    ];
  }

  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-20">
      <div className="bg-gradient-hero border-b border-border dark:border-dark-border py-14 px-4">
        <div className="container-narrow">
          <div className="flex items-start gap-5 mb-6">
            <ProviderLogo src={program.providerLogo} alt={program.provider} fallback={program.provider} size="lg" />
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className={cn("text-xs font-semibold px-2.5 py-1 rounded-full", getStatusColor(program.status))}>
                  {program.status.toUpperCase()}
                </span>
                <span className={cn("text-xs font-semibold px-2.5 py-1 rounded-full", getDifficultyColor(program.difficulty))}>
                  {program.difficulty}
                </span>
                <span className="text-xs px-2.5 py-1 rounded-full bg-gray-100 dark:bg-gray-800 text-text-secondary dark:text-dark-text-secondary">
                  {program.category}
                </span>
              </div>
              <h1 className="text-3xl md:text-4xl font-bold text-text-primary dark:text-dark-text-primary">{program.name}</h1>
              <p className="text-text-secondary dark:text-dark-text-secondary mt-1">by {program.provider}</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-6 text-sm text-text-secondary dark:text-dark-text-secondary mb-8">
            <span className="flex items-center gap-1.5"><Clock size={14} /> {program.duration}</span>
            <span className="flex items-center gap-1.5"><Calendar size={14} /> Deadline: {formatDate(program.deadline)}</span>
            {program.applicants && <span className="flex items-center gap-1.5"><Users size={14} /> {program.applicants.toLocaleString()}+ applicants</span>}
          </div>
          <div className="flex flex-wrap gap-3">
            <a href={program.website} target="_blank" rel="noopener noreferrer"
              className="btn-gradient px-6 py-3 rounded-pill text-sm font-semibold text-white inline-flex items-center gap-2">
              Apply on Official Website <ExternalLink size={15} />
            </a>
            <button className="px-6 py-3 rounded-pill text-sm font-semibold border border-border dark:border-dark-border text-text-primary dark:text-dark-text-primary hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
              Bookmark
            </button>
          </div>
        </div>
      </div>

      <div className="container-narrow py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
          <div className="lg:col-span-2 space-y-10">
            <GenericSection title="Overview">
              <p className="text-text-secondary dark:text-dark-text-secondary leading-relaxed">{program.description}</p>
            </GenericSection>
            <GenericSection title="Eligibility">
              <ul className="space-y-3">
                {eligibilityPoints.map((point, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm text-text-secondary dark:text-dark-text-secondary">
                    <CheckCircle2 size={16} className="text-emerald-500 shrink-0 mt-0.5" />
                    {point}
                  </li>
                ))}
              </ul>
            </GenericSection>
            <GenericSection title="What You Get">
              <ul className="space-y-3">
                {benefits.map((b, i) => (
                  <li key={i} className="flex items-start gap-3 text-sm text-text-secondary dark:text-dark-text-secondary">
                    <Gift size={15} className="text-secondary dark:text-primary shrink-0 mt-0.5" />
                    {b}
                  </li>
                ))}
              </ul>
            </GenericSection>
            <GenericSection title="Timeline">
              <div className="space-y-6">
                {timeline.map((item, i) => (
                  <div key={i} className="flex items-start gap-4">
                    <div className={cn("w-3.5 h-3.5 rounded-full mt-1 shrink-0 border-2",
                      item.done ? "bg-emerald-500 border-emerald-500" : "bg-transparent border-border dark:border-dark-border"
                    )} />
                    <div className="space-y-0.5">
                      <p className="text-sm font-bold text-text-primary dark:text-dark-text-primary">{item.label}</p>
                      <p className="text-xs text-secondary dark:text-primary font-semibold">{item.date}</p>
                      {item.description && (
                        <p className="text-xs text-text-secondary dark:text-dark-text-secondary mt-1.5 leading-relaxed max-w-2xl">
                          {item.description}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </GenericSection>
          </div>

          <div className="space-y-5">
            <div className="card-base p-5 space-y-4">
              <h3 className="font-semibold text-sm text-text-primary dark:text-dark-text-primary">Quick Info</h3>
              <div className="space-y-3 text-sm">
                <InfoRow label="Provider" value={program.provider} />
                <InfoRow label="Category" value={program.category} />
                <InfoRow label="Duration" value={program.duration} />
                <InfoRow label="Difficulty" value={program.difficulty} />
                <InfoRow label="Deadline" value={formatDate(program.deadline)} />
              </div>
            </div>
            <div className="card-base p-5">
              <h3 className="font-semibold text-sm text-text-primary dark:text-dark-text-primary mb-3">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {program.tags.map((tag) => (
                  <span key={tag} className="text-xs px-2.5 py-1 rounded-full bg-gray-100 dark:bg-gray-800 text-text-secondary dark:text-dark-text-secondary">
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            <div className="card-base p-5">
              <h3 className="font-semibold text-sm text-text-primary dark:text-dark-text-primary mb-3">Official Resources</h3>
              <a href={program.website} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 text-sm text-secondary dark:text-primary hover:underline">
                <Globe size={14} /> Official Website <ExternalLink size={12} />
              </a>
            </div>
          </div>
        </div>

        {related.length > 0 && (
          <div className="mt-14 pt-10 border-t border-border dark:border-dark-border">
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-6">Related Programs</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              {related.map((p) => <ProgramCard key={p.id} program={p} />)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function GenericSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4 pb-2 border-b border-border dark:border-dark-border">
        {title}
      </h2>
      {children}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-text-secondary dark:text-dark-text-secondary">{label}</span>
      <span className="font-medium text-text-primary dark:text-dark-text-primary">{value}</span>
    </div>
  );
}

function NaukriAmbassadorPage({ program }: { program: typeof programs[0] }) {
  return (
    <div className="min-h-screen bg-background dark:bg-dark-background">
      {/* Hero */}
      <div className="bg-gradient-to-br from-orange-950 via-slate-950 to-indigo-950 border-b border-white/10 pt-24 pb-14 px-4 relative overflow-hidden">
        <div className="container-narrow">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6 mb-8">
            <div className="shrink-0">
              <Image
                src="/naukri-logo.png"
                alt="Naukri Campus Logo"
                width={100}
                height={100}
                className="rounded-2xl ring-4 ring-white/20 shadow-2xl bg-white p-2"
              />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 uppercase tracking-wide">
                  OPEN
                </span>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-orange-500/20 text-orange-300 border border-orange-500/30">
                  Beginner
                </span>
                <span className="text-xs px-2.5 py-1 rounded-full bg-white/10 text-white/70 border border-white/10">
                  Campus Ambassador
                </span>
              </div>
              <h1 className="text-3xl md:text-4xl font-black text-white leading-tight mb-1">
                Naukri Campus
                <span className="block text-orange-400 font-mono">Ambassador Program</span>
              </h1>
              <p className="text-white/60 text-sm mt-1">by Naukri Campus</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-6 text-sm text-white/70 mb-8">
            <span className="flex items-center gap-2">
              <Globe size={14} className="text-orange-400" />
              <a href="https://www.naukri.com/campus/ambassador-program" target="_blank" rel="noopener noreferrer" className="hover:text-white underline underline-offset-2 transition-colors">
                Official Program Website
              </a>
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container-narrow py-12 space-y-8">
        {/* Description */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6">
          <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-4">About the Program</h2>
          <p className="text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed">
            The Naukri Campus Ambassador Program is designed for students who want to build leadership, marketing, communication, and community-building skills while earning exclusive rewards, certificates, merchandise, vouchers, and recognition from Naukri Campus.
          </p>
        </div>

        {/* How to Join */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6">
          <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-6">How to Join</h2>
          <div className="space-y-6">
            <div className="p-5 rounded-xl border border-border dark:border-dark-border bg-gray-50 dark:bg-dark-background">
              <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-primary/10 text-primary uppercase tracking-wide mb-3 inline-block">
                Step 1
              </span>
              <p className="text-sm text-text-primary dark:text-dark-text-primary font-semibold mb-4">
                Sign up for the Naukri Campus Contest using the referral link.
              </p>
              <a
                href="https://www.naukri.com/campus/contests/digiquezt-sharp-1-seo-and-sem-basics-contest-event-36479?action=enrol&referral=e36479-rUAOZYY-psap&uapp=801&utm_source=share_desktop&utm_medium=referral"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-primary hover:bg-primary/90 shadow-md transition-all duration-200"
              >
                Register Now <ExternalLink size={13} />
              </a>
            </div>

            <div className="p-5 rounded-xl border border-border dark:border-dark-border bg-gray-50 dark:bg-dark-background">
              <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-primary/10 text-primary uppercase tracking-wide mb-3 inline-block">
                Step 2
              </span>
              <p className="text-sm text-text-primary dark:text-dark-text-primary font-semibold mb-4">
                After registering, apply for the Naukri Campus Ambassador Program.
              </p>
              <a
                href="https://www.naukri.com/campus/ambassador-program"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-secondary dark:bg-primary dark:text-dark-background hover:bg-secondary/90 shadow-md transition-all duration-200"
              >
                Apply Now <ExternalLink size={13} />
              </a>
            </div>
          </div>
        </div>

        {/* Why Join? */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6">
          <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-6">Why Join?</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              "Build your professional network",
              "Gain leadership experience",
              "Improve communication and marketing skills",
              "Receive certificates and recognition",
              "Earn exclusive merchandise and vouchers",
              "Become part of the Naukri Campus student community"
            ].map((highlight, index) => (
              <div key={index} className="flex items-start gap-3 text-sm text-text-secondary dark:text-dark-text-secondary">
                <CheckCircle2 size={16} className="text-emerald-500 shrink-0 mt-0.5" />
                <span>{highlight}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Rewards & Benefits */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6">
          <h2 className="text-lg font-bold text-text-primary dark:text-dark-text-primary mb-6">Rewards & Benefits</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {[
              { name: "iPhone", icon: <Smartphone className="text-blue-500" /> },
              { name: "iPad", icon: <Tablet className="text-indigo-500" /> },
              { name: "AirPods", icon: <Headphones className="text-purple-500" /> },
              { name: "SAP Summer Squad Welcome Certificate", icon: <FileText className="text-teal-500" /> },
              { name: "SAP Summer Squad 50 Points Certificate", icon: <FileText className="text-emerald-500" /> },
              { name: "SAP Summer Squad 250 Points Certificate", icon: <FileText className="text-green-500" /> },
              { name: "Ambassador Certificate", icon: <Star className="text-amber-500" /> },
              { name: "Letter of Recommendation", icon: <FileText className="text-rose-500" /> },
              { name: "Amazon Voucher – ₹1,000", icon: <Gift className="text-orange-500" /> },
              { name: "Amazon Voucher – ₹1,500", icon: <Gift className="text-orange-600" /> },
              { name: "Amazon Voucher – ₹4,000", icon: <Gift className="text-red-500" /> },
              { name: "Amazon Voucher – Up to ₹25,000", icon: <Gift className="text-red-600" /> },
              { name: "NC Branded T-Shirt", icon: <ShoppingBag className="text-pink-500" /> },
              { name: "NC Branded Bag", icon: <ShoppingBag className="text-sky-500" /> },
              { name: "NC Merch Kit (Neck Pillow, Water Bottle)", icon: <Gift className="text-cyan-500" /> },
              { name: "Wireless Headphones", icon: <Headphones className="text-violet-500" /> }
            ].map((reward, index) => (
              <div 
                key={index}
                className="p-4 rounded-xl border border-border dark:border-dark-border bg-gray-50 dark:bg-dark-background flex flex-col items-center text-center gap-3 hover:scale-105 transition-transform duration-200"
              >
                <div className="w-10 h-10 rounded-full bg-white dark:bg-dark-card flex items-center justify-center shadow-sm">
                  {reward.icon}
                </div>
                <span className="text-xs font-bold text-text-primary dark:text-dark-text-primary leading-tight">
                  {reward.name}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// AWS Student Builder Campus Leaders Custom Page
// ─────────────────────────────────────────

function AWSSBCLPage({ program }: { program: typeof programs[0] }) {
  return (
    <div className="min-h-screen bg-background dark:bg-dark-background">
      {/* Hero */}
      <div className="bg-gradient-to-br from-orange-950 via-slate-950 to-indigo-950 border-b border-white/10 pt-24 pb-14 px-4 relative overflow-hidden">
        <div className="container-narrow">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6 mb-8">
            <div className="shrink-0 bg-white p-2 rounded-2xl ring-4 ring-white/20 shadow-2xl">
              <Image
                src={program.providerLogo || ""}
                alt="AWS Logo"
                width={100}
                height={100}
                className="object-contain w-[100px] h-[100px]"
              />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 uppercase tracking-wide">
                  OPEN
                </span>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-orange-500/20 text-orange-300 border border-orange-500/30">
                  Beginner
                </span>
                <span className="text-xs px-2.5 py-1 rounded-full bg-white/10 text-white/70 border border-white/10">
                  Ambassador
                </span>
              </div>
              <h1 className="text-3xl md:text-4xl font-black text-white leading-tight mb-1">
                AWS Student Builder
                <span className="block text-orange-400 font-mono">Campus Leaders (SBCL)</span>
              </h1>
              <p className="text-white/60 text-sm mt-1">by Amazon Web Services</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-6 text-sm text-white/70 mb-8">
            <span className="flex items-center gap-2">
              <Clock size={14} className="text-orange-400" />
              12 Weeks (8–10 hours per week)
            </span>
            <span className="flex items-center gap-2">
              <Globe size={14} className="text-orange-400" />
              Active in: USA, India, Brazil
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container-narrow py-12 space-y-8">
        {/* Description */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6 md:p-8 space-y-4">
          <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
            Overview
          </h2>
          <p className="text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed">
            AWS Student Builder Campus Leaders (SBCL) are paid, part-time student ambassadors who bring AWS Builder Center to life on their campuses. You'll drive awareness of cloud tools and resources, host events, create content, and inspire your peers to start building.
          </p>
          <p className="text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed">
            This program is run by Amazon Web Services in partnership with official recruitment and management partners including NEXT GEN TEAM, Plus 1 Communications, and Effect Sports.
          </p>
        </div>

        {/* What will you do */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6 md:p-8 space-y-4">
          <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
            What will you do as a Campus Leader?
          </h2>
          <ul className="space-y-3">
            {[
              "Share the value of AWS Builder Center to your peers and show them how to get started.",
              "Develop and share content that highlights AWS Builder Center tools and education.",
              "Host events on-campus that get people talking, like mini demos, tabling, class announcements, and anything that works for your campus."
            ].map((task, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-text-secondary dark:text-dark-text-secondary">
                <CheckCircle2 size={16} className="text-orange-500 shrink-0 mt-0.5" />
                {task}
              </li>
            ))}
          </ul>
        </div>

        {/* Benefits */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6 md:p-8 space-y-4">
          <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
            What’s in it for you?
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { title: "💵 You Get Paid", desc: "A paycheck for doing cool things and representing AWS on campus." },
              { title: "💻 Hands-on Experience", desc: "Gain practical experience with AWS cloud tools and technologies." },
              { title: "📈 Career Progression", desc: "Opportunity to reapply for future terms or lead AWS Student Builder Groups." },
              { title: "🎓 Ongoing Coaching", desc: "Receive professional development coaching and group training sessions." }
            ].map((benefit, i) => (
              <div key={i} className="p-4 rounded-xl border border-border dark:border-dark-border bg-gray-50 dark:bg-dark-background">
                <h3 className="font-bold text-sm text-text-primary dark:text-dark-text-primary flex items-center gap-2">
                  <Gift size={16} className="text-orange-500" />
                  {benefit.title}
                </h3>
                <p className="text-xs text-text-secondary dark:text-dark-text-secondary mt-1 leading-relaxed">
                  {benefit.desc}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Qualifications */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6 md:p-8 space-y-4">
          <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
            How can you qualify?
          </h2>
          <ul className="space-y-3">
            {[
              "You are a current college or university student (ages 18+) with at least one year remaining in your program.",
              "You're the person your friends come to when they want to know what's happening on campus -- you're proactive and comfortable talking to different people.",
              "You are involved in campus life, student organizations, or builder communities."
            ].map((qual, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-text-secondary dark:text-dark-text-secondary">
                <CheckCircle2 size={16} className="text-orange-500 shrink-0 mt-0.5" />
                {qual}
              </li>
            ))}
          </ul>
        </div>

        {/* Recruitment */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6 md:p-8 space-y-4">
          <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
            How does recruitment work?
          </h2>
          <div className="space-y-4 text-sm text-text-secondary dark:text-dark-text-secondary">
            <p>If you've been contacted about the SBCL program, here's what to expect:</p>
            <div className="space-y-3 pl-2 border-l-2 border-orange-500/30">
              <div>
                <p className="font-bold text-text-primary dark:text-dark-text-primary">1. Initial outreach</p>
                <p className="text-xs mt-0.5">You'll receive an email or message introducing the program and inviting you to learn more. (Note: Outreach may come from the NEXT GEN TEAM, Plus 1 Communications, or Effect Sports recruitment team on behalf of AWS).</p>
              </div>
              <div>
                <p className="font-bold text-text-primary dark:text-dark-text-primary">2. Program onboarding conversation</p>
                <p className="text-xs mt-0.5">A short video call where the recruitment team walks you through the program, answers questions, and gets to know you (a two-way conversation, not a formal interview).</p>
              </div>
              <div>
                <p className="font-bold text-text-primary dark:text-dark-text-primary">3. Offer and onboarding</p>
                <p className="text-xs mt-0.5">Selected students receive a formal offer and join a structured onboarding session before the program kicks off.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Application Section */}
        <div className="rounded-2xl border border-orange-500/30 hover:border-orange-500/50 bg-gradient-to-br from-orange-500/5 to-indigo-500/5 p-6 md:p-8 space-y-6">
          <div>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
              Sound like your thing?
            </h2>
            <p className="text-sm text-text-secondary dark:text-dark-text-secondary mt-1">
              Applications are rolling, and spots are limited per campus. Supported countries: USA 🇺🇸, India 🇮🇳, and Brazil 🇧🇷.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-5 rounded-xl border border-border dark:border-dark-border bg-white dark:bg-dark-card space-y-3">
              <h3 className="font-bold text-sm text-text-primary dark:text-dark-text-primary">
                📝 Path A: Referral Application (Recommended)
              </h3>
              <p className="text-xs text-text-secondary dark:text-dark-text-secondary leading-relaxed">
                If you have a referral code or want to apply via the official Cloud Loop facilitator referral program, fill out this direct application form.
              </p>
              <a
                href="https://forms.gle/2WbSMSpwX9nKUpoz6"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-400 hover:to-amber-500 shadow-md shadow-orange-500/20 transition-all duration-200 hover:scale-105"
              >
                Apply via Referral <ExternalLink size={13} />
              </a>
            </div>
            <div className="p-5 rounded-xl border border-border dark:border-dark-border bg-white dark:bg-dark-card space-y-3">
              <h3 className="font-bold text-sm text-text-primary dark:text-dark-text-primary">
                🌐 Path B: Non-Referral Application
              </h3>
              <p className="text-xs text-text-secondary dark:text-dark-text-secondary leading-relaxed">
                If you wish to apply directly through the official website without a facilitator referral, please apply through the official AWS portal only.
              </p>
              <a
                href="https://aws.amazon.com/developer/community/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold border border-border dark:border-dark-border text-text-primary dark:text-dark-text-primary hover:bg-black/5 dark:hover:bg-white/5 transition-all duration-200"
              >
                AWS Student Groups Portal <ExternalLink size={13} />
              </a>
            </div>
          </div>
          <div className="pt-4 border-t border-border dark:border-dark-border text-xs text-text-secondary dark:text-dark-text-secondary flex flex-wrap gap-4 justify-between items-center">
            <span>📧 Questions? Email the team at: <a href="mailto:StudentBuilders@amazon.com" className="font-bold hover:underline">StudentBuilders@amazon.com</a></span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// AWS Student Builder Group Leaders Custom Page
// ─────────────────────────────────────────

function AWSSBGLPage({ program }: { program: typeof programs[0] }) {
  return (
    <div className="min-h-screen bg-background dark:bg-dark-background">
      {/* Hero */}
      <div className="bg-gradient-to-br from-blue-950 via-slate-950 to-orange-950 border-b border-white/10 pt-24 pb-14 px-4 relative overflow-hidden">
        <div className="container-narrow">
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-6 mb-8">
            <div className="shrink-0 bg-white p-2 rounded-2xl ring-4 ring-white/20 shadow-2xl">
              <Image
                src={program.providerLogo || ""}
                alt="AWS Logo"
                width={100}
                height={100}
                className="object-contain w-[100px] h-[100px]"
              />
            </div>
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 uppercase tracking-wide">
                  OPEN
                </span>
                <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  Beginner
                </span>
                <span className="text-xs px-2.5 py-1 rounded-full bg-white/10 text-white/70 border border-white/10">
                  Ambassador
                </span>
              </div>
              <h1 className="text-3xl md:text-4xl font-black text-white leading-tight mb-1">
                AWS Student Builder
                <span className="block text-blue-400 font-mono">Group Leaders (SBGL)</span>
              </h1>
              <p className="text-white/60 text-sm mt-1">by Amazon Web Services</p>
            </div>
          </div>
          <div className="flex flex-wrap gap-6 text-sm text-white/70 mb-8">
            <span className="flex items-center gap-2">
              <Clock size={14} className="text-blue-400" />
              Flexible / Ongoing Commitment
            </span>
            <span className="flex items-center gap-2">
              <Globe size={14} className="text-blue-400" />
              Active in: USA, India, Brazil, and worldwide
            </span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="container-narrow py-12 space-y-8">
        {/* Description */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6 md:p-8 space-y-4">
          <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
            Overview
          </h2>
          <p className="text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed">
            AWS Student Builder Group Leaders (SBGL) are student leaders who establish, run, and grow official AWS Student Builder Groups on their university campuses. Leaders help fellow students learn cloud technologies, build projects, and prepare for careers in tech.
          </p>
          <p className="text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed">
            By leading a campus group, you represent AWS Developer Experience on your campus, coordinate with cloud advocates, and gain official support to run workshops, hackathons, and study sessions.
          </p>
        </div>

        {/* What will you do */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6 md:p-8 space-y-4">
          <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
            What will you do as a Group Leader?
          </h2>
          <ul className="space-y-3">
            {[
              "Launch and manage an official AWS Student Builder Group on your campus.",
              "Coordinate study jams, cloud certification prep groups, and hands-on lab sessions.",
              "Build a community of students who are passionate about learning cloud computing and AWS.",
              "Host speaker events, mini hackathons, and networking sessions for builders."
            ].map((task, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-text-secondary dark:text-dark-text-secondary">
                <CheckCircle2 size={16} className="text-blue-500 shrink-0 mt-0.5" />
                {task}
              </li>
            ))}
          </ul>
        </div>

        {/* Benefits */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6 md:p-8 space-y-4">
          <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
            What’s in it for you?
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { title: "🗣️ Leadership Experience", desc: "Build real community management, speaking, and leadership credentials." },
              { title: "☁️ AWS Credits & Support", desc: "Get AWS credits and official learning materials to support your group events." },
              { title: "🎁 Exclusive Swag", desc: "Receive official AWS student group merchandise and leader welcome kits." },
              { title: "💼 Professional Networking", desc: "Connect directly with AWS developer advocates, recruiters, and tech mentors." }
            ].map((benefit, i) => (
              <div key={i} className="p-4 rounded-xl border border-border dark:border-dark-border bg-gray-50 dark:bg-dark-background">
                <h3 className="font-bold text-sm text-text-primary dark:text-dark-text-primary flex items-center gap-2">
                  <Gift size={16} className="text-blue-500" />
                  {benefit.title}
                </h3>
                <p className="text-xs text-text-secondary dark:text-dark-text-secondary mt-1 leading-relaxed">
                  {benefit.desc}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Qualifications */}
        <div className="rounded-2xl border border-border dark:border-dark-border bg-white dark:bg-dark-card p-6 md:p-8 space-y-4">
          <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
            Who should apply?
          </h2>
          <ul className="space-y-3">
            {[
              "Enrolled university students who are passionate about cloud computing and open learning.",
              "Self-motivated students with strong communication and organizational skills.",
              "Students who enjoy building and nurturing technology communities on campus."
            ].map((qual, i) => (
              <li key={i} className="flex items-start gap-3 text-sm text-text-secondary dark:text-dark-text-secondary">
                <CheckCircle2 size={16} className="text-blue-500 shrink-0 mt-0.5" />
                {qual}
              </li>
            ))}
          </ul>
        </div>

        {/* Application Section */}
        <div className="rounded-2xl border border-blue-500/30 hover:border-blue-500/50 bg-gradient-to-br from-blue-500/5 to-indigo-500/5 p-6 md:p-8 space-y-6">
          <div>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary">
              Apply to lead on your campus
            </h2>
            <p className="text-sm text-text-secondary dark:text-dark-text-secondary mt-1">
              Applications are reviewed on a rolling basis. Set up your group and start connecting builders today!
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-5 rounded-xl border border-border dark:border-dark-border bg-white dark:bg-dark-card space-y-3">
              <h3 className="font-bold text-sm text-text-primary dark:text-dark-text-primary">
                📝 Path A: Referral Application (Recommended)
              </h3>
              <p className="text-xs text-text-secondary dark:text-dark-text-secondary leading-relaxed">
                If you have a referral code or want to apply via the official Cloud Loop facilitator referral program, fill out this direct application form.
              </p>
              <a
                href="https://forms.gle/39m9vHB8LHLtceoR9"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-400 hover:to-indigo-500 shadow-md shadow-blue-500/20 transition-all duration-200 hover:scale-105"
              >
                Apply via Referral <ExternalLink size={13} />
              </a>
            </div>
            <div className="p-5 rounded-xl border border-border dark:border-dark-border bg-white dark:bg-dark-card space-y-3">
              <h3 className="font-bold text-sm text-text-primary dark:text-dark-text-primary">
                🌐 Path B: Non-Referral Application
              </h3>
              <p className="text-xs text-text-secondary dark:text-dark-text-secondary leading-relaxed">
                If you wish to apply directly through the official website without a facilitator referral, please apply through the official AWS portal only.
              </p>
              <a
                href="https://aws.amazon.com/developer/community/"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold border border-border dark:border-dark-border text-text-primary dark:text-dark-text-primary hover:bg-black/5 dark:hover:bg-white/5 transition-all duration-200"
              >
                AWS Student Groups Portal <ExternalLink size={13} />
              </a>
            </div>
          </div>
          <div className="pt-4 border-t border-border dark:border-dark-border text-xs text-text-secondary dark:text-dark-text-secondary flex flex-wrap gap-4 justify-between items-center">
            <span>📧 Questions? Email the team at: <a href="mailto:StudentBuilders@amazon.com" className="font-bold hover:underline">StudentBuilders@amazon.com</a></span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────
// Route Entry Point
// ─────────────────────────────────────────

export default function ProgramDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { getProgramBySlug, programs: livePrograms } = useOpportunities();
  const program = getProgramBySlug(slug) || programs.find((p) => p.slug === slug || p.id === slug);
  if (!program) notFound();

  const related = (livePrograms.length > 0 ? livePrograms : programs)
    .filter((p) => p.id !== program.id && (p.provider === program.provider || p.category === program.category))
    .slice(0, 3);

  if (slug === "google-cloud-arcade") {
    return <ArcadeFacilitatorPage program={program as typeof program & { registrationForm?: string; facilitatorCode?: string }} />;
  }

  if (slug === "naukri-campus-ambassador-program") {
    return <NaukriAmbassadorPage program={program} />;
  }

  if (slug === "aws-student-builder-campus-leaders") {
    return <AWSSBCLPage program={program} />;
  }

  if (slug === "aws-student-builder-group-leaders") {
    return <AWSSBGLPage program={program} />;
  }

  return <GenericProgramPage program={program} related={related} />;
}


