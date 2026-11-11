export const APP_NAME = 'SplitSync AI';
export const CURRENCY_SYMBOL = '₹';
export const DEFAULT_CURRENCY = 'INR';

export const EXPENSE_CATEGORIES = [
  'Food & Dining',
  'Transportation',
  'Accommodation',
  'Entertainment',
  'Shopping',
  'Utilities',
  'Medical',
  'Other',
] as const;

export type ExpenseCategory = (typeof EXPENSE_CATEGORIES)[number];

export const SPLIT_METHODS = ['equal'] as const;
export type SplitMethod = (typeof SPLIT_METHODS)[number];

export const ACCOUNTING_MODES = ['cash', 'accrual'] as const;
export type AccountingMode = (typeof ACCOUNTING_MODES)[number];

export const PAYMENT_STATUSES = [
  'pending',
  'completed',
  'failed',
  'refunded',
] as const;
export type PaymentStatus = (typeof PAYMENT_STATUSES)[number];

export const CASH_STATUSES = [
  'pending_approval',
  'approved',
  'rejected',
  'cancelled',
] as const;
export type CashStatus = (typeof CASH_STATUSES)[number];

export const EXPENSE_STATUSES = [
  'active',
  'settled',
  'voided',
] as const;
export type ExpenseStatus = (typeof EXPENSE_STATUSES)[number];

export const SETTLEMENT_STATUSES = [
  'draft',
  'in_progress',
  'completed',
  'cancelled',
] as const;
export type SettlementStatus = (typeof SETTLEMENT_STATUSES)[number];

export const MEMBER_ROLES = [
  'admin',
  'member',
  'viewer',
] as const;
export type MemberRole = (typeof MEMBER_ROLES)[number];
