/**
 * @file site.ts
 * @description Site-wide metadata, navigation, and social links.
 */

export const siteConfig = {
  name: "Cloud Loop",
  tagline: "Discover Every Student Opportunity. One Platform.",
  description:
    "Cloud Loop is the single place students go to discover every opportunity — programs, events, internships, jobs, and certifications — instead of checking a dozen different websites.",
  url: "https://cloudloop.dev",
  ogImage: "https://cloudloop.dev/og-image.png",
  keywords: [
    "student opportunities",
    "internships",
    "hackathons",
    "Google Cloud Arcade",
    "GSoC",
    "MLSA",
    "certifications",
    "campus programs",
    "fresher jobs",
    "India",
  ],
  authors: [{ name: "Ayush Sharma", url: "https://github.com/Ayushh-Sharmaa" }],
  socials: {
    linkedin: "https://www.linkedin.com/in/ayushh-sharmaa/",
    telegram: "https://t.me/cloudloopupdates",
    whatsapp: "https://www.whatsapp.com/channel/0029VbAiEFzAe5VikdanX42e",
    github: "https://github.com/Ayushh-Sharmaa/Cloud-Loop",
  },
  contact: {
    email: "hello@cloudloop.dev",
  },
};

export type SiteConfig = typeof siteConfig;

