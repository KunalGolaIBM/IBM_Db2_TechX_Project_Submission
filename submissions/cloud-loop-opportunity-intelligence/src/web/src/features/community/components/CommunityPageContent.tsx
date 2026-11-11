"use client";

import { useState } from "react";
import { MessageCircle, Send, Users, Trophy, ExternalLink, X } from "lucide-react";
import { cn } from "@/lib/utils";

const platforms = [
  {
    name: "LinkedIn",
    description: "Professional updates, alumni network, job referrals",
    icon: LinkedInIcon,
    members: "6,800+",
    href: "https://www.linkedin.com/in/ayushh-sharmaa/",
    color: "#0A66C2",
    bg: "bg-[#0A66C2]/10",
  },
  {
    name: "Telegram",
    description: "Bot-powered alerts for new opportunities",
    icon: Send,
    members: "15,600+",
    href: "https://t.me/cloudloopupdates",
    color: "#0088CC",
    bg: "bg-[#0088CC]/10",
  },
  {
    name: "WhatsApp",
    description: "Quick updates, deadline reminders, peer help",
    icon: MessageCircle,
    members: "8,200+",
    href: "https://chat.whatsapp.com/JlAx2MYkAfZLBoy4Jx9J7X",
    color: "#25D366",
    bg: "bg-[#25D366]/10",
  },
];

const leaderboard = [
  { rank: 1, name: "Arjun Sharma", points: 4820, badge: "🏆", university: "IIT Bombay" },
  { rank: 2, name: "Priya Nair", points: 4210, badge: "🥈", university: "NIT Trichy" },
  { rank: 3, name: "Karthik Menon", points: 3990, badge: "🥉", university: "BITS Pilani" },
  { rank: 4, name: "Divya Patel", points: 3440, badge: "⭐", university: "IIT Delhi" },
  { rank: 5, name: "Rahul Gupta", points: 3120, badge: "⭐", university: "VIT Vellore" },
];

export function CommunityPageContent() {
  const [showModal, setShowModal] = useState(false);

  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-24 pb-16">
      {/* Closed Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md p-6 bg-white dark:bg-[#0d1b3e] rounded-2xl shadow-xl text-center space-y-4 border border-border dark:border-white/10 animate-in fade-in zoom-in duration-200 relative">
            <button 
              onClick={() => setShowModal(false)}
              className="absolute top-4 right-4 p-1 rounded-lg text-text-secondary hover:text-text-primary hover:bg-black/5 dark:hover:bg-white/10 transition-colors"
            >
              <X size={16} />
            </button>
            <div className="w-12 h-12 rounded-full bg-amber-500/10 text-amber-500 flex items-center justify-center mx-auto text-xl font-bold">
              ⚠️
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-bold text-text-primary dark:text-dark-text-primary">
                Applications Closed
              </h3>
              <p className="text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed">
                We are not accepting applications as of now. The new cohort will start in the <strong>second week of August</strong>.
              </p>
            </div>
            <button
              onClick={() => setShowModal(false)}
              className="w-full px-5 py-2.5 rounded-xl bg-primary text-white font-semibold text-sm hover:bg-primary/95 transition-colors cursor-pointer"
            >
              Got it
            </button>
          </div>
        </div>
      )}

      <div className="container-narrow">
        {/* Header */}
        <div className="mb-12 text-center max-w-2xl mx-auto">
          <span className="text-xs font-semibold uppercase tracking-widest text-primary mb-3 block">Community</span>
          <h1 className="text-4xl md:text-5xl font-bold text-text-primary dark:text-dark-text-primary mb-4">
            Join 60,000+ Students
          </h1>
          <p className="text-text-secondary dark:text-dark-text-secondary text-lg">
            Connect, collaborate, and grow with the largest student opportunity community in India.
          </p>
        </div>

        {/* Platform Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-16">
          {platforms.map((platform) => {
            const Icon = platform.icon;
            return (
              <a
                key={platform.name}
                href={platform.href}
                target="_blank"
                rel="noopener noreferrer"
                className="card-base p-6 flex flex-col gap-4 group"
              >
                <div className="flex items-start justify-between">
                  <div className={`w-12 h-12 rounded-2xl ${platform.bg} flex items-center justify-center`}>
                    <Icon size={22} style={{ color: platform.color }} />
                  </div>
                  <ExternalLink size={14} className="text-text-secondary group-hover:text-text-primary transition-colors mt-1" />
                </div>
                <div>
                  <p className="font-semibold text-text-primary dark:text-dark-text-primary mb-1">{platform.name}</p>
                  <p className="text-sm text-text-secondary dark:text-dark-text-secondary">{platform.description}</p>
                </div>
                <div className="flex items-center gap-1.5 text-xs font-medium" style={{ color: platform.color }}>
                  <Users size={12} />
                  {platform.members} members
                </div>
              </a>
            );
          })}
        </div>

        {/* Leaderboard */}
        <div className="mb-16">
          <div className="flex items-center gap-3 mb-6">
            <Trophy size={20} className="text-amber-500" />
            <h2 className="text-2xl font-bold text-text-primary dark:text-dark-text-primary">Top Contributors</h2>
          </div>
          <div className="card-base overflow-hidden">
            {leaderboard.map((user, i) => (
              <div
                key={user.rank}
                className={`flex items-center gap-4 px-6 py-4 ${i < leaderboard.length - 1 ? "border-b border-border dark:border-dark-border" : ""}`}
              >
                <span className="text-2xl w-8 text-center">{user.badge}</span>
                <div className="w-9 h-9 rounded-full bg-gradient-brand flex items-center justify-center text-white font-bold text-sm shrink-0">
                  {user.name[0]}
                </div>
                <div className="flex-1">
                  <p className="font-semibold text-sm text-text-primary dark:text-dark-text-primary">{user.name}</p>
                  <p className="text-xs text-text-secondary dark:text-dark-text-secondary">{user.university}</p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-sm text-secondary dark:text-primary">{user.points.toLocaleString()}</p>
                  <p className="text-xs text-text-secondary">points</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* CTA */}
        <div className="rounded-2xl bg-gradient-brand p-px">
          <div className="rounded-2xl bg-[#0d1b3e] dark:bg-[#080f20] p-10 text-center">
            <h2 className="text-2xl font-bold text-white mb-3">Be a Cloud Loop Campus Ambassador</h2>
            <p className="text-white/70 mb-6 max-w-sm mx-auto text-sm">
              Represent Cloud Loop at your college. Host events, grow the community, earn points.
            </p>
            <button 
              onClick={() => setShowModal(true)}
              className="px-6 py-3 rounded-xl bg-white text-secondary font-semibold text-sm hover:bg-white/90 transition-colors cursor-pointer"
            >
              Apply to be an Ambassador
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function LinkedInIcon({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}
