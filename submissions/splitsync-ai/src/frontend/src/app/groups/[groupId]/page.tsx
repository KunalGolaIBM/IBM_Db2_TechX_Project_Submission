'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useFetch } from '@/hooks/use-api';
import { AppShell } from '@/components/layout/app-shell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { StatusBadge } from '@/components/ui/status-badge';
import { Spinner } from '@/components/ui/spinner';
import { ErrorState } from '@/components/ui/error-state';
import { formatPaise, formatDate, getInitials } from '@/lib/utils';
import type { Group, GroupMember, GroupSummary } from '@/lib/types';

export default function GroupDashboardPage() {
  const params = useParams();
  const groupId = typeof params?.groupId === 'string' ? params.groupId : '';

  const {
    data: group,
    error: groupError,
    isLoading: isGroupLoading,
    refetch: refetchGroup,
  } = useFetch<Group>(groupId ? `/api/v1/groups/${groupId}` : null);

  const {
    data: members,
    isLoading: isMembersLoading,
  } = useFetch<GroupMember[]>(groupId ? `/api/v1/groups/${groupId}/members` : null);

  const {
    data: summary,
  } = useFetch<GroupSummary>(groupId ? `/api/v1/groups/${groupId}/summary` : null);

  if (isGroupLoading) {
    return (
      <AppShell title="Group Dashboard">
        <div className="flex h-96 items-center justify-center">
          <Spinner size="lg" />
        </div>
      </AppShell>
    );
  }

  if (groupError || !group) {
    return (
      <AppShell title="Group Dashboard">
        <ErrorState
          title="Failed to load group details"
          message={groupError?.message || 'Group not found.'}
          onRetry={() => refetchGroup()}
        />
      </AppShell>
    );
  }

  const totalContributions = summary?.total_contributions_minor ?? 0;
  const totalExpenses = summary?.total_expenses_minor ?? 0;
  const memberCount = summary?.member_count ?? (members ? members.length : 0);
  const pendingApprovals = summary?.pending_approvals ?? 0;

  const quickActions = [
    {
      title: 'Payments',
      description: 'Record QR & UPI payments to the pool',
      href: `/groups/${groupId}/payments`,
      icon: (
        <svg className="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8h2a1 1 0 001-1V5a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1zm12 0h2a1 1 0 001-1V5a1 1 0 00-1-1h-2a1 1 0 00-1 1v2a1 1 0 001 1zM5 20h2a1 1 0 001-1v-2a1 1 0 00-1-1H5a1 1 0 00-1 1v2a1 1 0 001 1z" />
        </svg>
      ),
    },
    {
      title: 'Cash Contributions',
      description: 'Log and review physical cash handovers',
      href: `/groups/${groupId}/cash`,
      icon: (
        <svg className="w-5 h-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 9V7a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2m2 4h10a2 2 0 002-2v-6a2 2 0 00-2-2H9a2 2 0 00-2 2v6a2 2 0 002 2zm7-5a2 2 0 11-4 0 2 2 0 014 0z" />
        </svg>
      ),
    },
    {
      title: 'Expenses',
      description: 'Add and split group expenditures',
      href: `/groups/${groupId}/expenses`,
      icon: (
        <svg className="w-5 h-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
      ),
    },
    {
      title: 'Approvals',
      description: 'Dual-custody verification workflow',
      href: `/groups/${groupId}/approvals`,
      icon: (
        <svg className="w-5 h-5 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      title: 'Transactions',
      description: 'Audit log and immutable Db2 entries',
      href: `/groups/${groupId}/transactions`,
      icon: (
        <svg className="w-5 h-5 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
        </svg>
      ),
    },
    {
      title: 'Settlement',
      description: 'Min-transfer reconciliation engine',
      href: `/groups/${groupId}/settlement`,
      icon: (
        <svg className="w-5 h-5 text-rose-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
        </svg>
      ),
    },
  ];

  return (
    <AppShell title={group.name}>
      <div className="space-y-8">
        {/* Header Section */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 border-b border-slate-200 pb-6">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-2xl font-bold tracking-tight text-slate-900">
                {group.name}
              </h2>
              <StatusBadge status={group.status} />
              <Badge variant="default" className="text-xs uppercase">
                {group.currency}
              </Badge>
            </div>
            <p className="mt-2 text-sm text-slate-600 max-w-3xl">
              {group.description || 'No description provided.'}
            </p>
            <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
              <span>Accounting Mode: <strong className="font-semibold text-slate-700 capitalize">{group.accounting_mode}</strong></span>
              <span>•</span>
              <span>Split Method: <strong className="font-semibold text-slate-700 capitalize">{group.split_method}</strong></span>
              <span>•</span>
              <span>Created {formatDate(group.created_at)}</span>
            </div>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <Link href={`/groups/${groupId}/members`}>
              <Button variant="outline" size="sm">
                <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z" />
                </svg>
                Manage Members
              </Button>
            </Link>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Total Contributions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">
                {formatPaise(totalContributions)}
              </div>
              <p className="mt-1 text-xs text-slate-500">Verified cash & digital payments</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Total Expenses
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">
                {formatPaise(totalExpenses)}
              </div>
              <p className="mt-1 text-xs text-slate-500">Recorded shared expenses</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Members
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">
                {memberCount}
              </div>
              <p className="mt-1 text-xs text-slate-500">Active pool participants</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Pending Approvals
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">
                {pendingApprovals}
              </div>
              <p className="mt-1 text-xs text-slate-500">Awaiting peer review</p>
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions Grid */}
        <div className="space-y-4">
          <h3 className="text-lg font-bold text-slate-900">
            Quick Actions
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {quickActions.map((action) => (
              <Link key={action.title} href={action.href} className="block group">
                <Card className="h-full transition-all duration-200 border-slate-200 hover:border-primary-400 hover:shadow-sm">
                  <CardContent className="p-5 flex items-start space-x-4">
                    <div className="p-2.5 rounded-lg bg-slate-100 group-hover:bg-primary-50 transition-colors">
                      {action.icon}
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-slate-900 group-hover:text-primary-600 transition-colors">
                        {action.title}
                      </h4>
                      <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                        {action.description}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>
        </div>

        {/* Group Members Preview Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-slate-900">
              Group Members
            </h3>
            <Link
              href={`/groups/${groupId}/members`}
              className="text-xs font-medium text-primary-600 hover:text-primary-700 transition-colors"
            >
              View All ({members?.length || 0}) &rarr;
            </Link>
          </div>

          {isMembersLoading ? (
            <div className="flex h-32 items-center justify-center rounded-lg border border-slate-200 bg-white">
              <Spinner size="md" />
            </div>
          ) : !members || members.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
              No members found in this group.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {members.slice(0, 4).map((member) => (
                <Card key={member.group_member_id} className="p-4 border-slate-200">
                  <div className="flex items-center space-x-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
                      {getInitials(member.display_name)}
                    </div>
                    <div className="overflow-hidden">
                      <p className="truncate text-sm font-semibold text-slate-900">
                        {member.display_name}
                      </p>
                      <p className="truncate text-xs text-slate-500">
                        {member.email || 'No email'}
                      </p>
                      <div className="mt-1.5 flex items-center gap-1.5">
                        <Badge
                          variant={member.role.toLowerCase() === 'admin' ? 'info' : 'default'}
                          className="text-[10px] px-1.5 py-0 uppercase"
                        >
                          {member.role}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity Section */}
        <div className="space-y-4">
          <h3 className="text-lg font-bold text-slate-900">
            Recent Activity
          </h3>
          <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
            Recent activity will appear here
          </div>
        </div>
      </div>
    </AppShell>
  );
}
