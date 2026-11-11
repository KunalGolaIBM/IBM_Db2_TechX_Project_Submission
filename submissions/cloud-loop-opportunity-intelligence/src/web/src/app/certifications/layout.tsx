import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Industry Certifications & Free Vouchers — Cloud Loop",
  description: "Free and discounted cloud, AI, and cybersecurity certifications from Google Cloud, AWS, Microsoft, and IBM.",
};

export default function CertificationsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}

