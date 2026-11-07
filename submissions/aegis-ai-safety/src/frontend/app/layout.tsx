import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";

import "./globals.css";

export const metadata: Metadata = {
  title: "AEGIS — The paper exists. Does the evidence?",
  description:
    "Independent research verification. Check AI-generated claims against the actual paper, inspect page-level evidence, and export an auditable report.",
  metadataBase: new URL("https://aegis-research-verification.vercel.app"),
  openGraph: {
    title: "AEGIS — The paper exists. Does the evidence?",
    description:
      "Check AI-generated research claims against actual scientific papers. Evidence first. Confidence second.",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={GeistSans.variable}>
      <body className="min-h-screen bg-canvas font-sans text-ink antialiased">{children}</body>
    </html>
  );
}
