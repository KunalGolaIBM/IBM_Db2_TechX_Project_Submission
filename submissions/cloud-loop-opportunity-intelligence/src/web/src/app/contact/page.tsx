import type { Metadata } from "next";
import Link from "next/link";
import { siteConfig } from "@/config/site";

export const metadata: Metadata = {
  title: "Contact — Cloud Loop",
  description: "Get in touch with the Cloud Loop team.",
};

export default function ContactPage() {
  return (
    <div className="min-h-screen bg-background dark:bg-dark-background pt-28 pb-20">
      <div className="container-narrow max-w-2xl">
        <div className="mb-10 border-b-2 border-[#C6F432] pb-6">
          <span className="text-xs font-bold uppercase tracking-widest text-[#C6F432] mb-3 block">Contact</span>
          <h1 className="text-4xl md:text-5xl font-black text-text-primary dark:text-dark-text-primary mb-4">Get In Touch</h1>
          <p className="text-text-secondary dark:text-dark-text-secondary">Have a question, suggestion, or opportunity to list? Reach out.</p>
        </div>

        <div className="space-y-6">
          <div className="card-base p-6">
            <h3 className="font-bold text-text-primary dark:text-dark-text-primary mb-2">📧 Email</h3>
            <a href={`mailto:${siteConfig.contact.email}`} className="text-[#C6F432] font-medium hover:underline text-lg">
              {siteConfig.contact.email}
            </a>
          </div>

          <div className="card-base p-6">
            <h3 className="font-bold text-text-primary dark:text-dark-text-primary mb-2">📞 Helpline / WhatsApp Direct</h3>
            <a href="tel:+919876543210" className="text-[#C6F432] font-medium hover:underline text-lg">
              +91 (987) 654-3210
            </a>
            <p className="text-text-secondary dark:text-dark-text-secondary text-xs mt-1">Available Mon–Fri, 10 AM – 6 PM IST</p>
          </div>

          <div className="card-base p-6">
            <h3 className="font-bold text-text-primary dark:text-dark-text-primary mb-2">💬 Community</h3>
            <p className="text-text-secondary dark:text-dark-text-secondary text-sm mb-3">Join our channels for instant updates and discussion:</p>
            <div className="flex flex-wrap gap-3">
              <a href={siteConfig.socials.telegram} target="_blank" rel="noopener noreferrer" className="btn-outline-lime px-4 py-2 rounded-full text-sm">Telegram Channel</a>
              <a href={siteConfig.socials.whatsapp} target="_blank" rel="noopener noreferrer" className="btn-outline-lime px-4 py-2 rounded-full text-sm">WhatsApp Channel</a>
            </div>
          </div>

          <div className="card-base p-6">
            <h3 className="font-bold text-text-primary dark:text-dark-text-primary mb-2">🐙 GitHub</h3>
            <p className="text-text-secondary dark:text-dark-text-secondary text-sm mb-3">Report bugs, contribute, or suggest features:</p>
            <a href={siteConfig.socials.github} target="_blank" rel="noopener noreferrer" className="text-[#C6F432] hover:underline font-medium">
              github.com/Ayushh-Sharmaa/Cloud-Loop →
            </a>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-border dark:border-dark-border">
          <Link href="/" className="text-sm text-[#C6F432] hover:underline">← Back to Cloud Loop</Link>
        </div>
      </div>
    </div>
  );
}

