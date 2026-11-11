import eventsSeed from "@/data/seed/events.json";
import { Event } from "../types/Event";

export const events: Event[] = (eventsSeed as any[]).map((e) => {
  const skills = Array.isArray(e.skills)
    ? e.skills
    : (typeof e.skills === "string" ? e.skills.split(",").map((s: string) => s.trim()) : []);

  return {
    id: String(e.id || e.slug),
    slug: String(e.slug || e.id),
    title: String(e.title || "Hackathon & Event"),
    organizer: String(e.org || e.organizer || "Community Organizer"),
    organizerLogo: `https://www.google.com/s2/favicons?domain=${String(e.org || e.organizer || "devpost").toLowerCase().replace(/[^a-z0-9]/g, "")}.com&sz=64`,
    type: String(e.type || e.category || "Hackathon"),
    date: e.date || "2026-11-15",
    endDate: e.endDate,
    location: e.location || "Online / Pan-India",
    isOnline: !e.location || e.location.toLowerCase().includes("online") || e.location.toLowerCase().includes("remote"),
    banner: e.banner || "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=800&auto=format&fit=crop&q=60",
    registrationDeadline: e.deadline || e.registrationDeadline || "2026-12-01",
    description: e.description || `${e.title} organized by ${e.org || e.organizer}`,
    prize: e.prize || "Cash Prizes, Goodies & Certificates",
    tags: e.tags || skills || ["Hackathon", "Student"],
    registered: e.registered || 350,
    applyUrl: e.apply_url || e.applyUrl || "#",
  };
});
