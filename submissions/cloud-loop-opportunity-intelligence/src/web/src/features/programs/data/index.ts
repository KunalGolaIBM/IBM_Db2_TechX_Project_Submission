import programsSeed from "@/data/seed/programs.json";
import { Program } from "../types/Program";

export const programs: Program[] = (programsSeed as any[]).map((p) => {
  const skills = Array.isArray(p.skills)
    ? p.skills
    : (typeof p.skills === "string" ? p.skills.split(",").map((s: string) => s.trim()) : []);

  return {
    id: String(p.id || p.slug),
    slug: String(p.slug || p.id),
    name: String(p.title || p.name || "Student Program"),
    provider: String(p.org || p.provider || "Tech Leader"),
    providerLogo: `https://www.google.com/s2/favicons?domain=${String(p.org || p.provider || "google").toLowerCase().replace(/[^a-z0-9]/g, "")}.com&sz=64`,
    category: String(p.category || "Student Program"),
    status: (p.status || "open") as "open" | "closed",
    difficulty: p.difficulty || "Beginner / Intermediate",
    duration: p.duration || "Self-Paced / Cohort",
    deadline: p.deadline || "Ongoing",
    eligibility: p.eligibility || "Open to all enrolled university students",
    keyBenefit: p.keyBenefit || "Mentorship, Swag, Certification, Network",
    description: p.description || `${p.title} offered by ${p.org}`,
    tags: p.tags || skills || ["Campus", "Community"],
    website: p.apply_url || p.website || "#",
    featured: Boolean(p.featured),
    applicants: p.applicants || 120,
    registrationForm: p.apply_url || p.registrationForm,
    facilitatorCode: p.facilitatorCode,
  };
});
