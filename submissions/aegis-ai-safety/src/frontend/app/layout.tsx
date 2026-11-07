import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "AEGIS — Verify Before You Trust",
  description:
    "Independent AI research verification. Extract atomic claims, retrieve evidence from IBM Db2, and inspect evidence-linked LangChain assessments.",
};

const themeScript = `
(function () {
  try {
    var stored = localStorage.getItem('aegis-theme');
    if (stored === 'light') document.documentElement.classList.remove('dark');
  } catch (e) {}
})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-screen bg-bg font-sans text-fg antialiased">{children}</body>
    </html>
  );
}
