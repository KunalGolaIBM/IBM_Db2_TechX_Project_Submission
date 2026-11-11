import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'SplitSync AI',
  description: 'AI-assisted group payment tracking and expense reconciliation',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-slate-50 text-slate-900 min-h-screen font-sans">
        {children}
      </body>
    </html>
  );
}
