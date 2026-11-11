'use client';

import * as React from 'react';
import { Sidebar } from './sidebar';
import { Header } from './header';

export interface AppShellProps {
  title?: string;
  children: React.ReactNode;
}

export function AppShell({ title, children }: AppShellProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = React.useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* Sidebar navigation */}
      <Sidebar
        isOpen={isMobileMenuOpen}
        onClose={() => setIsMobileMenuOpen(false)}
      />

      {/* Main content column */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header
          title={title}
          onOpenMenu={() => setIsMobileMenuOpen(true)}
        />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-7xl">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
