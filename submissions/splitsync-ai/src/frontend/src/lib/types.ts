export interface User {
  user_id: string;
  display_name: string;
  email: string;
  status: string;
  created_at: string;
}

export interface Group {
  group_id: string;
  name: string;
  description?: string;
  currency: string;
  split_method: string;
  accounting_mode: string;
  status: string;
  member_count?: number;
  created_by: string;
  created_at: string;
}

export interface GroupMember {
  group_member_id: string;
  group_id: string;
  user_id: string;
  display_name: string;
  email?: string;
  role: string;
  status: string;
  joined_at: string;
}

export interface PaymentEvent {
  payment_id: string;
  group_id: string;
  member_id: string;
  member_name?: string;
  provider: string;
  provider_txn_id: string;
  amount_minor: number;
  currency: string;
  status: string;
  source: string;
  paid_at: string;
  created_at: string;
}

export interface CashContribution {
  cash_contribution_id: string;
  group_id: string;
  member_id: string;
  display_name: string;
  amount_minor: number;
  description?: string;
  status: string;
  created_at: string;
}

export interface Expense {
  expense_id: string;
  group_id: string;
  paid_by_member_id: string;
  paid_by_name: string;
  amount_minor: number;
  description: string;
  category: string;
  payment_method: string;
  status: string;
  expense_date: string;
  created_at: string;
  splits?: ExpenseSplit[];
}

export interface PendingApprovalItem {
  approval_id?: string;
  entity_id: string;
  entity_type: 'CASH_CONTRIBUTION' | 'CASH_EXPENSE' | string;
  amount_minor: number;
  description?: string;
  submitter_member_id: string;
  submitter_user_id?: string;
  submitter_name: string;
  status: string;
  created_at: string;
  decision?: string;
  comment?: string;
  decided_at?: string;
  approver_name?: string;
}

export interface TransactionItem {
  transaction_id: string;
  group_id: string;
  member_id?: string;
  member_name?: string;
  type: 'DIGITAL_PAYMENT' | 'CASH_CONTRIBUTION' | 'EXPENSE' | string;
  entity_type: string;
  entity_id: string;
  entry_type?: 'CREDIT' | 'DEBIT' | string;
  amount_minor: number;
  description: string;
  status: string;
  created_at: string;
}

export interface ExpenseSplit {
  split_id: string;
  expense_id: string;
  member_id: string;
  display_name: string;
  share_minor: number;
}

export interface CashApproval {
  approval_id: string;
  entity_type: string;
  entity_id: string;
  approver_member_id: string;
  approver_name: string;
  decision: string;
  comment?: string;
  decided_at: string;
}

export interface LedgerEntry {
  ledger_entry_id: string;
  group_id: string;
  member_id: string;
  entity_type: string;
  entity_id: string;
  entry_type: string;
  amount_minor: number;
  currency: string;
  status: string;
  created_at: string;
}

export interface MemberBalance {
  member_id: string;
  display_name: string;
  email?: string;
  total_contributed_minor: number;
  total_share_minor: number;
  net_balance_minor: number;
}

export interface SettlementRun {
  run_id: string;
  group_id: string;
  total_minor: number;
  currency: string;
  status: string;
  calculated_at: string;
  calculated_by: string;
  items?: SettlementItem[];
}

export interface SettlementItem {
  item_id: string;
  run_id: string;
  from_member_id: string;
  from_name: string;
  to_member_id: string;
  to_name: string;
  amount_minor: number;
  status: string;
}

export interface AuditEvent {
  event_id: string;
  group_id: string;
  actor_id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  details: string | Record<string, unknown>;
  created_at: string;
}

export interface GroupSummary {
  total_contributions_minor: number;
  total_expenses_minor: number;
  member_count: number;
  pending_approvals: number;
}

export interface ApiErrorResponse {
  error: {
    message: string;
    detail?: string;
  };
}

export interface AuthResponse {
  token: string;
  user: User;
}
