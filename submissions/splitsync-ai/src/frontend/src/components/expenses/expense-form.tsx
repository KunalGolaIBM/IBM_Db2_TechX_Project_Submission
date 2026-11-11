'use client';

import * as React from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { EXPENSE_CATEGORIES } from '@/lib/constants';
import type { GroupMember } from '@/lib/types';

export interface ExpenseFormData {
  amount_minor: number;
  description: string;
  category: string;
  payment_method: 'DIGITAL' | 'CASH';
  paid_by_member_id: string;
  participant_member_ids: string[];
}

export interface ExpenseFormProps {
  members: GroupMember[];
  onSubmit: (data: ExpenseFormData) => Promise<void> | void;
  isLoading?: boolean;
  errorMessage?: string | null;
  onCancel?: () => void;
}

export function ExpenseForm({
  members,
  onSubmit,
  isLoading = false,
  errorMessage,
  onCancel,
}: ExpenseFormProps) {
  const [amountRupees, setAmountRupees] = React.useState<string>('');
  const [description, setDescription] = React.useState<string>('');
  const [category, setCategory] = React.useState<string>(EXPENSE_CATEGORIES[0]);
  const [paymentMethod, setPaymentMethod] = React.useState<'DIGITAL' | 'CASH'>('DIGITAL');
  const [paidByMemberId, setPaidByMemberId] = React.useState<string>(members[0]?.group_member_id || '');
  const [selectedMemberIds, setSelectedMemberIds] = React.useState<string[]>(
    members.map((m) => m.group_member_id)
  );
  const [validationError, setValidationError] = React.useState<string | null>(null);

  // Sync default paidBy and selected members if members change
  React.useEffect(() => {
    if (members.length > 0 && !paidByMemberId) {
      setPaidByMemberId(members[0].group_member_id);
      setSelectedMemberIds(members.map((m) => m.group_member_id));
    }
  }, [members, paidByMemberId]);

  const handleToggleMember = (memberId: string) => {
    setSelectedMemberIds((prev) =>
      prev.includes(memberId)
        ? prev.filter((id) => id !== memberId)
        : [...prev, memberId]
    );
  };

  const handleSelectAll = () => {
    if (selectedMemberIds.length === members.length) {
      setSelectedMemberIds([]);
    } else {
      setSelectedMemberIds(members.map((m) => m.group_member_id));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const parsedRupees = parseFloat(amountRupees);
    if (isNaN(parsedRupees) || parsedRupees <= 0) {
      setValidationError('Please enter a valid expense amount in Rupees.');
      return;
    }

    if (!description.trim()) {
      setValidationError('Description is required.');
      return;
    }

    if (!paidByMemberId) {
      setValidationError('Please select who paid for this expense.');
      return;
    }

    if (selectedMemberIds.length === 0) {
      setValidationError('Please select at least one participant to split this expense.');
      return;
    }

    const amountMinor = Math.round(parsedRupees * 100);

    await onSubmit({
      amount_minor: amountMinor,
      description: description.trim(),
      category,
      payment_method: paymentMethod,
      paid_by_member_id: paidByMemberId,
      participant_member_ids: selectedMemberIds,
    });
  };

  const displayedError = validationError || errorMessage;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {displayedError && (
        <div className="rounded-md bg-rose-50 p-3 text-xs font-medium text-rose-700 border border-rose-200">
          {displayedError}
        </div>
      )}

      {/* Cash Warning Callout */}
      {paymentMethod === 'CASH' && (
        <div className="rounded-md bg-amber-50 p-3 text-xs text-amber-900 border border-amber-200 flex items-start gap-2">
          <svg className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <span>Cash expenses require independent approval by another member.</span>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          id="expense-amount"
          type="number"
          min="1"
          step="any"
          label="Amount (in ₹ Rupees)"
          placeholder="e.g. 1250.50"
          value={amountRupees}
          onChange={(e) => setAmountRupees(e.target.value)}
          required
        />

        <Select
          id="expense-category"
          label="Category"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          options={EXPENSE_CATEGORIES.map((cat) => ({ label: cat, value: cat }))}
        />
      </div>

      <Input
        id="expense-description"
        label="Description"
        placeholder="e.g. Dinner at Fisherman's Wharf, Uber to airport"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        required
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* Paid By */}
        <Select
          id="paid-by"
          label="Paid By"
          value={paidByMemberId}
          onChange={(e) => setPaidByMemberId(e.target.value)}
          options={members.map((m) => ({
            label: m.display_name,
            value: m.group_member_id,
          }))}
        />

        {/* Payment Method Radio */}
        <div className="space-y-1.5">
          <label className="block text-sm font-medium text-slate-700">
            Payment Method
          </label>
          <div className="flex items-center gap-4 h-10">
            <label className="flex items-center gap-2 text-sm text-slate-800 cursor-pointer">
              <input
                type="radio"
                name="payment_method"
                value="DIGITAL"
                checked={paymentMethod === 'DIGITAL'}
                onChange={() => setPaymentMethod('DIGITAL')}
                className="text-primary-600 focus:ring-primary-500"
              />
              <span>Digital / UPI</span>
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-800 cursor-pointer">
              <input
                type="radio"
                name="payment_method"
                value="CASH"
                checked={paymentMethod === 'CASH'}
                onChange={() => setPaymentMethod('CASH')}
                className="text-primary-600 focus:ring-primary-500"
              />
              <span>Physical Cash</span>
            </label>
          </div>
        </div>
      </div>

      {/* Participant Selection */}
      <div className="space-y-2 pt-2 border-t border-slate-100">
        <div className="flex items-center justify-between">
          <label className="text-sm font-semibold text-slate-900">
            Split Between ({selectedMemberIds.length} of {members.length} selected)
          </label>
          <button
            type="button"
            onClick={handleSelectAll}
            className="text-xs font-semibold text-primary-600 hover:text-primary-700 transition-colors"
          >
            {selectedMemberIds.length === members.length ? 'Deselect All' : 'Select All'}
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-48 overflow-y-auto rounded-md border border-slate-200 p-2 bg-slate-50">
          {members.map((member) => {
            const isChecked = selectedMemberIds.includes(member.group_member_id);
            return (
              <label
                key={member.group_member_id}
                className="flex items-center gap-2.5 p-2 rounded hover:bg-white transition-colors cursor-pointer text-sm"
              >
                <input
                  type="checkbox"
                  checked={isChecked}
                  onChange={() => handleToggleMember(member.group_member_id)}
                  className="rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                />
                <span className="font-medium text-slate-800 truncate">
                  {member.display_name}
                </span>
              </label>
            );
          })}
        </div>
      </div>

      <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
        {onCancel && (
          <Button
            type="button"
            variant="outline"
            size="md"
            onClick={onCancel}
            disabled={isLoading}
          >
            Cancel
          </Button>
        )}
        <Button
          type="submit"
          variant="primary"
          size="md"
          isLoading={isLoading}
        >
          Add Expense
        </Button>
      </div>
    </form>
  );
}
