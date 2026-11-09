from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# Health
class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

class DbHealthResponse(BaseModel):
    status: str
    database: str
    server_version: str
    latency_ms: float
    total_transactions: int

# Chat & Financial Assistant
class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None
    mode: Optional[str] = "auto"  # "auto", "deterministic", "llm"
    conversation_history: Optional[List[ChatMessage]] = []

class EvidenceItem(BaseModel):
    evidence_type: str
    source_query: Optional[str] = None
    transaction_ids: Optional[List[str]] = []
    aggregated_metrics: Optional[Dict[str, Any]] = {}
    notes: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    intent_detected: str
    evidence: List[EvidenceItem]
    model_used: str
    mode_active: str = "DETERMINISTIC"  # "DETERMINISTIC" or "LLM"
    is_grounded: bool = True

# Vector Search
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    user_id: Optional[str] = None
    limit: int = Field(default=5, ge=1, le=50)

class SearchResultItem(BaseModel):
    transaction_id: str
    merchant: str
    category: Optional[str] = None
    amount: float
    currency: str = "INR"
    date: str
    transaction_status: str = "POSTED"
    description: Optional[str] = None
    similarity_score: float
    distance: float
    relevance_label: str = "High Match"
    explanation: Optional[str] = None
    engine: Optional[str] = "db2_native_vector_cosine"

class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResultItem]
    embedding_model: str
    engine: str = "IBM Db2 Native Vector (COSINE) + LangChain DB2VS"

class IndexRequest(BaseModel):
    user_id: Optional[str] = None

class IndexResponse(BaseModel):
    status: str
    indexed_count: int
    dimension: int
    table: str

# Anomalies
class AnomalyItem(BaseModel):
    alert_id: str
    transaction_id: Optional[str] = None
    alert_type: str
    severity: str
    explanation: str
    score: float
    merchant: Optional[str] = None
    category: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = "INR"
    date: Optional[str] = None
    status: str

class AnomalyListResponse(BaseModel):
    user_id: str
    total_anomalies: int
    anomalies: List[AnomalyItem]

class UpdateAnomalyStatusRequest(BaseModel):
    status: str

class UpdateAnomalyStatusResponse(BaseModel):
    alert_id: str
    status: str
    updated: bool

class AnomalyExplainResponse(BaseModel):
    alert_id: str
    alert_type: str = "UNKNOWN"
    severity: str = "MEDIUM"
    status: str = "NEEDS_REVIEW"
    explanation: str
    statistical_context: Dict[str, Any]
    recommendation: str
    evidence_tx_ids: List[str]
    calculation_details: Optional[Dict[str, Any]] = None
    limitations: Optional[str] = None

# Insights
class InsightItem(BaseModel):
    insight_id: str
    insight_type: str
    title: str
    explanation: str
    generated_at: str

class InsightsResponse(BaseModel):
    user_id: str
    insights: List[InsightItem] = []

class CategoryChangeItem(BaseModel):
    category_name: str
    category_id: Optional[str] = "cat_other"
    current_amount: float
    previous_amount: float
    difference: float
    percentage_change: Optional[float] = None
    tx_count: int

class MonthlyMetricComparison(BaseModel):
    current: float
    previous: float
    difference: float
    percentage_change: Optional[float] = None

class RecurringObservationItem(BaseModel):
    merchant: str
    amount: float
    category: str
    frequency: str = "MONTHLY"
    last_date: str

class AnomalyObservationItem(BaseModel):
    alert_id: str
    alert_type: str
    severity: str
    status: str
    merchant: str
    amount: float
    description: str

class TopMerchantItem(BaseModel):
    merchant: str
    category: str
    total_spent: float
    tx_count: int

class FinancialInsightsResponse(InsightsResponse):
    month: str
    previous_month: str
    available_months: List[str] = []
    currency: str = "INR"
    income: MonthlyMetricComparison
    expenses: MonthlyMetricComparison
    net_cash_flow: MonthlyMetricComparison
    savings_rate: float
    savings_rate_formula: str
    savings_rate_explanation: str
    category_changes: List[CategoryChangeItem] = []
    top_categories: List[Dict[str, Any]] = []
    top_merchants: List[TopMerchantItem] = []
    recurring_observations: List[RecurringObservationItem] = []
    unusual_observations: List[AnomalyObservationItem] = []
    narrative_summary: str
    generation_mode: str = "MODE_A_DETERMINISTIC"
    calculation_notes: List[str] = []
    is_empty: bool = False

class MonthlyReportResponse(BaseModel):
    user_id: str
    user_name: str
    user_email: str
    month: str
    previous_month: str
    available_months: List[str] = []
    generated_at: str
    currency: str = "INR"
    summary: Dict[str, Any]
    comparison: Dict[str, MonthlyMetricComparison]
    category_breakdown: List[CategoryChangeItem] = []
    top_merchants: List[TopMerchantItem] = []
    recurring_commitments: List[RecurringObservationItem] = []
    anomalies: List[AnomalyObservationItem] = []
    executive_summary: str
    generation_mode: str = "MODE_A_DETERMINISTIC"
    methodology_notes: List[str] = []
    is_empty: bool = False

# Imports
class PreviewImportRequest(BaseModel):
    filename: str
    csv_content: str
    column_mapping: Optional[Dict[str, str]] = None

class CommitImportRequest(BaseModel):
    import_id: str
    filename: str
    csv_content: str
    column_mapping: Optional[Dict[str, str]] = None
    skip_duplicates: bool = True
    account_id: Optional[str] = None

