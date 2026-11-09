/**
 * @file navigation.ts
 * @description Centralised navigation link definitions.
 * Single source of truth for Navbar, Footer, and mobile menu.
 */

export interface NavLink {
  label: string;
  href: string;
  description?: string;
}

/** Main top-level navigation links */
export const mainNavLinks: NavLink[] = [
  { label: "Programs", href: "/programs", description: "Student ambassador & campus programs" },
  { label: "Events", href: "/events", description: "Hackathons, workshops & conferences" },
  { label: "Internships", href: "/internships", description: "Paid internship openings" },
  { label: "Jobs", href: "/jobs", description: "Fresher & entry-level positions" },
  { label: "Certifications", href: "/certifications", description: "Industry-recognized certificates" },
  { label: "Community", href: "/community", description: "Connect with fellow students" },
];

/** Footer link sections */
export const footerLinkSections: Record<string, NavLink[]> = {
  Product: [
    { label: "Programs", href: "/programs" },
    { label: "Events", href: "/events" },
    { label: "Internships", href: "/internships" },
    { label: "Jobs", href: "/jobs" },
    { label: "Certifications", href: "/certifications" },
  ],
  Resources: [
    { label: "Success Stories", href: "/#stories" },
    { label: "FAQ", href: "/#faq" },
    { label: "Community", href: "/community" },
  ],
  Company: [
    { label: "About", href: "/about" },
    { label: "Privacy Policy", href: "/privacy" },
    { label: "Terms of Service", href: "/terms" },
    { label: "Contact", href: "/contact" },
  ],
};

