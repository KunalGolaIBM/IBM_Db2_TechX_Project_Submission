'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/use-auth';
import { useGroups } from '@/hooks/use-groups';
import { AppShell } from '@/components/layout/app-shell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Dialog } from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { StatusBadge } from '@/components/ui/status-badge';
import { formatPaise, formatDate } from '@/lib/utils';
import { api } from '@/lib/api-client';
import type { Group } from '@/lib/types';

export default function DashboardPage() {
  const router = useRouter();
  const { user, isLoading: isAuthLoading } = useAuth();
  const { data: groups, error, isLoading: isGroupsLoading, refetch } = useGroups();

  const [isCreateModalOpen, setIsCreateModalOpen] = React.useState(false);
  const [newGroupName, setNewGroupName] = React.useState('');
  const [newGroupDescription, setNewGroupDescription] = React.useState('');
  const [newGroupCurrency, setNewGroupCurrency] = React.useState('INR');
  const [newGroupAccountingMode, setNewGroupAccountingMode] = React.useState('cash');
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);

  // Redirect to login if user is unauthenticated after auth finishes loading
  React.useEffect(() => {
    if (!isAuthLoading && !user) {
      router.push('/login');
    }
  }, [isAuthLoading, user, router]);

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!newGroupName.trim()) {
      setFormError('Please enter a group name');
      return;
    }

    setIsSubmitting(true);
    try {
      await api.post<Group>('/groups', {
        name: newGroupName.trim(),
        description: newGroupDescription.trim(),
        currency: newGroupCurrency,
        split_method: 'equal',
        accounting_mode: newGroupAccountingMode,
      });

      setNewGroupName('');
      setNewGroupDescription('');
      setIsCreateModalOpen(false);
      refetch();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError('Failed to create group. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isAuthLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-slate-50">
        <Spinner size="lg" />
      </div>
    );
  }

  const activeGroups = groups?.filter((g) => g.status === 'active') || [];
  const groupCount = groups?.length || 0;

  return (
    <AppShell title="Dashboard">
      <div className="space-y-8">
        {/* Welcome and Top Actions */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Welcome back, {user?.display_name || 'there'}
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Here is an overview of your active expense pools and reconciliation ledgers.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/groups">
              <Button variant="outline" size="md">
                View All Groups
              </Button>
            </Link>
            <Button
              variant="primary"
              size="md"
              onClick={() => setIsCreateModalOpen(true)}
            >
              <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create Group
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">
                Active Groups
              </CardTitle>
              <div className="h-8 w-8 rounded-md bg-primary-50 text-primary-600 flex items-center justify-center">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
                </svg>
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">
                {activeGroups.length}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                {groupCount} total groups created
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">
                Total Contributed
              </CardTitle>
              <div className="h-8 w-8 rounded-md bg-emerald-50 text-emerald-600 flex items-center justify-center">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">
                {formatPaise(0)}
              </div>
              <p className="mt-1 text-xs text-slate-500">
                Across all active ledgers
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium text-slate-600">
                Pending Approvals
              </CardTitle>
              <div className="h-8 w-8 rounded-md bg-amber-50 text-amber-600 flex items-center justify-center">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-slate-900">0</div>
              <p className="mt-1 text-xs text-slate-500">
                Dual-custody cash reviews
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Groups Section */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-slate-900">
              Recent Groups
            </h3>
          </div>

          {isGroupsLoading ? (
            <div className="flex h-48 items-center justify-center rounded-lg border border-slate-200 bg-white">
              <Spinner size="lg" />
            </div>
          ) : error ? (
            <ErrorState
              title="Unable to load groups"
              message={error.message}
              onRetry={() => refetch()}
            />
          ) : !groups || groups.length === 0 ? (
            <EmptyState
              title="No groups found"
              description="You are not a member of any expense groups yet. Create your first group to start splitting expenses."
              action={{
                label: 'Create First Group',
                onClick: () => setIsCreateModalOpen(true),
              }}
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {groups.map((group) => (
                <Card key={group.group_id} className="hover:border-slate-300 transition-colors">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <CardTitle className="text-base truncate">
                        {group.name}
                      </CardTitle>
                      <StatusBadge status={group.status} />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <p className="text-sm text-slate-600 line-clamp-2 min-h-[2.5rem]">
                      {group.description || 'No description provided'}
                    </p>
                    <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-100">
                      <span>Accounting: <strong className="font-medium text-slate-700 capitalize">{group.accounting_mode}</strong></span>
                      <span>Created {formatDate(group.created_at)}</span>
                    </div>
                    <Link href={`/groups/${group.group_id}`} className="block w-full">
                      <Button variant="secondary" size="sm" className="w-full">
                        View Group
                      </Button>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create Group Modal Dialog */}
      <Dialog
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create New Group"
        description="Set up a shared expense pool with automated Db2 ledger tracking."
      >
        <form onSubmit={handleCreateGroup} className="space-y-4">
          {formError && (
            <div className="rounded-md bg-rose-50 p-3 text-sm font-medium text-rose-700 border border-rose-200">
              {formError}
            </div>
          )}

          <Input
            id="group-name"
            label="Group Name"
            placeholder="e.g. Goa Trip 2026, Flat 402 Utilities"
            value={newGroupName}
            onChange={(e) => setNewGroupName(e.target.value)}
            required
          />

          <div className="w-full space-y-1.5">
            <label htmlFor="group-desc" className="block text-sm font-medium text-slate-700">
              Description (Optional)
            </label>
            <textarea
              id="group-desc"
              rows={3}
              className="flex w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors"
              placeholder="Brief details about the group purpose..."
              value={newGroupDescription}
              onChange={(e) => setNewGroupDescription(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Select
              label="Currency"
              value={newGroupCurrency}
              onChange={(e) => setNewGroupCurrency(e.target.value)}
              options={[
                { label: 'INR (₹)', value: 'INR' },
                { label: 'USD ($)', value: 'USD' },
                { label: 'EUR (€)', value: 'EUR' },
              ]}
            />

            <Select
              label="Accounting Mode"
              value={newGroupAccountingMode}
              onChange={(e) => setNewGroupAccountingMode(e.target.value)}
              options={[
                { label: 'Cash (Recorded on payment)', value: 'cash' },
                { label: 'Accrual (Recorded on expense)', value: 'accrual' },
              ]}
            />
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isSubmitting}
            >
              Create Group
            </Button>
          </div>
        </form>
      </Dialog>
    </AppShell>
  );
}
