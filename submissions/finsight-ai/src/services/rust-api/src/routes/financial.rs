use crate::{
    errors::AppError,
    middleware::{AuthContext, MutatingAuthContext},
    state::SharedState,
};
use axum::{
    extract::{Path, Query, State},
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use serde_json::Value;

#[derive(Deserialize)]
pub struct TransactionQueryParams {
    pub limit: Option<u32>,
    pub offset: Option<u32>,
    pub category: Option<String>,
    pub category_id: Option<String>,
    pub search: Option<String>,
}

#[derive(Deserialize)]
pub struct AnomalyQueryParams {
    pub status: Option<String>,
    pub severity: Option<String>,
    pub alert_type: Option<String>,
}

#[derive(Deserialize)]
pub struct UpdateAnomalyStatusPayload {
    pub status: String,
}

pub async fn get_dashboard_summary(
    State(state): State<SharedState>,
    auth: AuthContext,
) -> Result<impl IntoResponse, AppError> {
    let url = format!(
        "{}/api/internal/dashboard/summary?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&auth.user_id)
    );

    let res = state
        .http_client
        .get(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to reach financial data service: {e}")))?;

    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Financial summary unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse summary response: {e}")))?;

    Ok(Json(data))
}

pub async fn get_transactions(
    State(state): State<SharedState>,
    auth: AuthContext,
    Query(params): Query<TransactionQueryParams>,
) -> Result<impl IntoResponse, AppError> {
    let limit = params.limit.unwrap_or(50).clamp(1, 200);
    let offset = params.offset.unwrap_or(0);

    let mut url = format!(
        "{}/api/internal/transactions?user_id={}&limit={}&offset={}",
        state.config.ai_service_url,
        urlencoding::encode(&auth.user_id),
        limit,
        offset
    );

    let effective_cat = params.category.or(params.category_id);
    if let Some(cat) = effective_cat {
        if !cat.trim().is_empty() {
            url.push_str(&format!("&category={}", urlencoding::encode(cat.trim())));
        }
    }

    if let Some(s) = params.search {
        if !s.trim().is_empty() {
            url.push_str(&format!("&search={}", urlencoding::encode(s.trim())));
        }
    }

    let res = state
        .http_client
        .get(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to fetch transactions: {e}")))?;

    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Transactions list unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse transactions response: {e}")))?;

    Ok(Json(data))
}

pub async fn get_anomalies(
    State(state): State<SharedState>,
    auth: AuthContext,
    Query(params): Query<AnomalyQueryParams>,
) -> Result<impl IntoResponse, AppError> {
    let mut url = format!(
        "{}/api/ai/anomalies?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&auth.user_id)
    );
    if let Some(s) = params.status {
        url.push_str(&format!("&status={}", urlencoding::encode(&s)));
    }
    if let Some(sev) = params.severity {
        url.push_str(&format!("&severity={}", urlencoding::encode(&sev)));
    }
    if let Some(at) = params.alert_type {
        url.push_str(&format!("&alert_type={}", urlencoding::encode(&at)));
    }

    let res = state
        .http_client
        .get(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to fetch anomalies: {e}")))?;

    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Anomalies unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse anomalies response: {e}")))?;

    Ok(Json(data))
}

pub async fn get_anomaly(
    State(state): State<SharedState>,
    auth: AuthContext,
    Path(alert_id): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    let url = format!(
        "{}/api/ai/anomalies/{}?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&alert_id),
        urlencoding::encode(&auth.user_id)
    );

    let res = state
        .http_client
        .get(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to fetch anomaly: {e}")))?;

    if res.status().as_u16() == 404 {
        return Err(AppError::NotFound("Anomaly alert not found.".into()));
    }
    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Anomaly details unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse anomaly response: {e}")))?;

    Ok(Json(data))
}

pub async fn update_anomaly_status(
    State(state): State<SharedState>,
    auth: MutatingAuthContext,
    Path(alert_id): Path<String>,
    Json(payload): Json<UpdateAnomalyStatusPayload>,
) -> Result<impl IntoResponse, AppError> {
    let s = payload.status.trim().to_uppercase();
    if !["NEEDS_REVIEW", "REVIEWED", "DISMISSED", "ACTIVE"].contains(&s.as_str()) {
        return Err(AppError::BadRequest("Invalid review status. Allowed values: NEEDS_REVIEW, REVIEWED, DISMISSED.".into()));
    }

    let url = format!(
        "{}/api/ai/anomalies/{}/status?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&alert_id),
        urlencoding::encode(&auth.user_id)
    );

    let upstream_payload = serde_json::json!({
        "status": s
    });

    let res = state
        .http_client
        .patch(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .json(&upstream_payload)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to update anomaly status: {e}")))?;

    if res.status().as_u16() == 404 {
        return Err(AppError::NotFound("Anomaly alert not found or access denied.".into()));
    }
    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Failed to update anomaly review status.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse status update response: {e}")))?;

    Ok(Json(data))
}

#[derive(Deserialize)]
pub struct InsightsQueryParams {
    pub month: Option<String>,
}

pub async fn get_insights(
    State(state): State<SharedState>,
    auth: AuthContext,
    Query(params): Query<InsightsQueryParams>,
) -> Result<impl IntoResponse, AppError> {
    let mut url = format!(
        "{}/api/ai/insights?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&auth.user_id)
    );
    if let Some(m) = &params.month {
        if !m.trim().is_empty() {
            url.push_str(&format!("&month={}", urlencoding::encode(m.trim())));
        }
    }

    let res = state
        .http_client
        .get(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to fetch insights: {e}")))?;

    if res.status().as_u16() == 400 {
        let err_body: Value = res.json().await.unwrap_or_default();
        let detail = err_body["detail"].as_str().unwrap_or("Invalid month parameter.");
        return Err(AppError::BadRequest(detail.into()));
    }
    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Insights unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse insights response: {e}")))?;

    Ok(Json(data))
}

pub async fn get_monthly_report(
    State(state): State<SharedState>,
    auth: AuthContext,
    Query(params): Query<InsightsQueryParams>,
) -> Result<impl IntoResponse, AppError> {
    let mut url = format!(
        "{}/api/ai/reports/monthly?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&auth.user_id)
    );
    if let Some(m) = &params.month {
        if !m.trim().is_empty() {
            url.push_str(&format!("&month={}", urlencoding::encode(m.trim())));
        }
    }

    let res = state
        .http_client
        .get(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to fetch monthly report: {e}")))?;

    if res.status().as_u16() == 400 {
        let err_body: Value = res.json().await.unwrap_or_default();
        let detail = err_body["detail"].as_str().unwrap_or("Invalid month parameter.");
        return Err(AppError::BadRequest(detail.into()));
    }
    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Monthly report unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse monthly report response: {e}")))?;

    Ok(Json(data))
}

pub async fn explain_anomaly(
    State(state): State<SharedState>,
    auth: MutatingAuthContext,
    Path(alert_id): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    let url = format!(
        "{}/api/ai/anomalies/{}/explain?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&alert_id),
        urlencoding::encode(&auth.user_id)
    );

    let res = state
        .http_client
        .post(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to explain anomaly: {e}")))?;

    if res.status().as_u16() == 404 {
        return Err(AppError::NotFound("Anomaly alert not found.".into()));
    }
    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Failed to generate anomaly explanation.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse explanation response: {e}")))?;

    Ok(Json(data))
}

#[derive(Deserialize)]
pub struct PreviewImportPayload {
    pub filename: String,
    pub csv_content: String,
    pub column_mapping: Option<std::collections::HashMap<String, String>>,
}

#[derive(Deserialize)]
pub struct CommitImportPayload {
    pub import_id: String,
    pub filename: String,
    pub csv_content: String,
    pub column_mapping: Option<std::collections::HashMap<String, String>>,
    pub skip_duplicates: Option<bool>,
    pub account_id: Option<String>,
}

pub async fn preview_import(
    State(state): State<SharedState>,
    auth: MutatingAuthContext,
    Json(payload): Json<PreviewImportPayload>,
) -> Result<impl IntoResponse, AppError> {
    if payload.filename.trim().is_empty() {
        return Err(AppError::BadRequest("Filename cannot be empty.".into()));
    }
    if payload.csv_content.trim().is_empty() {
        return Err(AppError::BadRequest("CSV content cannot be empty.".into()));
    }
    if payload.csv_content.len() > 5 * 1024 * 1024 {
        return Err(AppError::BadRequest("CSV content exceeds maximum size of 5 MB.".into()));
    }

    let url = format!(
        "{}/api/ai/imports/preview?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&auth.user_id)
    );

    let upstream_payload = serde_json::json!({
        "filename": payload.filename,
        "csv_content": payload.csv_content,
        "column_mapping": payload.column_mapping
    });

    let res = state
        .http_client
        .post(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .json(&upstream_payload)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to reach import preview service: {e}")))?;

    if res.status().as_u16() == 400 {
        let err_body: Value = res.json().await.unwrap_or_default();
        let msg = err_body["detail"].as_str().unwrap_or("Invalid CSV format or parameters.");
        return Err(AppError::BadRequest(msg.into()));
    }

    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Import preview service unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse preview response: {e}")))?;

    Ok(Json(data))
}

pub async fn commit_import(
    State(state): State<SharedState>,
    auth: MutatingAuthContext,
    Json(payload): Json<CommitImportPayload>,
) -> Result<impl IntoResponse, AppError> {
    if payload.import_id.trim().is_empty() {
        return Err(AppError::BadRequest("Import ID cannot be empty.".into()));
    }
    if payload.filename.trim().is_empty() {
        return Err(AppError::BadRequest("Filename cannot be empty.".into()));
    }
    if payload.csv_content.trim().is_empty() {
        return Err(AppError::BadRequest("CSV content cannot be empty.".into()));
    }

    let url = format!(
        "{}/api/ai/imports/commit?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&auth.user_id)
    );

    let upstream_payload = serde_json::json!({
        "import_id": payload.import_id,
        "filename": payload.filename,
        "csv_content": payload.csv_content,
        "column_mapping": payload.column_mapping,
        "skip_duplicates": payload.skip_duplicates.unwrap_or(true),
        "account_id": payload.account_id
    });

    let res = state
        .http_client
        .post(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .json(&upstream_payload)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to reach import commit service: {e}")))?;

    if res.status().as_u16() == 409 {
        return Err(AppError::Conflict("Import is currently being processed.".into()));
    }
    if res.status().as_u16() == 400 {
        let err_body: Value = res.json().await.unwrap_or_default();
        let msg = err_body["detail"].as_str().unwrap_or("Invalid import request.");
        return Err(AppError::BadRequest(msg.into()));
    }
    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Import commit failed.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse commit response: {e}")))?;

    Ok(Json(data))
}

pub async fn get_import(
    State(state): State<SharedState>,
    auth: AuthContext,
    Path(import_id): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    let url = format!(
        "{}/api/ai/imports/{}?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&import_id),
        urlencoding::encode(&auth.user_id)
    );

    let res = state
        .http_client
        .get(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to fetch import job: {e}")))?;

    if res.status().as_u16() == 404 {
        return Err(AppError::NotFound("Import job not found or access denied.".into()));
    }
    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Import job details unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse import details: {e}")))?;

    Ok(Json(data))
}

pub async fn list_imports(
    State(state): State<SharedState>,
    auth: AuthContext,
) -> Result<impl IntoResponse, AppError> {
    let url = format!(
        "{}/api/ai/imports/history?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&auth.user_id)
    );

    let res = state
        .http_client
        .get(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to fetch import history: {e}")))?;

    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Import history unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse import history: {e}")))?;

    Ok(Json(data))
}

pub async fn retry_import_indexing(
    State(state): State<SharedState>,
    auth: MutatingAuthContext,
    Path(import_id): Path<String>,
) -> Result<impl IntoResponse, AppError> {
    let url = format!(
        "{}/api/ai/imports/{}/retry-indexing?user_id={}",
        state.config.ai_service_url,
        urlencoding::encode(&import_id),
        urlencoding::encode(&auth.user_id)
    );

    let res = state
        .http_client
        .post(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to reach retry indexing service: {e}")))?;

    if res.status().as_u16() == 404 {
        return Err(AppError::NotFound("Import job not found or access denied.".into()));
    }
    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Retry indexing failed.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse indexing response: {e}")))?;

    Ok(Json(data))
}
