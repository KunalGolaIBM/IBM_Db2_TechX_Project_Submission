import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Community & Student Success Stories — Cloud Loop",
  description: "Connect with thousands of students and mentors. Read real success stories and preparation strategies for top student programs.",
};

export default function CommunityLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

