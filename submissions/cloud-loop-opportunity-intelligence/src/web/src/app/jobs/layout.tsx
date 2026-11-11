import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Fresher & Entry-Level Tech Jobs — Cloud Loop",
  description: "Browse curated fresher jobs, junior software engineer openings, AI/ML roles, and cloud careers. Real-time updates powered by IBM Db2.",
};

export default function JobsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

