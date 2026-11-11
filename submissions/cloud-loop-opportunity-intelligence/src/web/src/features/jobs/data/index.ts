import jobsSeed from "@/data/seed/jobs.json";
import { Job } from "../types/Job";

export const jobs: Job[] = (jobsSeed as any[]).map((j) => {
  const skills = Array.isArray(j.skills)
    ? j.skills
    : (typeof j.skills === "string" ? j.skills.split(",").map((s: string) => s.trim()) : []);

  const location = j.location || "India";
  let locationType: "remote" | "hybrid" | "onsite" = "onsite";
  const locLower = (j.mode || j.location_type || location || "").toLowerCase();
  if (locLower.includes("remote") || locLower.includes("wfh")) {
    locationType = "remote";
  } else if (locLower.includes("hybrid")) {
    locationType = "hybrid";
  }

  return {
    id: String(j.id || j.slug),
    slug: String(j.slug || j.id),
    company: String(j.org || j.organization || "Company"),
    companyLogo: `https://www.google.com/s2/favicons?domain=${String(j.org || "google").toLowerCase().replace(/[^a-z0-9]/g, "")}.com&sz=64`,
    role: String(j.title || j.role || "Software Engineer"),
    location,
    locationType,
    salaryRange: j.salaryRange || "Competitive",
    experience: j.experience || "Freshers / 0-2 yrs",
    category: j.category || "Software",
    skills,
    isEasyApply: Boolean(j.isEasyApply),
    deadline: j.deadline || "Ongoing",
    posted: j.posted || "2026-08-01",
    description: j.description || `${j.title} at ${j.org}`,
    tags: j.tags || ["Full-time", "Active"],
    applyUrl: j.apply_url || j.applyUrl || "#",
    eligibleBatch: j.eligibleBatch || "2024-2027",
    isNew: true,
  };
});
