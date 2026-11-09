export interface User {
  user_id: string;
  email: string;
  full_name: string;
}

export interface AuthResponse {
  user: User;
  csrf_token: string;
}

export interface MeResponse {
  user: User;
  csrf_token: string;
}

export interface CategorySpending {
  category: string;
  total_spent: number;
  count: number;
}

export interface MonthlyTrend {
  month: string;
  income: number;
  expenses: number;
  net: number;
}

export interface DashboardSummary {
  user_id: string;
  total_income: number;
  total_expenses: number;
  net_savings: number;
  total_transactions: number;
  posted_transactions?: number;
  pending_transactions?: number;
  pending_anomalies: number;
  top_categories: CategorySpending[];
  monthly_trends: MonthlyTrend[];
  currency: string;
}

export interface Transaction {
  transaction_id: string;
  user_id: string;
  account_id: string;
  category_id: string | null;
  category_name: string;
  merchant: string;
  description: string | null;
  amount: number;
  currency: string;
  transaction_type: 'DEBIT' | 'CREDIT';
  transaction_date: string;
  status: 'POSTED' | 'PENDING';
}

export interface TransactionsResponse {
  user_id: string;
  count: number;
  total_count: number;
  offset: number;
  limit: number;
  transactions: Transaction[];
}

export interface LogoutResponse {
  message: string;
}

export interface EvidenceItem {
  evidence_type: string;
  source_query?: string | null;
  transaction_ids?: string[] | null;
  aggregated_metrics?: Record<string, any> | null;
  notes?: string | null;
}

export interface SearchResultItem {
  transaction_id: string;
  merchant: string;
  category?: string | null;
  amount: number;
  currency?: string;
  date: string;
  transaction_status?: 'POSTED' | 'PENDING' | string;
  description?: string | null;
  similarity_score: number;
  distance: number;
  relevance_label?: string;
  explanation?: string;
  engine?: string;
}

export interface SearchResponse {
  query: string;
  total_results: number;
  results: SearchResultItem[];
  embedding_model: string;
  engine?: string;
}

export interface AnomalyItem {
  alert_id: string;
  transaction_id?: string | null;
  alert_type: string;
  severity: string;
  explanation: string;
  score: number;
  merchant?: string | null;
  category?: string | null;
  amount?: number | null;
  currency?: string;
  date?: string | null;
  status: string;
}

export interface AnomaliesResponse {
  user_id: string;
  total_anomalies: number;
  anomalies: AnomalyItem[];
}

export interface StatisticalContext {
  transaction_amount: number;
  category_average: number;
  multiplier: number;
  alert_type: string;
  severity: string;
  confidence_score: number;
  historical_sample_size?: number;
}

export interface CalculationDetails {
  transaction_amount: number;
  category_name?: string;
  category_average_unadjusted?: number;
  category_multiplier_unadjusted?: number;
  category_baseline_clean?: number;
  category_multiplier_clean?: number;
  category_sample_size?: number;
  merchant_historical_baseline?: number;
  merchant_multiplier?: number;
  merchant_historical_sample_size?: number;
  burst_transaction_count?: number;
  total_burst_amount?: number;
  formula_applied?: string;
}

export interface AnomalyExplainResponse {
  alert_id: string;
  alert_type: string;
  severity: string;
  status: string;
  explanation: string;
  statistical_context: StatisticalContext;
  calculation_details?: CalculationDetails;
  recommendation: string;
  evidence_tx_ids: string[];
  limitations?: string;
}

export interface UpdateAnomalyStatusResponse {
  alert_id: string;
  status: string;
  updated: boolean;
}

// Stage 6: Financial Insights & Reports Models
export interface CategoryChangeItem {
  category_name: string;
  category_id?: string;
  current_amount: number;
  previous_amount: number;
  difference: number;
  percentage_change: number | null;
  tx_count: number;
}

export interface MonthlyMetricComparison {
  current: number;
  previous: number;
  difference: number;
  percentage_change: number | null;
}

export interface RecurringObservationItem {
  merchant: string;
  amount: number;
  category: string;
  frequency: string;
  last_date: string;
}

export interface AnomalyObservationItem {
  alert_id: string;
  alert_type: string;
  severity: string;
  status: string;
  merchant: string;
  amount: number;
  description: string;
}

export interface TopMerchantItem {
  merchant: string;
  category: string;
  total_spent: number;
  tx_count: number;
}

export interface FinancialInsightsData {
  user_id: string;
  month: string;
  previous_month: string;
  available_months: string[];
  currency: string;
  income: MonthlyMetricComparison;
  expenses: MonthlyMetricComparison;
  net_cash_flow: MonthlyMetricComparison;
  savings_rate: number;
  savings_rate_formula: string;
  savings_rate_explanation: string;
  category_changes: CategoryChangeItem[];
  top_categories: Array<{
    category: string;
    total_spent: number;
    count: number;
    share_of_wallet: number;
  }>;
  top_merchants: TopMerchantItem[];
  recurring_observations: RecurringObservationItem[];
  unusual_observations: AnomalyObservationItem[];
  narrative_summary: string;
  generation_mode: string;
  calculation_notes: string[];
  is_empty: boolean;
  insights?: Array<{
    insight_id: string;
    insight_type: string;
    title: string;
    explanation: string;
    generated_at: string;
  }>;
}

