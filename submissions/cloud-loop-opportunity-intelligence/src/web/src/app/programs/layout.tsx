import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Student Programs & Campus Ambassadorships — Cloud Loop",
  description: "Explore Google Cloud Arcade, Microsoft Learn Student Ambassadors (MLSA), GitHub Campus Experts, and exclusive developer fellowship programs.",
};

export default function ProgramsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

