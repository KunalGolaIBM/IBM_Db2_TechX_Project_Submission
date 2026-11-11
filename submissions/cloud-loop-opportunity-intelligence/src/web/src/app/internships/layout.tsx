import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Tech Internships & Summer Programs — Cloud Loop",
  description: "Find high-stipend software engineering, data science, AI, and cloud internships from top global tech companies.",
};

export default function InternshipsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

