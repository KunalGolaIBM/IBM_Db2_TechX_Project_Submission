'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useFetch } from '@/hooks/use-api';
import { AppShell } from '@/components/layout/app-shell';
import { BalanceTable } from '@/components/settlement/balance-table';
import { TransferList } from '@/components/settlement/transfer-list';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Spinner } from '@/components/ui/spinner';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { formatPaise, formatDateTime, formatDate } from '@/lib/utils';
import { api, ApiError } from '@/lib/api-client';
import type { Group, MemberBalance, SettlementRun, SettlementItem } from '@/lib/types';

interface LatestSettlementResponse {
  run?: SettlementRun;
  items?: SettlementItem[];
}

export default function GroupSettlementPage() {
  const params = useParams();
  const groupId = typeof params?.groupId === 'string' ? params.groupId : '';

  const { data: group } = useFetch<Group>(groupId ? `/api/v1/groups/${groupId}` : null);

  const {
    data: balances,
    error: balancesError,
    isLoading: isBalancesLoading,
    refetch: refetchBalances,
  } = useFetch<MemberBalance[]>(
    groupId ? `/api/v1/groups/${groupId}/settlements/balances` : null
  );

  const {
    data: latestSettlement,
    error: settlementError,
    isLoading: isSettlementLoading,
    refetch: refetchSettlement,
  } = useFetch<LatestSettlementResponse>(
    groupId ? `/api/v1/groups/${groupId}/settlements/latest` : null
  );

  const {
    data: settlementHistory,
    refetch: refetchHistory,
  } = useFetch<SettlementRun[]>(
    groupId ? `/api/v1/groups/${groupId}/settlements` : null
  );

  const [isCalculating, setIsCalculating] = React.useState<boolean>(false);
  const [calcError, setCalcError] = React.useState<string | null>(null);

  const handleCalculateSettlement = async () => {
    setIsCalculating(true);
    setCalcError(null);

    try {
      await api.post(`/api/v1/groups/${groupId}/settlements`);
      await Promise.all([refetchBalances(), refetchSettlement(), refetchHistory()]);
    } catch (err) {
      if (err instanceof ApiError) {
        setCalcError(err.message || 'Settlement calculation failed');
      } else if (err instanceof Error) {
        setCalcError(err.message);
      } else {
        setCalcError('An unexpected error occurred while calculating the settlement.');
      }
    } finally {
      setIsCalculating(false);
    }
  };

  const handleItemSettled = () => {
    refetchSettlement();
    refetchBalances();
  };

  const currentRun = latestSettlement?.run;
  const recommendedItems = latestSettlement?.items || currentRun?.items || [];

  return (
    <AppShell title={group ? `${group.name} - Settlement` : 'Group Settlement'}>
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
          <span className="text-slate-900 font-semibold">Settlement</span>
        </div>

        {/* Notice Callout */}
        <div className="rounded-lg border border-indigo-200 bg-indigo-50/70 p-4 text-indigo-950">
          <div className="flex items-start gap-3">
            <div className="p-1.5 rounded-md bg-indigo-100 text-indigo-700 shrink-0 mt-0.5">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <div>
              <h4 className="text-sm font-bold text-indigo-900">
                Minimum-Transfer Settlement Engine
              </h4>
              <p className="mt-1 text-xs text-indigo-800 leading-relaxed">
                Settlement transfers are mathematically optimized recommendations to clear all debts in the fewest possible steps. No automated bank transfers or debits are made.
              </p>
            </div>
          </div>
        </div>

        {/* Top Header & Calculate Action */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Debt Reconciliation & Settlement
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Deterministic graph minimization to settle pool debits down to the paisa.
            </p>
          </div>
          <Button
            variant="primary"
            size="md"
            isLoading={isCalculating}
            onClick={handleCalculateSettlement}
          >
            <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            Calculate Settlement
          </Button>
        </div>

        {calcError && (
          <div className="rounded-md bg-rose-50 p-3 text-xs font-medium text-rose-700 border border-rose-200">
            {calcError}
          </div>
        )}

        {/* Section 1: Member Balances */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-bold text-slate-900">
              Current Member Net Balances
            </h3>
            <span className="text-xs text-slate-500">
              Total Contributions vs Total Share Owed
            </span>
          </div>

          {isBalancesLoading ? (
            <div className="flex h-36 items-center justify-center rounded-lg border border-slate-200 bg-white">
              <Spinner size="md" />
            </div>
          ) : balancesError ? (
            <ErrorState
              title="Unable to load member balances"
              message={balancesError.message}
              onRetry={() => refetchBalances()}
            />
          ) : (
            <BalanceTable balances={balances || []} />
          )}
        </div>

        {/* Section 2: Recommended Transfers */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900">
                Recommended Minimum Transfers
              </h3>
              <p className="text-xs text-slate-500">
                Minimal transfer route to resolve all net member positions
              </p>
            </div>
            {currentRun && (
              <Badge variant="info" className="text-xs">
                Run: {currentRun.run_id.slice(0, 8)}
              </Badge>
            )}
          </div>

          {isSettlementLoading ? (
            <div className="flex h-44 items-center justify-center rounded-lg border border-slate-200 bg-white">
              <Spinner size="md" />
            </div>
          ) : settlementError ? (
            <ErrorState
              title="Failed to load settlement transfers"
              message={settlementError.message}
              onRetry={() => refetchSettlement()}
            />
          ) : recommendedItems.length === 0 ? (
            <EmptyState
              title="No settlement calculations yet"
              description="Click 'Calculate Settlement' above to run the optimization algorithm on current group balances."
              action={{
                label: 'Calculate Settlement Now',
                onClick: handleCalculateSettlement,
              }}
            />
          ) : (
            <TransferList
              groupId={groupId}
              runId={currentRun?.run_id}
              items={recommendedItems}
              onItemSettled={handleItemSettled}
            />
          )}
        </div>

        {/* Section 3: Settlement Run History */}
        {settlementHistory && settlementHistory.length > 0 && (
          <div className="space-y-4 pt-4 border-t border-slate-200">
            <h3 className="text-base font-bold text-slate-900">
              Settlement Run History
            </h3>
            <div className="rounded-lg border border-slate-200 bg-white overflow-hidden shadow-sm">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase">
                  <tr>
                    <th className="p-3">Run ID</th>
                    <th className="p-3">Total Amount</th>
                    <th className="p-3">Status</th>
                    <th className="p-3">Calculated On</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-800">
                  {settlementHistory.map((run) => (
                    <tr key={run.run_id} className="hover:bg-slate-50/50">
                      <td className="p-3 font-mono">{run.run_id.slice(0, 8)}</td>
                      <td className="p-3 font-bold">{formatPaise(run.total_minor)}</td>
                      <td className="p-3">
                        <Badge variant="default" className="text-[10px] uppercase">
                          {run.status}
                        </Badge>
                      </td>
                      <td className="p-3 text-slate-500">{formatDateTime(run.calculated_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
