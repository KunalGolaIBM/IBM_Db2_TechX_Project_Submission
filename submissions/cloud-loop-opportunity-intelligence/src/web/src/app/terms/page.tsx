import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service — Cloud Loop",
  description: "Terms of service for using Cloud Loop.",
};

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-28 pb-20">
      <div className="container-narrow max-w-3xl">
        <div className="mb-10 border-b-2 border-[#C6F432] pb-6">
          <span className="text-xs font-bold uppercase tracking-widest text-[#C6F432] mb-3 block">Legal</span>
          <h1 className="text-4xl font-black text-text-primary dark:text-dark-text-primary mb-2">Terms of Service</h1>
          <p className="text-text-secondary dark:text-dark-text-secondary text-sm">Last updated: {new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}</p>
        </div>

        <div className="space-y-8 text-text-secondary dark:text-dark-text-secondary leading-relaxed">
          <section>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-3">1. Acceptance</h2>
            <p>By using Cloud Loop, you agree to these terms. Cloud Loop is provided free of charge to students for personal, non-commercial use.</p>
          </section>
          <section>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-3">2. Use of the Service</h2>
            <p>Cloud Loop aggregates publicly available opportunity listings. We do not guarantee the accuracy, availability, or completeness of any listing. Always verify opportunities directly with the company or organiser.</p>
          </section>
          <section>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-3">3. Intellectual Property</h2>
            <p>Cloud Loop&apos;s codebase is open-source (MIT). The brand, logo, and design are owned by Ayush Sharma. Opportunity data belongs to their respective owners.</p>
          </section>
          <section>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-3">4. Limitation of Liability</h2>
            <p>Cloud Loop is provided &quot;as is&quot; without warranty. We are not responsible for any employment decisions, missed applications, or outcomes resulting from using the platform.</p>
          </section>
          <section>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-3">5. Changes</h2>
            <p>We may update these terms. Continued use after changes constitutes acceptance.</p>
          </section>
        </div>

        <div className="mt-12 pt-6 border-t border-border dark:border-dark-border">
          <Link href="/" className="text-sm text-[#C6F432] hover:underline">← Back to Cloud Loop</Link>
        </div>
      </div>
    </div>
  );
}

