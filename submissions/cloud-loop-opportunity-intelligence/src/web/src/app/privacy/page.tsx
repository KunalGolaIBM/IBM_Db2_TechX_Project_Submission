import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy — Cloud Loop",
  description: "Privacy policy for Cloud Loop — how we handle your data.",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-28 pb-20">
      <div className="container-narrow max-w-3xl">
        <div className="mb-10 border-b-2 border-[#C6F432] pb-6">
          <span className="text-xs font-bold uppercase tracking-widest text-[#C6F432] mb-3 block">Legal</span>
          <h1 className="text-4xl font-black text-text-primary dark:text-dark-text-primary mb-2">Privacy Policy</h1>
          <p className="text-text-secondary dark:text-dark-text-secondary text-sm">Last updated: {new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}</p>
        </div>

        <div className="space-y-8 text-text-secondary dark:text-dark-text-secondary leading-relaxed">
          <section>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-3">1. Information We Collect</h2>
            <p>Cloud Loop collects only the minimum information needed to provide the service: your email address and name when you sign up via Clerk, and opportunity tracking preferences. We do not sell your data.</p>
          </section>
          <section>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-3">2. How We Use Your Data</h2>
            <p>Your data is used to: personalise your opportunity feed, remember your saved/tracked opportunities on the dashboard, and send optional weekly digest emails (only if you subscribe).</p>
          </section>
          <section>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-3">3. Third-Party Services</h2>
            <p>We use <strong>Clerk</strong> for secure authentication and <strong>IBM Db2 Cloud</strong> for encrypted database storage and analytics. Each maintains rigorous privacy and security certifications.</p>
          </section>
          <section>
            <h2 className="text-xl font-bold text-text-primary dark:text-dark-text-primary mb-3">4. Contact</h2>
            <p>For privacy questions, email <a href="mailto:hello@cloudloop.dev" className="text-[#C6F432] hover:underline">hello@cloudloop.dev</a>.</p>
          </section>
        </div>

        <div className="mt-12 pt-6 border-t border-border dark:border-dark-border">
          <Link href="/" className="text-sm text-[#C6F432] hover:underline">← Back to Cloud Loop</Link>
        </div>
      </div>
    </div>
  );
}

