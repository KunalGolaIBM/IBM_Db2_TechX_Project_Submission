import { MetadataRoute } from "next";
import { programs } from "@/features/programs";
import { events } from "@/features/events";
import { internships } from "@/features/internships";
import { jobs } from "@/features/jobs";
import { certifications } from "@/features/certifications";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://cloudloop.dev";

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: base, lastModified: new Date(), changeFrequency: "daily", priority: 1 },
    { url: `${base}/programs`, lastModified: new Date(), changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/events`, lastModified: new Date(), changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/internships`, lastModified: new Date(), changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/jobs`, lastModified: new Date(), changeFrequency: "daily", priority: 0.9 },
    { url: `${base}/certifications`, lastModified: new Date(), changeFrequency: "weekly", priority: 0.8 },
    { url: `${base}/community`, lastModified: new Date(), changeFrequency: "weekly", priority: 0.7 },
    { url: `${base}/dashboard`, lastModified: new Date(), changeFrequency: "daily", priority: 0.7 },
    { url: `${base}/about`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.5 },
    { url: `${base}/contact`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.5 },
    { url: `${base}/privacy`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.3 },
    { url: `${base}/terms`, lastModified: new Date(), changeFrequency: "monthly", priority: 0.3 },
  ];

  const programRoutes: MetadataRoute.Sitemap = programs.map((p) => ({
    url: `${base}/programs/${p.slug}`,
    lastModified: new Date(),
    changeFrequency: "weekly",
    priority: 0.8,
  }));

  const eventRoutes: MetadataRoute.Sitemap = events.map((e) => ({
    url: `${base}/events/${e.slug}`,
    lastModified: new Date(),
    changeFrequency: "weekly",
    priority: 0.7,
  }));

  return [...staticRoutes, ...programRoutes, ...eventRoutes];
}
