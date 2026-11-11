import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Hackathons, Tech Conferences & Bootcamps — Cloud Loop",
  description: "Discover upcoming hackathons, AI summits, competitive programming contests, and developer bootcamps with major prize pools.",
};

export default function EventsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

