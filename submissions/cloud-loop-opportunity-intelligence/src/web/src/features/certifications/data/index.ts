import certsSeed from "@/data/seed/certifications.json";
import { Certification } from "../types/Certification";

export const certifications: Certification[] = (certsSeed as any[]).map((c) => {
  const skills = Array.isArray(c.skills)
    ? c.skills
    : (typeof c.skills === "string" ? c.skills.split(",").map((s: string) => s.trim()) : []);

  return {
    id: String(c.id || c.slug),
    slug: String(c.slug || c.id),
    name: String(c.title || c.name || "Certification"),
    provider: String(c.org || c.provider || "Enterprise Academy"),
    providerLogo: `https://www.google.com/s2/favicons?domain=${String(c.org || c.provider || "ibm").toLowerCase().replace(/[^a-z0-9]/g, "")}.com&sz=64`,
    providerLink: c.providerLink || c.apply_url || "https://ibm.com",
    interestedCount: c.interestedCount || "5.2k",
    cost: (c.cost || "Free") as "Free" | "Paid",
    badge: c.badge || "Verified Credential",
    enrollUrl: c.apply_url || c.enrollUrl || "#",
    thumbnail: c.thumbnail || "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=400&auto=format&fit=crop&q=60",
    description: c.description || `${c.title} by ${c.org || c.provider}`,
    skills,
    difficulty: c.difficulty || "Beginner / Intermediate",
    duration: c.duration || "Self-Paced (2-6 Hours)",
  };
});
