import internshipsSeed from "@/data/seed/internships.json";
import { Internship } from "../types/Internship";

export const internships: Internship[] = (internshipsSeed as any[]).map((i) => {
  const skills = Array.isArray(i.skills)
    ? i.skills
    : (typeof i.skills === "string" ? i.skills.split(",").map((s: string) => s.trim()) : []);

  const location = i.location || "India";
  let locationType: "remote" | "hybrid" | "onsite" = "onsite";
  const locLower = (i.mode || i.location_type || location || "").toLowerCase();
  if (locLower.includes("remote") || locLower.includes("wfh")) {
    locationType = "remote";
  } else if (locLower.includes("hybrid")) {
    locationType = "hybrid";
  }

  return {
    id: String(i.id || i.slug),
    slug: String(i.slug || i.id),
    company: String(i.org || i.organization || "Company"),
    companyLogo: `https://www.google.com/s2/favicons?domain=${String(i.org || "google").toLowerCase().replace(/[^a-z0-9]/g, "")}.com&sz=64`,
    role: String(i.title || i.role || "Intern"),
    location,
    locationType,
    stipend: i.stipend || "Competitive",
    duration: i.duration || "3-6 Months",
    isPaid: true,
    deadline: i.deadline || "Ongoing",
    skills,
    description: i.description || `${i.title} at ${i.org}`,
    tags: i.tags || ["Internship", "Active"],
    applyUrl: i.apply_url || i.applyUrl || "#",
    eligibleBatch: i.eligibleBatch || "2025-2028",
    isNew: true,
  };
});
