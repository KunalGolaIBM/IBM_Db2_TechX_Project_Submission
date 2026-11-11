'use client';

import * as React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AppShell } from '@/components/layout/app-shell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { GroupForm, type CreateGroupData } from '@/components/groups/group-form';
import { api, ApiError } from '@/lib/api-client';
import type { Group } from '@/lib/types';

export default function NewGroupPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = React.useState(false);
  const [apiError, setApiError] = React.useState<string | null>(null);

  const handleCreateGroup = async (formData: CreateGroupData) => {
    setIsLoading(true);
    setApiError(null);

    try {
      const response = await api.post<Group>('/api/v1/groups', formData);
      if (response && response.group_id) {
        router.push(`/groups/${response.group_id}`);
      } else {
        router.push('/groups');
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setApiError(err.message || 'Failed to create group');
      } else if (err instanceof Error) {
        setApiError(err.message);
      } else {
        setApiError('An unexpected error occurred while creating the group.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AppShell title="Create Group">
      <div className="max-w-2xl mx-auto py-6">
        <div className="mb-6">
          <Link
            href="/groups"
            className="inline-flex items-center text-sm font-medium text-slate-500 hover:text-slate-800 transition-colors"
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
                d="M15 19l-7-7 7-7"
              />
            </svg>
            Back to Groups
          </Link>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Create New Group</CardTitle>
            <CardDescription>
              Set up a shared expense pool with automated Db2 ledger tracking and fair settlement.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <GroupForm
              onSubmit={handleCreateGroup}
              isLoading={isLoading}
              errorMessage={apiError}
              onCancel={() => router.push('/groups')}
            />
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
