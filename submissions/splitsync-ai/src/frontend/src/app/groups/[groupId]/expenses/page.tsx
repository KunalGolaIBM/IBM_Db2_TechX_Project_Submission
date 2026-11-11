'use client';

import * as React from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useFetch } from '@/hooks/use-api';
import { AppShell } from '@/components/layout/app-shell';
import { ExpenseForm, type ExpenseFormData } from '@/components/expenses/expense-form';
import { ExpenseList } from '@/components/expenses/expense-list';
import { Button } from '@/components/ui/button';
import { Dialog } from '@/components/ui/dialog';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/ui/error-state';
import { api, ApiError } from '@/lib/api-client';
import type { Group, GroupMember, Expense } from '@/lib/types';

export default function GroupExpensesPage() {
  const params = useParams();
  const groupId = typeof params?.groupId === 'string' ? params.groupId : '';

  const { data: group } = useFetch<Group>(groupId ? `/api/v1/groups/${groupId}` : null);
  const { data: members } = useFetch<GroupMember[]>(groupId ? `/api/v1/groups/${groupId}/members` : null);
  const {
    data: expenses,
    error: expensesError,
    isLoading: isExpensesLoading,
    refetch: refetchExpenses,
  } = useFetch<Expense[]>(groupId ? `/api/v1/groups/${groupId}/expenses` : null);

  const [isModalOpen, setIsModalOpen] = React.useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = React.useState<boolean>(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  const handleCreateExpense = async (formData: ExpenseFormData) => {
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      await api.post(`/api/v1/groups/${groupId}/expenses`, formData);
      setIsModalOpen(false);
      refetchExpenses();
    } catch (err) {
      if (err instanceof ApiError) {
        setSubmitError(err.message || 'Failed to record expense');
      } else if (err instanceof Error) {
        setSubmitError(err.message);
      } else {
        setSubmitError('An error occurred while creating the expense.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AppShell title={group ? `${group.name} - Expenses` : 'Group Expenses'}>
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
          <span className="text-slate-900 font-semibold">Expenses</span>
        </div>

        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">
              Group Expenses
            </h2>
            <p className="mt-1 text-sm text-slate-600">
              Track shared expenditures, allocate equal splits, and balance ledger debts.
            </p>
          </div>
          <Button
            variant="primary"
            size="md"
            onClick={() => setIsModalOpen(true)}
          >
            <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Expense
          </Button>
        </div>

        {/* Expenses List View */}
        {isExpensesLoading ? (
          <div className="flex h-64 items-center justify-center rounded-lg border border-slate-200 bg-white">
            <Spinner size="lg" />
          </div>
        ) : expensesError ? (
          <ErrorState
            title="Failed to load expenses"
            message={expensesError.message}
            onRetry={() => refetchExpenses()}
          />
        ) : !expenses || expenses.length === 0 ? (
          <EmptyState
            title="No expenses recorded yet"
            description="Log your first shared expense to divide costs accurately among group members."
            action={{
              label: 'Add First Expense',
              onClick: () => setIsModalOpen(true),
            }}
          />
        ) : (
          <ExpenseList expenses={expenses} />
        )}
      </div>

      {/* Add Expense Modal Dialog */}
      <Dialog
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setSubmitError(null);
        }}
        title="Add Group Expense"
        description="Record an expenditure to split equally among selected members."
        className="max-w-xl"
      >
        <ExpenseForm
          members={members || []}
          onSubmit={handleCreateExpense}
          isLoading={isSubmitting}
          errorMessage={submitError}
          onCancel={() => {
            setIsModalOpen(false);
            setSubmitError(null);
          }}
        />
      </Dialog>
    </AppShell>
  );
}
