import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import { BackendProvider } from "@/components/layout/BackendProvider";
import { Header } from "@/components/layout/Header";

export const metadata: Metadata = {
  title: "MetricGuard — Trustworthy AI analytics on IBM Db2",
  description: "Ask a business question, then inspect the SQL, metric definitions and checks behind the answer.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-ink focus:px-3 focus:py-2 focus:text-white">Skip to content</a>
        <BackendProvider>
          <Header />
          <main id="main" className="mx-auto w-full max-w-[1400px] px-4 pb-24 pt-8 sm:px-6">{children}</main>
        </BackendProvider>
      </body>
    </html>
  );
}
