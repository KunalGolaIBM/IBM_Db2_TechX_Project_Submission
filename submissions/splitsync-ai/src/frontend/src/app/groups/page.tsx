'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useFetch } from '@/hooks/use-api';
import { AppShell } from '@/components/layout/app-shell';
import { GroupCard } from '@/components/groups/group-card';
import { GroupForm, type CreateGroupData } from '@/components/groups/group-form';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { api, ApiError } from '@/lib/api-client';
import type { Group } from '@/lib/types';

export default function GroupsPage() {
  const router = useRouter();
  const { data: groups, error, isLoading, refetch } = useFetch<Group[]>('/api/v1/groups');

  const [isDialogOpen, setIsDialogOpen] = React.useState(false);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [formError, setFormError] = React.useState<string | null>(null);

  const handleCreateGroup = async (data: CreateGroupData) => {
    setIsSubmitting(true);
    setFormError(null);

    try {
      const newGroup = await api.post<Group>('/api/v1/groups', data);
      setIsDialogOpen(false);
      if (newGroup && newGroup.group_id) {
        router.push(`/groups/${newGroup.group_id}`);
      } else {
        refetch();
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else if (err instanceof Error) {
        setFormError(err.message);
      } else {
        setFormError('Failed to create group. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppShell title="Groups">
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Groups
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Manage your shared expense pools, participant members, and Db2 ledgers.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/groups/new">
              <Button variant="outline" size="md">
                Full Page Form
              </Button>
            </Link>
            <Button
              variant="primary"
              size="md"
              onClick={() => setIsDialogOpen(true)}
            >
              <svg
                className="w-4 h-4 mr-1.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Create Group
            </Button>
          </div>
        </div>

        {/* Content Body */}
        {isLoading ? (
          <div className="flex h-64 items-center justify-center rounded-lg border border-slate-200 bg-white">
            <Spinner size="lg" />
          </div>
        ) : error ? (
          <ErrorState
            title="Failed to load groups"
            message={error.message}
            onRetry={() => refetch()}
          />
        ) : !groups || groups.length === 0 ? (
          <EmptyState
            title="No groups found"
            description="You haven't joined or created any expense groups yet. Create a group to start tracking payments and reconciling shared debts."
            action={{
              label: 'Create Your First Group',
              onClick: () => setIsDialogOpen(true),
            }}
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {groups.map((group) => (
              <GroupCard key={group.group_id} group={group} />
            ))}
          </div>
        )}
      </div>

      {/* Quick Create Group Dialog */}
      <Dialog
        isOpen={isDialogOpen}
        onClose={() => {
          setIsDialogOpen(false);
          setFormError(null);
        }}
        title="Create New Group"
        description="Initialize a new expense group with IBM Db2 ledger tracking."
      >
        <GroupForm
          onSubmit={handleCreateGroup}
          isLoading={isSubmitting}
          errorMessage={formError}
          onCancel={() => {
            setIsDialogOpen(false);
            setFormError(null);
          }}
        />
      </Dialog>
    </AppShell>
  );
}