export interface MonthlyReportData {
  user_id: string;
  user_name: string;
  user_email: string;
  month: string;
  previous_month: string;
  available_months: string[];
  generated_at: string;
  currency: string;
  summary: {
    total_income: number;
    total_expenses: number;
    net_cash_flow: number;
    savings_rate: number;
    posted_transaction_count: number;
    pending_transaction_count: number;
    currency: string;
  };
  comparison: {
    income: MonthlyMetricComparison;
    expenses: MonthlyMetricComparison;
    net_cash_flow: MonthlyMetricComparison;
  };
  category_breakdown: CategoryChangeItem[];
  top_merchants: TopMerchantItem[];
  recurring_commitments: RecurringObservationItem[];
  anomalies: AnomalyObservationItem[];
  executive_summary: string;
  generation_mode: string;
  methodology_notes: string[];
  is_empty: boolean;
}

// Stage 5: CSV Import Models
export interface ImportSummary {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  duplicate_rows: number;
  total_credits: number;
  total_debits: number;
  net_value: number;
  currency: string;
}

export interface ValidationErrorItem {
  row_number: number;
  raw_data?: Record<string, string>;
  message: string;
  field?: string;
}

export interface DuplicateCandidateItem {
  row_number: number;
  merchant: string;
  amount: number;
  date: string;
  transaction_type: 'DEBIT' | 'CREDIT';
  duplicate_type: 'EXACT' | 'BATCH_DUPLICATE' | 'LIKELY';
  matched_transaction_id?: string;
  reason: string;
}

export interface PreviewRowItem {
  row_number: number;
  date: string | null;
  merchant: string;
  description: string;
  amount: number | null;
  currency: string;
  transaction_type: 'DEBIT' | 'CREDIT';
  category: string;
  category_id: string | null;
  transaction_status: string;
  external_transaction_id?: string | null;
  is_valid: boolean;
  is_duplicate: boolean;
  duplicate_info?: DuplicateCandidateItem | null;
  validation_errors: string[];
}

export interface ImportPreviewResponse {
  import_id: string;
  filename: string;
  headers: string[];
  detected_mapping: Record<string, string | null>;
  summary: ImportSummary;
  validation_errors: ValidationErrorItem[];
  duplicate_candidates: DuplicateCandidateItem[];
  preview_rows: PreviewRowItem[];
}

export interface IndexingStatus {
  status: 'COMPLETED' | 'PARTIAL' | 'FAILED';
  indexed_count: number;
  message: string;
}

export interface ImportCommitResponse {
  import_id: string;
  status: 'COMPLETED' | 'FAILED';
  total_rows: number;
  successful_rows: number;
  skipped_duplicates: number;
  rejected_rows: number;
  imported_transaction_ids: string[];
  completed_at: string;
  indexing_status: IndexingStatus;
}

export interface ImportJobItem {
  import_id: string;
  filename: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  total_rows: number;
  successful_rows: number;
  rejected_rows: number;
  duplicate_rows: number;
  created_at: string;
  completed_at?: string | null;
  indexing_status?: IndexingStatus | null;
}

export interface ChatResponse {
  answer: string;
  intent_detected: string;
  evidence: EvidenceItem[];
  model_used: string;
  mode_active: string;
  is_grounded: boolean;
}

export interface AiStatusResponse {
  status: string;
  mode_active: string;
  engine_name: string;
  llm_configured: boolean;
  llm_model: string;
  vector_engine: string;
  grounding: string;
  capabilities: string[];
}

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  // Set JSON content-type if body is an object or string
  if (options.body && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include', // Always send and receive cookies with Rust API
  });

  let data: any = null;
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      data = await response.text();
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    let errorMessage = `HTTP error ${response.status}`;
    if (data && typeof data === 'object' && typeof data.error === 'string') {
      errorMessage = data.error;
    } else if (data && typeof data === 'object' && typeof data.message === 'string') {
      errorMessage = data.message;
    } else if (typeof data === 'string' && data.length > 0 && data.length < 200) {
      errorMessage = data;
    }

    throw new ApiError(response.status, errorMessage, data);
  }

  return data as T;
}

