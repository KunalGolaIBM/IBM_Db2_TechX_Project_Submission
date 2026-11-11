'use client';

import * as React from 'react';
import { useFetch } from '@/hooks/use-api';
import { ApprovalCard } from './approval-card';
import { Spinner } from '@/components/ui/spinner';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { StatusBadge } from '@/components/ui/status-badge';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { formatPaise, formatDate, formatDateTime } from '@/lib/utils';
import type { PendingApprovalItem } from '@/lib/types';

export interface ApprovalListProps {
  groupId: string;
  currentUserId?: string;
  myMemberId?: string;
}

export function ApprovalList({
  groupId,
  currentUserId,
  myMemberId,
}: ApprovalListProps) {
  const [activeTab, setActiveTab] = React.useState<'pending' | 'history'>('pending');

  const {
    data: pendingItems,
    error: pendingError,
    isLoading: isPendingLoading,
    refetch: refetchPending,
  } = useFetch<PendingApprovalItem[]>(
    groupId ? `/api/v1/groups/${groupId}/approvals/pending` : null
  );

  const {
    data: historyItems,
    error: historyError,
    isLoading: isHistoryLoading,
    refetch: refetchHistory,
  } = useFetch<PendingApprovalItem[]>(
    groupId && activeTab === 'history'
      ? `/api/v1/groups/${groupId}/approvals`
      : null
  );

  const handleDecided = () => {
    refetchPending();
    if (activeTab === 'history') {
      refetchHistory();
    }
  };

  const pendingCount = pendingItems?.length ?? 0;

  return (
    <div className="space-y-6">
      {/* Tabs Switcher */}
      <div className="flex border-b border-slate-200">
        <button
          type="button"
          onClick={() => setActiveTab('pending')}
          className={`flex items-center gap-2 py-3 px-4 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'pending'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>Pending Approvals</span>
          {pendingCount > 0 && (
            <span className="rounded-full bg-amber-100 text-amber-800 px-2 py-0.5 text-xs font-bold">
              {pendingCount}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('history')}
          className={`flex items-center gap-2 py-3 px-4 text-sm font-semibold border-b-2 transition-colors ${
            activeTab === 'history'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <span>Decision History</span>
        </button>
      </div>

      {/* Tab 1: Pending Approvals */}
      {activeTab === 'pending' && (
        <div>
          {isPendingLoading ? (
            <div className="flex h-48 items-center justify-center">
              <Spinner size="lg" />
            </div>
          ) : pendingError ? (
            <ErrorState
              title="Failed to load pending approvals"
              message={pendingError.message}
              onRetry={() => refetchPending()}
            />
          ) : !pendingItems || pendingItems.length === 0 ? (
            <EmptyState
              title="All clear! No pending approvals"
              description="Any physical cash contributions or cash expenses declared by group members will appear here for verification."
            />
          ) : (
            <div className="space-y-4">
              {pendingItems.map((item) => (
                <ApprovalCard
                  key={item.approval_id || item.entity_id}
                  item={item}
                  groupId={groupId}
                  currentUserId={currentUserId}
                  myMemberId={myMemberId}
                  onDecided={handleDecided}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Decision History */}
      {activeTab === 'history' && (
        <div>
          {isHistoryLoading ? (
            <div className="flex h-48 items-center justify-center">
              <Spinner size="lg" />
            </div>
          ) : historyError ? (
            <ErrorState
              title="Failed to load decision history"
              message={historyError.message}
              onRetry={() => refetchHistory()}
            />
          ) : !historyItems || historyItems.length === 0 ? (
            <EmptyState
              title="No past decisions recorded"
              description="Historical approval decisions with dual-custody audit logs will be displayed here."
            />
          ) : (
            <div className="rounded-lg border border-slate-200 bg-white overflow-hidden shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type & Description</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Submitter</TableHead>
                    <TableHead>Decision</TableHead>
                    <TableHead>Decided By</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {historyItems.map((record) => {
                    const isApproved =
                      record.decision?.toUpperCase() === 'APPROVED' ||
                      record.status?.toUpperCase() === 'APPROVED';

                    return (
                      <TableRow key={record.approval_id || record.entity_id}>
                        <TableCell>
                          <div>
                            <span className="font-semibold text-slate-900 block text-sm">
                              {record.description || record.entity_type}
                            </span>
                            <span className="text-[11px] uppercase font-bold text-slate-400">
                              {record.entity_type}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="font-bold text-slate-900">
                          {formatPaise(record.amount_minor)}
                        </TableCell>
                        <TableCell className="text-slate-700">
                          {record.submitter_name}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={isApproved ? 'success' : 'danger'}
                            className="uppercase text-[11px] font-bold"
                          >
                            {record.decision || record.status}
                          </Badge>
                          {record.comment && (
                            <p className="text-xs text-slate-500 mt-1 italic">
                              &ldquo;{record.comment}&rdquo;
                            </p>
                          )}
                        </TableCell>
                        <TableCell className="text-slate-600 text-sm">
                          {record.approver_name || 'Group Member'}
                        </TableCell>
                        <TableCell className="text-xs text-slate-500">
                          {formatDateTime(record.decided_at || record.created_at)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
