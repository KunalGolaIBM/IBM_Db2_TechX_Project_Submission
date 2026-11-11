import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Student Career Dashboard — Cloud Loop",
  description: "Track your bookmarked opportunities, monitor application deadlines, and receive personalized AI recommendations.",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

