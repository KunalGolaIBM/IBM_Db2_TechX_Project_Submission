"use client";

import Link from "next/link";
import Image from "next/image";
import { useState, useEffect } from "react";
import { footerLinkSections } from "@/config/navigation";
import { siteConfig } from "@/config/site";

function getRelativeTimeString(isoString: string): string {
  try {
    const date = new Date(isoString);
    const diffMs = Date.now() - date.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch {
    return "";
  }
}

export function Footer() {
  const [lastUpdated, setLastUpdated] = useState("");
  const [email, setEmail] = useState("");
  const [subStatus, setSubStatus] = useState<"idle" | "success" | "error">("idle");

  useEffect(() => {
    fetch("/api/scrape")
      .then((r) => r.json())
      .then((data) => {
        if (data?.stats?.lastScraped) setLastUpdated(getRelativeTimeString(data.stats.lastScraped));
      })
      .catch(() => {
        setLastUpdated("recently updated");
      });
  }, []);

  const handleSubscribe = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !email.includes("@")) {
      setSubStatus("error");
      setTimeout(() => setSubStatus("idle"), 3000);
      return;
    }
    // In production: POST to newsletter API
    setSubStatus("success");
    setEmail("");
    setTimeout(() => setSubStatus("idle"), 4000);
  };

  return (
    <footer className="border-t border-border dark:border-dark-border bg-background-alt dark:bg-dark-card">
      <div className="container-narrow py-16">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10 lg:gap-8">
          {/* Brand */}
          <div className="lg:col-span-2">
            <Link href="/" className="flex items-center gap-2 mb-4 w-fit" aria-label="Cloud Loop home">
              <Image
                src="/cloud-loop-logo.jpg"
                alt="Cloud Loop logo"
                width={32}
                height={32}
                className="rounded-full object-cover"
              />
              <span className="font-bold text-lg tracking-tight text-text-primary dark:text-dark-text-primary">
                Cloud Loop
              </span>
            </Link>
            <p className="text-sm text-text-secondary dark:text-dark-text-secondary leading-relaxed mb-6 max-w-xs">
              The single place students go to discover every opportunity — programs, events, internships, jobs, and certifications.
            </p>

            {/* Newsletter form with success/error feedback */}
            <form onSubmit={handleSubscribe} noValidate>
              <div className="flex gap-2">
                <label htmlFor="footer-email" className="sr-only">Email for newsletter</label>
                <input
                  id="footer-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@email.com"
                  aria-label="Email for newsletter"
                  className="flex-1 px-3.5 py-2.5 rounded-xl border border-border dark:border-dark-border bg-background dark:bg-dark-background text-sm text-text-primary dark:text-dark-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-[#C6F432]/40"
                />
                <button
                  type="submit"
                  className="btn-gradient px-4 py-2.5 rounded-xl text-sm font-semibold whitespace-nowrap"
                  aria-label="Subscribe to newsletter"
                >
                  Subscribe
                </button>
              </div>
              {subStatus === "success" && (
                <p className="text-xs text-[#C6F432] mt-2 font-medium" role="status">
                  ✅ Subscribed! You&apos;ll get the weekly digest every Friday.
                </p>
              )}
              {subStatus === "error" && (
                <p className="text-xs text-red-500 mt-2 font-medium" role="alert">
                  ❌ Please enter a valid email address.
                </p>
              )}
              {subStatus === "idle" && (
                <p className="text-xs text-text-secondary dark:text-dark-text-secondary mt-2">
                  Weekly digest of the best student opportunities.
                </p>
              )}
            </form>
          </div>

          {/* Link sections — using navigation config (no dead links) */}
          {Object.entries(footerLinkSections).map(([section, links]) => (
            <div key={section}>
              <h3 className="font-semibold text-sm text-text-primary dark:text-dark-text-primary mb-4">
                {section}
              </h3>
              <ul className="space-y-3">
                {links.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="text-sm text-text-secondary dark:text-dark-text-secondary hover:text-[#C6F432] dark:hover:text-[#C6F432] transition-colors"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="mt-12 pt-6 border-t border-border dark:border-dark-border flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
            <p className="text-sm text-text-secondary dark:text-dark-text-secondary">
              © 2024–{new Date().getFullYear()} Cloud Loop. Built for students, by students.
            </p>
            {lastUpdated && (
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-[#C6F432]/10 text-[#C6F432]">
                <span className="w-1.5 h-1.5 rounded-full bg-[#C6F432] animate-pulse" />
                Updated {lastUpdated}
              </span>
            )}
          </div>

          {/* Social links */}
          <div className="flex items-center gap-3">
            <a
              href={siteConfig.socials.linkedin}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Cloud Loop on LinkedIn"
              className="p-2 rounded-lg text-text-secondary dark:text-dark-text-secondary hover:text-[#C6F432] dark:hover:text-[#C6F432] hover:bg-[#C6F432]/10 transition-colors"
            >
              <LinkedInIcon />
            </a>
            <a
              href={siteConfig.socials.telegram}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Cloud Loop Telegram channel"
              className="p-2 rounded-lg text-text-secondary dark:text-dark-text-secondary hover:text-[#C6F432] dark:hover:text-[#C6F432] hover:bg-[#C6F432]/10 transition-colors"
            >
              <TelegramIcon />
            </a>
            <a
              href={siteConfig.socials.whatsapp}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Cloud Loop WhatsApp channel"
              className="p-2 rounded-lg text-text-secondary dark:text-dark-text-secondary hover:text-[#C6F432] dark:hover:text-[#C6F432] hover:bg-[#C6F432]/10 transition-colors"
            >
              <WhatsAppIcon />
            </a>
          </div>
        </div>
      </div>
    </footer>
  );
}

function LinkedInIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  );
}
function TelegramIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  );
}
function WhatsAppIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z" />
    </svg>
  );
}
