"use client";

import Link from "next/link";
import { Home, Search, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-[#0B0B0C] flex items-center justify-center px-4 py-20 relative overflow-hidden">
      {/* Aurora BG */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 40% at 50% 0%, rgba(198,244,50,0.12) 0%, transparent 70%)",
        }}
      />
      {/* Cyber grid */}
      <div
        className="absolute inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage:
            "linear-gradient(rgba(198,244,50,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(198,244,50,0.06) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      <div className="relative z-10 text-center max-w-lg mx-auto">
        {/* Big 404 — pixel art style */}
        <div className="mb-6 relative inline-block">
          <span
            className="text-[9rem] sm:text-[12rem] font-black leading-none select-none"
            style={{
              color: "#C6F432",
              textShadow: "4px 4px 0 rgba(198,244,50,0.2), 0 0 60px rgba(198,244,50,0.3)",
              fontVariantNumeric: "tabular-nums",
              letterSpacing: "-0.04em",
            }}
          >
            404
          </span>
          {/* Glitch layer */}
          <span
            aria-hidden
            className="absolute inset-0 text-[9rem] sm:text-[12rem] font-black leading-none select-none"
            style={{
              color: "#ef4444",
              opacity: 0.3,
              transform: "translate(3px, 0)",
              clip: "rect(0, 900px, 30px, 0)",
              fontVariantNumeric: "tabular-nums",
              letterSpacing: "-0.04em",
            }}
          >
            404
          </span>
        </div>

        {/* SVG vector art — broken link */}
        <div className="mb-8 flex justify-center">
          <svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
            <circle cx="40" cy="40" r="38" stroke="#C6F432" strokeWidth="2" strokeDasharray="6 4" />
            <path d="M28 40 Q32 32 40 32 Q48 32 52 40" stroke="#C6F432" strokeWidth="2.5" strokeLinecap="round" fill="none" />
            <path d="M28 40 Q32 48 40 48 Q48 48 52 40" stroke="#272729" strokeWidth="2.5" strokeLinecap="round" fill="none" strokeDasharray="4 3" />
            <circle cx="40" cy="40" r="4" fill="#C6F432" />
            <line x1="58" y1="22" x2="66" y2="14" stroke="#C6F432" strokeWidth="2" strokeLinecap="round" />
            <line x1="62" y1="22" x2="58" y2="18" stroke="#C6F432" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>

        <h1 className="text-2xl sm:text-3xl font-bold text-white mb-3">
          Opportunity Not Found
        </h1>
        <p className="text-[#A0A09A] mb-8 text-base leading-relaxed">
          This page doesn&apos;t exist — but thousands of real student opportunities do.{" "}
          <span className="text-[#C6F432] font-medium">Let&apos;s get you back on track.</span>
        </p>

        {/* Quick links */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center mb-8">
          <Link
            href="/"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-full font-semibold text-sm text-[#0B0B0C] transition-all"
            style={{ background: "linear-gradient(135deg, #C6F432, #A8D620)", boxShadow: "0 0 20px rgba(198,244,50,0.3)" }}
          >
            <Home size={16} />
            Go Home
          </Link>
          <Link
            href="/jobs"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-full font-semibold text-sm text-[#C6F432] border border-[#C6F432]/40 hover:border-[#C6F432] hover:bg-[#C6F432]/10 transition-all"
          >
            <Search size={16} />
            Browse Jobs
          </Link>
          <Link
            href="javascript:history.back()"
            className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-full font-semibold text-sm text-white/60 border border-white/20 hover:border-white/40 hover:text-white transition-all"
          >
            <ArrowLeft size={16} />
            Go Back
          </Link>
        </div>

        {/* Quick categories */}
        <div className="flex flex-wrap justify-center gap-2">
          {[
            { label: "Programs", href: "/programs" },
            { label: "Events", href: "/events" },
            { label: "Internships", href: "/internships" },
            { label: "Certifications", href: "/certifications" },
          ].map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="px-3 py-1.5 rounded-full text-xs font-medium text-[#A0A09A] border border-[#272729] hover:border-[#C6F432]/40 hover:text-[#C6F432] transition-colors"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

