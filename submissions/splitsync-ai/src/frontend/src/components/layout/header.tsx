'use client';

import * as React from 'react';
import { useAuth } from '@/hooks/use-auth';
import { getInitials } from '@/lib/utils';

export interface HeaderProps {
  title?: string;
  onOpenMenu?: () => void;
}

export function Header({ title, onOpenMenu }: HeaderProps) {
  const { user } = useAuth();

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6">
      <div className="flex items-center space-x-3">
        {onOpenMenu && (
          <button
            onClick={onOpenMenu}
            className="rounded-md p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700 lg:hidden"
            aria-label="Open sidebar"
          >
            <svg
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 12h16M4 18h16"
              />
            </svg>
          </button>
        )}
        {title && (
          <h1 className="text-xl font-semibold text-slate-900 tracking-tight">
            {title}
          </h1>
        )}
      </div>

      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-3">
          <div className="hidden text-right sm:block">
            <p className="text-sm font-medium text-slate-900">
              {user?.display_name || 'User'}
            </p>
            <p className="text-xs text-slate-500">{user?.email || ''}</p>
          </div>
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
            {user ? getInitials(user.display_name) : 'U'}
          </div>
        </div>
      </div>
    </header>
  );
}
