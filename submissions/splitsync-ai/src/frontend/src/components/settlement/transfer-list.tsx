'use client';

import * as React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { formatPaise, getInitials } from '@/lib/utils';
import { api, ApiError } from '@/lib/api-client';
import type { SettlementItem } from '@/lib/types';

export interface TransferListProps {
  groupId: string;
  runId?: string;
  items: SettlementItem[];
  onItemSettled?: () => void;
}

export function TransferList({
  groupId,
  runId,
  items,
  onItemSettled,
}: TransferListProps) {
  const [settlingItemId, setSettlingItemId] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        No transfers recommended. All member debts are completely balanced and settled.
      </div>
    );
  }

  const handleMarkSettled = async (item: SettlementItem) => {
    const currentRunId = runId || item.run_id;
    if (!currentRunId) return;

    setSettlingItemId(item.item_id);
    setError(null);

    try {
      await api.patch(
        `/api/v1/groups/${groupId}/settlements/${currentRunId}/items/${item.item_id}`,
        { status: 'SETTLED' }
      );
      if (onItemSettled) {
        onItemSettled();
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message || 'Failed to update transfer status');
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred.');
      }
    } finally {
      setSettlingItemId(null);
    }
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-md bg-rose-50 p-3 text-xs font-medium text-rose-700 border border-rose-200">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4">
        {items.map((item) => {
          const isSettled = item.status?.toUpperCase() === 'SETTLED';
          const isUpdating = settlingItemId === item.item_id;

          return (
            <Card
              key={item.item_id}
              className={`border transition-all ${
                isSettled
                  ? 'border-slate-200 bg-slate-50/60 opacity-80'
                  : 'border-slate-200 bg-white hover:border-slate-300 shadow-sm'
              }`}
            >
              <CardContent className="p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
                {/* Visual Transfer Arrow */}
                <div className="flex items-center gap-3 sm:gap-6 flex-1">
                  {/* Debtor */}
                  <div className="flex items-center gap-2.5 min-w-[140px]">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-rose-100 text-xs font-bold text-rose-800">
                      {getInitials(item.from_name || 'Debtor')}
                    </div>
                    <div>
                      <p className="text-xs uppercase font-bold tracking-wider text-rose-600">
                        Owes
                      </p>
                      <h4 className="text-sm font-bold text-slate-900 truncate">
                        {item.from_name || 'Member'}
                      </h4>
                    </div>
                  </div>

                  {/* Transfer Line Indicator */}
                  <div className="flex-1 flex flex-col items-center justify-center px-2">
                    <span className="text-sm sm:text-base font-extrabold text-slate-900">
                      {formatPaise(item.amount_minor)}
                    </span>
                    <div className="w-full flex items-center justify-center my-1">
                      <div className="h-0.5 w-full bg-slate-300" />
                      <div className="w-0 h-0 border-t-4 border-t-transparent border-b-4 border-b-transparent border-l-8 border-l-slate-400 shrink-0 -ml-1" />
                    </div>
                    <span className="text-[11px] text-slate-400 font-medium">
                      Direct Transfer
                    </span>
                  </div>

                  {/* Creditor */}
                  <div className="flex items-center gap-2.5 min-w-[140px] justify-end md:justify-start">
                    <div className="text-right md:text-left">
                      <p className="text-xs uppercase font-bold tracking-wider text-emerald-600">
                        Receives
                      </p>
                      <h4 className="text-sm font-bold text-slate-900 truncate">
                        {item.to_name || 'Member'}
                      </h4>
                    </div>
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-emerald-800">
                      {getInitials(item.to_name || 'Creditor')}
                    </div>
                  </div>
                </div>

                {/* Status & Action */}
                <div className="flex items-center justify-between md:justify-end gap-3 pt-3 md:pt-0 border-t md:border-t-0 border-slate-100 shrink-0">
                  <Badge
                    variant={isSettled ? 'success' : 'warning'}
                    className="uppercase text-[11px] font-bold px-2 py-0.5"
                  >
                    {item.status || 'RECOMMENDED'}
                  </Badge>

                  <Button
                    type="button"
                    variant={isSettled ? 'outline' : 'primary'}
                    size="sm"
                    disabled={isSettled || isUpdating}
                    isLoading={isUpdating}
                    onClick={() => handleMarkSettled(item)}
                    className={
                      isSettled
                        ? 'opacity-60 cursor-not-allowed bg-slate-100 text-slate-500'
                        : ''
                    }
                  >
                    {isSettled ? 'Settled' : 'Mark as Settled'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
