import type { Metadata } from "next";
import Link from "next/link";
import { siteConfig } from "@/config/site";

export const metadata: Metadata = {
  title: "About Cloud Loop",
  description: "Learn about Cloud Loop — built to help Indian students discover every opportunity from one place.",
};

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-28 pb-20">
      <div className="container-narrow max-w-3xl">
        {/* Editorial header */}
        <div className="mb-12 border-b-2 border-[#C6F432] pb-6">
          <span className="text-xs font-bold uppercase tracking-widest text-[#C6F432] mb-3 block">About</span>
          <h1 className="text-4xl md:text-5xl font-black text-text-primary dark:text-dark-text-primary leading-tight mb-4">
            Built for Students,<br />by a Student.
          </h1>
          <p className="text-lg text-text-secondary dark:text-dark-text-secondary leading-relaxed">
            Cloud Loop was born from a simple frustration — too many platforms, too little time.
          </p>
        </div>

        <div className="prose prose-lg max-w-none dark:prose-invert space-y-8">
          <section>
            <h2 className="text-2xl font-bold text-text-primary dark:text-dark-text-primary mb-3">The Problem</h2>
            <p className="text-text-secondary dark:text-dark-text-secondary leading-relaxed">
              As a student in India, finding opportunities meant checking Unstop, LinkedIn, Internshala, Google&apos;s website, Microsoft&apos;s page, GDG, MLH, and a dozen WhatsApp groups — every single day. 
              Most students miss out simply because the information is scattered everywhere.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-text-primary dark:text-dark-text-primary mb-3">The Solution</h2>
            <p className="text-text-secondary dark:text-dark-text-secondary leading-relaxed">
              Cloud Loop aggregates <strong className="text-[#C6F432]">programs, hackathons, internships, jobs, and certifications</strong> into a single,
              clean platform — updated daily through automated scraping. No more tab-switching. No more missed deadlines.
            </p>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-text-primary dark:text-dark-text-primary mb-3">The Stack</h2>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {["Next.js 16", "React 19", "TypeScript", "Tailwind CSS 4", "IBM Db2", "Clerk Auth", "Framer Motion", "LangChain"].map((tech) => (
                <div key={tech} className="px-4 py-2 rounded-lg border border-[#C6F432]/20 bg-[#C6F432]/05 text-sm font-medium text-text-primary dark:text-dark-text-primary text-center">
                  {tech}
                </div>
              ))}
            </div>
          </section>

          <section>
            <h2 className="text-2xl font-bold text-text-primary dark:text-dark-text-primary mb-3">Creator</h2>
            <p className="text-text-secondary dark:text-dark-text-secondary leading-relaxed">
              Built by <a href={siteConfig.socials.linkedin} target="_blank" rel="noopener noreferrer" className="text-[#C6F432] font-semibold hover:underline">Ayush Sharma</a> — a student developer from India.
              Cloud Loop is open-source and community-driven.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <a href={siteConfig.socials.github} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#C6F432]/40 text-[#C6F432] text-sm font-medium hover:bg-[#C6F432]/10 transition-colors">
                GitHub →
              </a>
              <a href={siteConfig.socials.linkedin} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-[#C6F432]/40 text-[#C6F432] text-sm font-medium hover:bg-[#C6F432]/10 transition-colors">
                LinkedIn →
              </a>
            </div>
          </section>
        </div>

        <div className="mt-12 pt-8 border-t border-border dark:border-dark-border">
          <Link href="/" className="text-sm text-[#C6F432] hover:underline">← Back to Cloud Loop</Link>
        </div>
      </div>
    </div>
  );
}

