'use client';

import * as React from 'react';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Button } from '@/components/ui/button';

export interface CreateGroupData {
  name: string;
  description: string;
  currency: string;
  split_method: string;
  accounting_mode?: string;
}

export interface GroupFormProps {
  onSubmit: (data: CreateGroupData) => Promise<void> | void;
  isLoading?: boolean;
  onCancel?: () => void;
  errorMessage?: string | null;
}

export function GroupForm({
  onSubmit,
  isLoading = false,
  onCancel,
  errorMessage,
}: GroupFormProps) {
  const [name, setName] = React.useState('');
  const [description, setDescription] = React.useState('');
  const [currency, setCurrency] = React.useState('INR');
  const [splitMethod, setSplitMethod] = React.useState('equal');
  const [accountingMode, setAccountingMode] = React.useState('cash');
  const [validationError, setValidationError] = React.useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const trimmedName = name.trim();
    if (!trimmedName) {
      setValidationError('Group name is required.');
      return;
    }

    await onSubmit({
      name: trimmedName,
      description: description.trim(),
      currency,
      split_method: splitMethod,
      accounting_mode: accountingMode,
    });
  };

  const displayedError = validationError || errorMessage;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {displayedError && (
        <div className="rounded-md bg-rose-50 p-3 text-sm font-medium text-rose-700 border border-rose-200">
          {displayedError}
        </div>
      )}

      <Input
        id="name"
        label="Group Name"
        placeholder="e.g. Goa Trip 2026, Bangalore Flatmates"
        value={name}
        onChange={(e) => {
          setName(e.target.value);
          if (validationError) setValidationError(null);
        }}
        required
      />

      <div className="w-full space-y-1.5">
        <label
          htmlFor="description"
          className="block text-sm font-medium text-slate-700"
        >
          Description
        </label>
        <textarea
          id="description"
          rows={3}
          className="flex w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-colors disabled:cursor-not-allowed disabled:bg-slate-100"
          placeholder="Brief description of the group's purpose..."
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={isLoading}
        />
        <p className="text-xs text-slate-500">
          Optional notes on who is participating and shared budget guidelines.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Select
          id="currency"
          label="Currency"
          value={currency}
          onChange={(e) => setCurrency(e.target.value)}
          disabled={isLoading}
          options={[
            { label: 'INR (₹ - Indian Rupee)', value: 'INR' },
            { label: 'USD ($ - US Dollar)', value: 'USD' },
            { label: 'EUR (€ - Euro)', value: 'EUR' },
          ]}
        />

        <Select
          id="split_method"
          label="Split Method"
          value={splitMethod}
          onChange={(e) => setSplitMethod(e.target.value)}
          disabled={isLoading}
          options={[
            { label: 'Equal Split', value: 'equal' },
          ]}
          helperText="Every expense will be divided equally by default."
        />
      </div>

      <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100">
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
          Create Group
        </Button>
      </div>
    </form>
  );
}
