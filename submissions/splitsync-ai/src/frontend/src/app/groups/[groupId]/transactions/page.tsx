'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useFetch } from '@/hooks/use-api';
import { AppShell } from '@/components/layout/app-shell';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Select } from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { StatusBadge } from '@/components/ui/status-badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Spinner } from '@/components/ui/spinner';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { formatPaise, formatDateTime } from '@/lib/utils';
import type { Group, GroupMember, TransactionItem } from '@/lib/types';

export default function GroupTransactionsPage() {
  const params = useParams();
  const groupId = typeof params?.groupId === 'string' ? params.groupId : '';

  const { data: group } = useFetch<Group>(groupId ? `/api/v1/groups/${groupId}` : null);
  const { data: members } = useFetch<GroupMember[]>(
    groupId ? `/api/v1/groups/${groupId}/members` : null
  );
  const {
    data: transactions,
    error: transactionsError,
    isLoading: isTransactionsLoading,
    refetch: refetchTransactions,
  } = useFetch<TransactionItem[]>(
    groupId ? `/api/v1/groups/${groupId}/transactions` : null
  );

  // Filters state
  const [filterType, setFilterType] = React.useState<string>('ALL');
  const [filterStatus, setFilterStatus] = React.useState<string>('ALL');
  const [filterMember, setFilterMember] = React.useState<string>('ALL');

  // Filtered list
  const filteredTransactions = React.useMemo(() => {
    if (!transactions) return [];

    return transactions.filter((tx) => {
      // Filter by Type
      if (filterType !== 'ALL') {
        const txType = (tx.type || tx.entity_type || '').toUpperCase();
        if (!txType.includes(filterType.toUpperCase())) {
          return false;
        }
      }

      // Filter by Status
      if (filterStatus !== 'ALL') {
        const status = (tx.status || '').toUpperCase();
        if (filterStatus === 'VERIFIED') {
          if (!['APPROVED', 'VERIFIED', 'COMPLETED', 'POSTED'].includes(status)) {
            return false;
          }
        } else if (filterStatus === 'PENDING') {
          if (!['PENDING', 'PENDING_APPROVAL', 'DRAFT'].includes(status)) {
            return false;
          }
        } else if (filterStatus === 'REJECTED') {
          if (!['REJECTED', 'FAILED', 'CANCELLED', 'VOIDED'].includes(status)) {
            return false;
          }
        }
      }

      // Filter by Member
      if (filterMember !== 'ALL') {
        if (tx.member_id !== filterMember) {
          return false;
        }
      }

      return true;
    });
  }, [transactions, filterType, filterStatus, filterMember]);

  return (
    <AppShell title={group ? `${group.name} - Transactions` : 'Transactions History'}>
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
          <span className="text-slate-900 font-semibold">Transactions</span>
        </div>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Transaction History
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Audit trail of all digital payments, physical cash claims, and shared expense entries.
            </p>
          </div>
          <button
            onClick={() => refetchTransactions()}
            className="text-xs font-semibold text-primary-600 hover:text-primary-700 transition-colors flex items-center gap-1.5 self-start sm:self-auto"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh Ledger
          </button>
        </div>

        {/* Filters Card */}
        <Card className="border-slate-200 bg-white">
          <CardContent className="p-4">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Select
                id="filter-type"
                label="Transaction Type"
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                options={[
                  { label: 'All Types', value: 'ALL' },
                  { label: 'Digital Payment', value: 'PAYMENT' },
                  { label: 'Cash Contribution', value: 'CASH' },
                  { label: 'Expense', value: 'EXPENSE' },
                ]}
              />

              <Select
                id="filter-status"
                label="Status"
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                options={[
                  { label: 'All Statuses', value: 'ALL' },
                  { label: 'Verified / Approved', value: 'VERIFIED' },
                  { label: 'Pending Review', value: 'PENDING' },
                  { label: 'Rejected / Cancelled', value: 'REJECTED' },
                ]}
              />

              <Select
                id="filter-member"
                label="Member"
                value={filterMember}
                onChange={(e) => setFilterMember(e.target.value)}
                options={[
                  { label: 'All Members', value: 'ALL' },
                  ...(members?.map((m) => ({
                    label: m.display_name,
                    value: m.group_member_id,
                  })) || []),
                ]}
              />
            </div>
          </CardContent>
        </Card>

        {/* Transactions Table */}
        <Card className="border-slate-200">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <CardTitle className="text-base font-bold text-slate-900">
              Ledger Entries ({filteredTransactions.length})
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {isTransactionsLoading ? (
              <div className="flex h-56 items-center justify-center">
                <Spinner size="lg" />
              </div>
            ) : transactionsError ? (
              <div className="p-6">
                <ErrorState
                  title="Failed to load transaction history"
                  message={transactionsError.message}
                  onRetry={() => refetchTransactions()}
                />
              </div>
            ) : filteredTransactions.length === 0 ? (
              <div className="p-8">
                <EmptyState
                  title="No transactions match your filters"
                  description="Try clearing or adjusting your type, status, or member filters to view entries."
                  action={
                    filterType !== 'ALL' || filterStatus !== 'ALL' || filterMember !== 'ALL'
                      ? {
                          label: 'Reset Filters',
                          onClick: () => {
                            setFilterType('ALL');
                            setFilterStatus('ALL');
                            setFilterMember('ALL');
                          },
                        }
                      : undefined
                  }
                />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date & Time</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Member</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTransactions.map((tx) => {
                    const txType = (tx.type || tx.entity_type || '').toUpperCase();
                    const isCredit =
                      tx.entry_type === 'CREDIT' ||
                      txType.includes('PAYMENT') ||
                      txType.includes('CASH');

                    let badgeVariant: 'info' | 'success' | 'warning' | 'default' = 'default';
                    if (txType.includes('PAYMENT')) badgeVariant = 'info';
                    else if (txType.includes('CASH')) badgeVariant = 'warning';
                    else if (txType.includes('EXPENSE')) badgeVariant = 'default';

                    return (
                      <TableRow key={tx.transaction_id || tx.entity_id}>
                        <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                          {formatDateTime(tx.created_at)}
                        </TableCell>
                        <TableCell>
                          <Badge variant={badgeVariant} className="text-[10px] uppercase font-bold">
                            {tx.type || tx.entity_type}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-medium text-slate-900 max-w-xs truncate">
                          {tx.description || tx.entity_type}
                        </TableCell>
                        <TableCell className="text-slate-700 text-sm">
                          {tx.member_name || 'Member'}
                        </TableCell>
                        <TableCell
                          className={`text-right font-bold text-base whitespace-nowrap ${
                            isCredit ? 'text-emerald-600' : 'text-rose-600'
                          }`}
                        >
                          {isCredit ? '+' : '-'} {formatPaise(tx.amount_minor)}
                        </TableCell>
                        <TableCell>
                          <StatusBadge status={tx.status} />
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