export const apiClient = {
  auth: {
    async register(payload: { email: string; password: string; full_name: string }): Promise<AuthResponse> {
      return request<AuthResponse>('/api/v1/auth/register', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },

    async login(payload: { email: string; password: string }): Promise<AuthResponse> {
      return request<AuthResponse>('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    },

    async logout(csrfToken?: string | null): Promise<LogoutResponse> {
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      return request<LogoutResponse>('/api/v1/auth/logout', {
        method: 'POST',
        headers,
      });
    },

    async me(): Promise<MeResponse> {
      return request<MeResponse>('/api/v1/auth/me', {
        method: 'GET',
      });
    },
  },

  dashboard: {
    async getSummary(): Promise<DashboardSummary> {
      return request<DashboardSummary>('/api/v1/dashboard/summary', {
        method: 'GET',
      });
    },

    async getTransactions(params: { limit?: number; offset?: number; category?: string; search?: string } = {}): Promise<TransactionsResponse> {
      const searchParams = new URLSearchParams();
      if (params.limit !== undefined) searchParams.set('limit', params.limit.toString());
      if (params.offset !== undefined) searchParams.set('offset', params.offset.toString());
      if (params.category) searchParams.set('category', params.category);
      if (params.search) searchParams.set('search', params.search);

      const qs = searchParams.toString();
      const url = qs ? `/api/v1/transactions?${qs}` : '/api/v1/transactions';
      return request<TransactionsResponse>(url, {
        method: 'GET',
      });
    },
  },

  ai: {
    async chat(message: string, mode: string = 'auto', csrfToken?: string | null): Promise<ChatResponse> {
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      return request<ChatResponse>('/api/v1/ai/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify({ message, mode }),
      });
    },

    async search(query: string, limit: number = 10, csrfToken?: string | null): Promise<SearchResponse> {
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      return request<SearchResponse>('/api/v1/ai/search', {
        method: 'POST',
        headers,
        body: JSON.stringify({ query, limit }),
      });
    },

    async getStatus(): Promise<AiStatusResponse> {
      return request<AiStatusResponse>('/api/v1/ai/status', {
        method: 'GET',
      });
    },
  },

  anomalies: {
    async getAnomalies(params: { status?: string; severity?: string; alert_type?: string } = {}): Promise<AnomaliesResponse> {
      const qs = new URLSearchParams();
      if (params.status) qs.set('status', params.status);
      if (params.severity) qs.set('severity', params.severity);
      if (params.alert_type) qs.set('alert_type', params.alert_type);
      const url = qs.toString() ? `/api/v1/anomalies?${qs.toString()}` : '/api/v1/anomalies';
      return request<AnomaliesResponse>(url, { method: 'GET' });
    },

    async getAnomaly(alertId: string): Promise<AnomalyItem> {
      return request<AnomalyItem>(`/api/v1/anomalies/${alertId}`, { method: 'GET' });
    },

    async explainAnomaly(alertId: string, csrfToken?: string | null): Promise<AnomalyExplainResponse> {
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      return request<AnomalyExplainResponse>(`/api/v1/anomalies/${alertId}/explain`, {
        method: 'POST',
        headers,
      });
    },

    async updateStatus(alertId: string, status: string, csrfToken?: string | null): Promise<UpdateAnomalyStatusResponse> {
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      return request<UpdateAnomalyStatusResponse>(`/api/v1/anomalies/${alertId}/status`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify({ status }),
      });
    },
  },

  imports: {
    async preview(
      filename: string,
      csvContent: string,
      columnMapping?: Record<string, string>,
      csrfToken?: string | null
    ): Promise<ImportPreviewResponse> {
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      return request<ImportPreviewResponse>('/api/v1/imports/preview', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          filename,
          csv_content: csvContent,
          column_mapping: columnMapping,
        }),
      });
    },

    async commit(
      importId: string,
      filename: string,
      csvContent: string,
      columnMapping?: Record<string, string>,
      skipDuplicates: boolean = true,
      accountId?: string,
      csrfToken?: string | null
    ): Promise<ImportCommitResponse> {
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      return request<ImportCommitResponse>('/api/v1/imports/commit', {
        method: 'POST',
        headers,
        body: JSON.stringify({
          import_id: importId,
          filename,
          csv_content: csvContent,
          column_mapping: columnMapping,
          skip_duplicates: skipDuplicates,
          account_id: accountId,
        }),
      });
    },

    async get(importId: string): Promise<ImportJobItem> {
      return request<ImportJobItem>(`/api/v1/imports/${importId}`, { method: 'GET' });
    },

    async getHistory(): Promise<ImportJobItem[]> {
      return request<ImportJobItem[]>('/api/v1/imports/history', { method: 'GET' });
    },

    async retryIndexing(importId: string, csrfToken?: string | null): Promise<IndexingStatus> {
      const headers: Record<string, string> = {};
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
      return request<IndexingStatus>(`/api/v1/imports/${importId}/retry-indexing`, {
        method: 'POST',
        headers,
      });
    },
  },

  insights: {
    async getInsights(month?: string): Promise<FinancialInsightsData> {
      const q = month ? `?month=${encodeURIComponent(month)}` : '';
      return request<FinancialInsightsData>(`/api/v1/insights${q}`, { method: 'GET' });
    },

    async getMonthlyReport(month?: string): Promise<MonthlyReportData> {
      const q = month ? `?month=${encodeURIComponent(month)}` : '';
      return request<MonthlyReportData>(`/api/v1/reports/monthly${q}`, { method: 'GET' });
    },
  },
};
