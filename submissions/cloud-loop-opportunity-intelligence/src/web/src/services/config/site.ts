export const siteConfig = {
  name: "Cloud-Loop",
  shortName: "CloudLoop",
  description: "Discover curated student opportunities, internships, hackathons, and certifications powered by IBM Db2 and Haystack AI vector search.",
  url: process.env.NEXT_PUBLIC_APP_URL || "https://cloud-loop.org",
  ogImage: "/cloud-loop.png",
  contact: {
    email: process.env.NEXT_PUBLIC_CONTACT_EMAIL || "contact@cloud-loop.org",
    supportEmail: process.env.NEXT_PUBLIC_SUPPORT_EMAIL || "support@cloud-loop.org",
    github: "https://github.com/Ayushh-Sharmaa/Cloud-Loop",
  },
  links: {
    github: "https://github.com/Ayushh-Sharmaa/Cloud-Loop",
    docs: "/about",
  },
  creator: "Ayush Sharma (@Ayushh-Sharmaa)",
};
