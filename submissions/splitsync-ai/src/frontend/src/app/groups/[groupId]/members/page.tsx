'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useAuth } from '@/hooks/use-auth';
import { useFetch } from '@/hooks/use-api';
import { AppShell } from '@/components/layout/app-shell';
import { MemberList } from '@/components/groups/member-list';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Dialog } from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import { ErrorState } from '@/components/ui/error-state';
import { api, ApiError } from '@/lib/api-client';
import type { Group, GroupMember } from '@/lib/types';

export default function GroupMembersPage() {
  const params = useParams();
  const groupId = typeof params?.groupId === 'string' ? params.groupId : '';
  const { user } = useAuth();

  const {
    data: group,
  } = useFetch<Group>(groupId ? `/api/v1/groups/${groupId}` : null);

  const {
    data: members,
    error: membersError,
    isLoading: isMembersLoading,
    refetch: refetchMembers,
  } = useFetch<GroupMember[]>(groupId ? `/api/v1/groups/${groupId}/members` : null);

  const {
    data: myMembership,
  } = useFetch<GroupMember>(groupId ? `/api/v1/groups/${groupId}/members/me` : null);

  // Determine if the current user is an admin
  const isAdmin = React.useMemo(() => {
    if (myMembership?.role?.toLowerCase() === 'admin') return true;
    if (user && members) {
      const match = members.find((m) => m.user_id === user.user_id);
      return match?.role?.toLowerCase() === 'admin';
    }
    return false;
  }, [myMembership, user, members]);

  // Add Member Modal State
  const [isAddModalOpen, setIsAddModalOpen] = React.useState(false);
  const [newMemberEmail, setNewMemberEmail] = React.useState('');
  const [newMemberRole, setNewMemberRole] = React.useState('member');
  const [isAdding, setIsAdding] = React.useState(false);
  const [addError, setAddError] = React.useState<string | null>(null);

  // Remove Member Confirm Modal State
  const [memberToRemove, setMemberToRemove] = React.useState<{ id: string; name: string } | null>(null);
  const [isRemoving, setIsRemoving] = React.useState(false);
  const [removeError, setRemoveError] = React.useState<string | null>(null);

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddError(null);

    const email = newMemberEmail.trim();
    if (!email) {
      setAddError('Please provide a valid email address.');
      return;
    }

    setIsAdding(true);
    try {
      await api.post(`/api/v1/groups/${groupId}/members`, {
        email,
        role: newMemberRole,
      });

      setNewMemberEmail('');
      setNewMemberRole('member');
      setIsAddModalOpen(false);
      refetchMembers();
    } catch (err) {
      if (err instanceof ApiError) {
        setAddError(err.message || 'Failed to add member.');
      } else if (err instanceof Error) {
        setAddError(err.message);
      } else {
        setAddError('Failed to add member to the group.');
      }
    } finally {
      setIsAdding(false);
    }
  };

  const handleConfirmRemove = async () => {
    if (!memberToRemove) return;

    setIsRemoving(true);
    setRemoveError(null);

    try {
      await api.delete(`/api/v1/groups/${groupId}/members/${memberToRemove.id}`);
      setMemberToRemove(null);
      refetchMembers();
    } catch (err) {
      if (err instanceof ApiError) {
        setRemoveError(err.message || 'Failed to remove member.');
      } else if (err instanceof Error) {
        setRemoveError(err.message);
      } else {
        setRemoveError('An error occurred while removing the member.');
      }
    } finally {
      setIsRemoving(false);
    }
  };

  return (
    <AppShell title={group ? `${group.name} - Members` : 'Group Members'}>
      <div className="space-y-6">
        {/* Navigation Breadcrumb */}
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
          <span className="text-slate-900 font-semibold">Members</span>
        </div>

        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Group Members
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Manage participant access, permissions, and roles in this ledger.
            </p>
          </div>
          {isAdmin && (
            <Button
              variant="primary"
              size="md"
              onClick={() => setIsAddModalOpen(true)}
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
                  d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z"
                />
              </svg>
              Add Member
            </Button>
          )}
        </div>

        {/* Members Table */}
        {isMembersLoading ? (
          <div className="flex h-64 items-center justify-center rounded-lg border border-slate-200 bg-white">
            <Spinner size="lg" />
          </div>
        ) : membersError ? (
          <ErrorState
            title="Unable to load group members"
            message={membersError.message}
            onRetry={() => refetchMembers()}
          />
        ) : (
          <MemberList
            members={members || []}
            currentUserId={user?.user_id}
            isAdmin={isAdmin}
            onRemove={(id, name) => setMemberToRemove({ id, name })}
          />
        )}
      </div>

      {/* Add Member Dialog */}
      <Dialog
        isOpen={isAddModalOpen}
        onClose={() => {
          setIsAddModalOpen(false);
          setAddError(null);
        }}
        title="Add Member to Group"
        description="Invite a registered user to participate in this group's expense pool."
      >
        <form onSubmit={handleAddMember} className="space-y-4">
          {addError && (
            <div className="rounded-md bg-rose-50 p-3 text-sm font-medium text-rose-700 border border-rose-200">
              {addError}
            </div>
          )}

          <Input
            id="member-email"
            type="email"
            label="User Email"
            placeholder="member@example.com"
            value={newMemberEmail}
            onChange={(e) => setNewMemberEmail(e.target.value)}
            required
            helperText="The user must have an active SplitSync AI account."
          />

          <Select
            id="member-role"
            label="Role in Group"
            value={newMemberRole}
            onChange={(e) => setNewMemberRole(e.target.value)}
            options={[
              { label: 'Member (Record payments, split expenses)', value: 'member' },
              { label: 'Admin (Full custody, approval workflows, member management)', value: 'admin' },
            ]}
          />

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setIsAddModalOpen(false);
                setAddError(null);
              }}
              disabled={isAdding}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isAdding}
            >
              Add Member
            </Button>
          </div>
        </form>
      </Dialog>

      {/* Remove Member Confirmation Dialog */}
      <Dialog
        isOpen={Boolean(memberToRemove)}
        onClose={() => {
          setMemberToRemove(null);
          setRemoveError(null);
        }}
        title="Remove Member"
        description="Are you sure you want to remove this member from the group?"
      >
        <div className="space-y-4">
          {removeError && (
            <div className="rounded-md bg-rose-50 p-3 text-sm font-medium text-rose-700 border border-rose-200">
              {removeError}
            </div>
          )}

          <p className="text-sm text-slate-700">
            You are about to remove{' '}
            <strong className="font-semibold text-slate-900">
              {memberToRemove?.name}
            </strong>{' '}
            from this group. Any unsettled debts or outstanding ledger transactions should be settled before removal.
          </p>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setMemberToRemove(null);
                setRemoveError(null);
              }}
              disabled={isRemoving}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="danger"
              size="sm"
              isLoading={isRemoving}
              onClick={handleConfirmRemove}
            >
              Confirm Remove
            </Button>
          </div>
        </div>
      </Dialog>
    </AppShell>
  );
}
