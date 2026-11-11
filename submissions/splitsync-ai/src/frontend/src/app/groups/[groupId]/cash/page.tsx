'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useFetch } from '@/hooks/use-api';
import { AppShell } from '@/components/layout/app-shell';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import { formatPaise, formatDate } from '@/lib/utils';
import { api, ApiError } from '@/lib/api-client';
import type { Group, CashContribution } from '@/lib/types';

export default function GroupCashPage() {
  const params = useParams();
  const groupId = typeof params?.groupId === 'string' ? params.groupId : '';

  const { data: group } = useFetch<Group>(groupId ? `/api/v1/groups/${groupId}` : null);
  const {
    data: cashList,
    error: cashError,
    isLoading: isCashLoading,
    refetch: refetchCash,
  } = useFetch<CashContribution[]>(groupId ? `/api/v1/groups/${groupId}/cash` : null);

  const [amountRupees, setAmountRupees] = React.useState<string>('');
  const [description, setDescription] = React.useState<string>('');
  const [isSubmitting, setIsSubmitting] = React.useState<boolean>(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);
  const [submitSuccess, setSubmitSuccess] = React.useState<string | null>(null);

  const handleCashSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    setSubmitSuccess(null);

    const parsedRupees = parseFloat(amountRupees);
    if (isNaN(parsedRupees) || parsedRupees <= 0) {
      setSubmitError('Please enter a valid cash amount in Rupees.');
      return;
    }

    const amountMinor = Math.round(parsedRupees * 100);

    setIsSubmitting(true);
    try {
      await api.post(`/api/v1/groups/${groupId}/cash`, {
        amount_minor: amountMinor,
        description: description.trim() || undefined,
      });

      setSubmitSuccess(`Cash contribution of ₹${parsedRupees.toLocaleString('en-IN')} logged successfully and submitted for peer approval.`);
      setAmountRupees('');
      setDescription('');
      refetchCash();
    } catch (err) {
      if (err instanceof ApiError) {
        setSubmitError(err.message || 'Failed to submit cash contribution');
      } else if (err instanceof Error) {
        setSubmitError(err.message);
      } else {
        setSubmitError('An unexpected error occurred while logging cash.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppShell title={group ? `${group.name} - Cash Contributions` : 'Cash Contributions'}>
      <div className="space-y-8">
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
          <span className="text-slate-900 font-semibold">Cash Contributions</span>
        </div>

        {/* Top Notice Callout */}
        <div className="rounded-lg border border-indigo-200 bg-indigo-50/70 p-4 text-indigo-950">
          <div className="flex items-start gap-3">
            <div className="p-1.5 rounded-md bg-indigo-100 text-indigo-700 shrink-0 mt-0.5">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div>
              <h4 className="text-sm font-bold text-indigo-900">
                Dual-Custody Physical Cash Policy
              </h4>
              <p className="mt-1 text-xs text-indigo-800 leading-relaxed">
                Cash contributions require independent verification and approval by another active group member before being credited to your balance.
              </p>
            </div>
          </div>
        </div>

        {/* Submission Card */}
        <Card className="border-slate-200 max-w-2xl">
          <CardHeader>
            <CardTitle className="text-lg font-bold text-slate-900">
              Log Physical Cash Contribution
            </CardTitle>
            <CardDescription>
              Record cash handed directly to a group organizer or pool holder.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCashSubmit} className="space-y-4">
              {submitError && (
                <div className="rounded-md bg-rose-50 p-3 text-xs font-medium text-rose-700 border border-rose-200">
                  {submitError}
                </div>
              )}
              {submitSuccess && (
                <div className="rounded-md bg-emerald-50 p-3 text-xs font-medium text-emerald-800 border border-emerald-200">
                  {submitSuccess}
                </div>
              )}

              <Input
                id="cash-amount"
                type="number"
                min="1"
                step="any"
                label="Amount (in ₹ Rupees)"
                placeholder="e.g. 500"
                value={amountRupees}
                onChange={(e) => setAmountRupees(e.target.value)}
                required
                helperText="Will be stored as exact integer paise in Db2."
              />

              <Input
                id="cash-description"
                label="Description / Purpose"
                placeholder="e.g. Paid cash to Rahul at restaurant"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />

              <div className="pt-2">
                <Button
                  type="submit"
                  variant="primary"
                  className="w-full sm:w-auto px-6"
                  isLoading={isSubmitting}
                >
                  Submit for Verification
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* History Table */}
        <Card className="border-slate-200">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg font-bold text-slate-900">
                Cash Contribution History
              </CardTitle>
              <p className="text-xs text-slate-500 mt-1">
                All physical cash declarations and their current peer-approval statuses
              </p>
            </div>
            <button
              onClick={() => refetchCash()}
              className="text-xs font-semibold text-primary-600 hover:text-primary-700 transition-colors flex items-center gap-1"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </CardHeader>

          <CardContent className="p-0">
            {isCashLoading ? (
              <div className="flex h-48 items-center justify-center">
                <Spinner size="lg" />
              </div>
            ) : cashError ? (
              <div className="p-6">
                <ErrorState
                  title="Failed to load cash contributions"
                  message={cashError.message}
                  onRetry={() => refetchCash()}
                />
              </div>
            ) : !cashList || cashList.length === 0 ? (
              <div className="p-8">
                <EmptyState
                  title="No cash contributions logged"
                  description="Physical cash handovers submitted via the form above will appear here awaiting verification."
                />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Amount</TableHead>
                    <TableHead>Contributor</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Submitted On</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {cashList.map((cash) => (
                    <TableRow key={cash.cash_contribution_id}>
                      <TableCell className="font-bold text-slate-900 text-base">
                        {formatPaise(cash.amount_minor)}
                      </TableCell>
                      <TableCell>
                        <span className="font-medium text-slate-800">
                          {cash.display_name || 'Group Member'}
                        </span>
                      </TableCell>
                      <TableCell className="text-slate-600 text-sm">
                        {cash.description || '—'}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={cash.status} />
                      </TableCell>
                      <TableCell className="text-xs text-slate-500">
                        {formatDate(cash.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
