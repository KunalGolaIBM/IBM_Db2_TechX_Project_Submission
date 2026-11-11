'use client';

import * as React from 'react';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { formatPaise, getInitials } from '@/lib/utils';
import type { MemberBalance } from '@/lib/types';

export interface BalanceTableProps {
  balances: MemberBalance[];
  isLoading?: boolean;
}

export function BalanceTable({ balances, isLoading = false }: BalanceTableProps) {
  if (balances.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        No balance records found for group members.
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white overflow-hidden shadow-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Member</TableHead>
            <TableHead>Email</TableHead>
            <TableHead className="text-right">Total Contributed</TableHead>
            <TableHead className="text-right">Total Share Owed</TableHead>
            <TableHead className="text-right">Net Balance</TableHead>
            <TableHead className="text-center">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {balances.map((balance) => {
            const net = balance.net_balance_minor;
            const isPositive = net > 0;
            const isNegative = net < 0;
            const isSettled = net === 0;

            return (
              <TableRow key={balance.member_id}>
                <TableCell>
                  <div className="flex items-center space-x-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary-100 text-xs font-semibold text-primary-700">
                      {getInitials(balance.display_name)}
                    </div>
                    <span className="font-semibold text-slate-900">
                      {balance.display_name}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="text-slate-600 text-xs">
                  {balance.email || '—'}
                </TableCell>
                <TableCell className="text-right font-medium text-slate-800">
                  {formatPaise(balance.total_contributed_minor)}
                </TableCell>
                <TableCell className="text-right font-medium text-slate-800">
                  {formatPaise(balance.total_share_minor)}
                </TableCell>
                <TableCell
                  className={`text-right font-bold text-base whitespace-nowrap ${
                    isPositive
                      ? 'text-emerald-600'
                      : isNegative
                      ? 'text-rose-600'
                      : 'text-slate-500'
                  }`}
                >
                  {isPositive ? `+${formatPaise(net)}` : isNegative ? `-${formatPaise(Math.abs(net))}` : formatPaise(0)}
                </TableCell>
                <TableCell className="text-center">
                  {isPositive && (
                    <Badge variant="success" className="font-bold text-[11px]">
                      To Receive
                    </Badge>
                  )}
                  {isNegative && (
                    <Badge variant="danger" className="font-bold text-[11px]">
                      Owes
                    </Badge>
                  )}
                  {isSettled && (
                    <Badge variant="default" className="text-slate-500 font-medium text-[11px]">
                      Settled
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
