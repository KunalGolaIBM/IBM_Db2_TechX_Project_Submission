'use client';

import * as React from 'react';
import { Badge } from '@/components/ui/badge';
import { StatusBadge } from '@/components/ui/status-badge';
import { formatPaise, formatDate } from '@/lib/utils';
import type { Expense } from '@/lib/types';

export interface ExpenseListProps {
  expenses: Expense[];
}

export function ExpenseList({ expenses }: ExpenseListProps) {
  const [expandedId, setExpandedId] = React.useState<string | null>(null);

  if (expenses.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        No expenses recorded yet.
      </div>
    );
  }

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-3">
      {expenses.map((expense) => {
        const isExpanded = expandedId === expense.expense_id;
        const isCash = expense.payment_method?.toUpperCase() === 'CASH';

        return (
          <div
            key={expense.expense_id}
            className="rounded-lg border border-slate-200 bg-white transition-all hover:border-slate-300 shadow-sm overflow-hidden"
          >
            {/* Top Row / Main Summary */}
            <div className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div className="flex items-start gap-3.5">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-indigo-50 text-indigo-600 font-semibold text-sm">
                  {expense.category ? expense.category.slice(0, 2).toUpperCase() : 'EX'}
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <h4 className="text-base font-bold text-slate-900">
                      {expense.description}
                    </h4>
                    <Badge variant="default" className="text-[11px]">
                      {expense.category}
                    </Badge>
                    <Badge
                      variant={isCash ? 'warning' : 'info'}
                      className="text-[10px] uppercase font-semibold"
                    >
                      {expense.payment_method || 'DIGITAL'}
                    </Badge>
                    <StatusBadge status={expense.status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    Paid by <strong className="font-semibold text-slate-700">{expense.paid_by_name || 'Member'}</strong> on{' '}
                    {formatDate(expense.expense_date || expense.created_at)}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-between sm:justify-end gap-4 shrink-0 border-t sm:border-t-0 pt-3 sm:pt-0 border-slate-100">
                <div className="text-right">
                  <div className="text-lg font-bold text-slate-900">
                    {formatPaise(expense.amount_minor)}
                  </div>
                  {expense.splits && (
                    <span className="text-[11px] text-slate-500">
                      Split across {expense.splits.length} {expense.splits.length === 1 ? 'person' : 'people'}
                    </span>
                  )}
                </div>

                <button
                  type="button"
                  onClick={() => toggleExpand(expense.expense_id)}
                  className="p-1.5 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                  aria-label={isExpanded ? 'Collapse split details' : 'Expand split details'}
                >
                  <svg
                    className={`w-5 h-5 transition-transform duration-200 ${
                      isExpanded ? 'rotate-180 text-primary-600' : ''
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Expanded Splits Breakdown */}
            {isExpanded && (
              <div className="bg-slate-50/75 border-t border-slate-100 p-4 sm:px-5">
                <h5 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-3">
                  Individual Split Breakdown
                </h5>
                {expense.splits && expense.splits.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                    {expense.splits.map((split) => (
                      <div
                        key={split.split_id || split.member_id}
                        className="flex items-center justify-between p-2.5 rounded-md bg-white border border-slate-200 text-xs"
                      >
                        <span className="font-medium text-slate-800 truncate mr-2">
                          {split.display_name || split.member_id}
                        </span>
                        <span className="font-semibold text-slate-900 shrink-0">
                          {formatPaise(split.share_minor)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic">
                    Split details not available for this entry.
                  </p>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
