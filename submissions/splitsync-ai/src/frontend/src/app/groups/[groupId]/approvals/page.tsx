'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useAuth } from '@/hooks/use-auth';
import { useFetch } from '@/hooks/use-api';
import { AppShell } from '@/components/layout/app-shell';
import { ApprovalList } from '@/components/approvals/approval-list';
import { Badge } from '@/components/ui/badge';
import type { Group, GroupMember, PendingApprovalItem } from '@/lib/types';

export default function GroupApprovalsPage() {
  const params = useParams();
  const groupId = typeof params?.groupId === 'string' ? params.groupId : '';
  const { user } = useAuth();

  const { data: group } = useFetch<Group>(groupId ? `/api/v1/groups/${groupId}` : null);
  const { data: myMembership } = useFetch<GroupMember>(
    groupId ? `/api/v1/groups/${groupId}/members/me` : null
  );
  const { data: pendingItems } = useFetch<PendingApprovalItem[]>(
    groupId ? `/api/v1/groups/${groupId}/approvals/pending` : null
  );

  const pendingCount = pendingItems?.length ?? 0;

  return (
    <AppShell title={group ? `${group.name} - Approvals` : 'Group Approvals'}>
      <div className="space-y-6">
        {/* Breadcrumb Navigation */}
        <div className="flex items-center space-x-2 text-sm text-slate-500">
          <Link href="/groups" className="hover:text-slate-800 transition-colors">
            Groups
          </Link>
          <span>/</span>
          <Link
            href={`/groups/${groupId}`}
            className="hover:text-slate-800 transition-colors font-medium text-slate-700"
          >
            {group?.name || 'Group'}
          </Link>
          <span>/</span>
          <span className="text-slate-900 font-semibold">Approvals</span>
        </div>

        {/* Header with Pending Badge */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">
                Peer Approvals
              </h2>
              {pendingCount > 0 ? (
                <Badge variant="warning" className="text-xs font-bold px-2 py-0.5">
                  {pendingCount} Pending
                </Badge>
              ) : (
                <Badge variant="success" className="text-xs font-semibold px-2 py-0.5">
                  All Approved
                </Badge>
              )}
            </div>
            <p className="mt-1 text-sm text-slate-600">
              Independent peer verification queue for physical cash claims and offline expenditures.
            </p>
          </div>
        </div>

        {/* Approval List Component */}
        <ApprovalList
          groupId={groupId}
          currentUserId={user?.user_id}
          myMemberId={myMembership?.group_member_id}
        />
      </div>
    </AppShell>
  );
}
