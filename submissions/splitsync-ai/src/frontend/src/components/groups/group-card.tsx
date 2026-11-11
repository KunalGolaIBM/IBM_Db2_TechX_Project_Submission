'use client';

import * as React from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { StatusBadge } from '@/components/ui/status-badge';
import { formatDate } from '@/lib/utils';
import type { Group } from '@/lib/types';

export interface GroupCardProps {
  group: Group;
}

export function GroupCard({ group }: GroupCardProps) {
  const memberCount = group.member_count ?? 1;

  return (
    <Link href={`/groups/${group.group_id}`} className="block group">
      <Card className="h-full transition-all duration-200 border-slate-200 hover:border-primary-400 hover:shadow-md">
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between gap-3">
            <CardTitle className="text-base font-bold text-slate-900 group-hover:text-primary-600 transition-colors line-clamp-1">
              {group.name}
            </CardTitle>
            <StatusBadge status={group.status} />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-600 line-clamp-2 min-h-[2.5rem]">
            {group.description || 'No description provided'}
          </p>

          <div className="flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <span className="flex items-center gap-1 font-medium text-slate-700">
                <svg
                  className="w-3.5 h-3.5 text-slate-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
                  />
                </svg>
                {memberCount} {memberCount === 1 ? 'member' : 'members'}
              </span>
              <Badge variant="default" className="text-[10px] px-1.5 py-0 uppercase">
                {group.currency}
              </Badge>
            </div>
            <span className="text-slate-400">
              {formatDate(group.created_at)}
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
