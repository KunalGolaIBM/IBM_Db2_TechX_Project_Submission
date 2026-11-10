use crate::{
    errors::AppError,
    middleware::{AuthContext, MutatingAuthContext},
    state::SharedState,
};
use axum::{extract::State, response::IntoResponse, Json};
use serde::Deserialize;
use serde_json::{json, Value};

#[derive(Deserialize)]
#[allow(dead_code)]
pub struct ChatPayload {
    pub message: String,
    pub mode: Option<String>,
    // Explicitly ignored if passed by client; tenant isolation guarantees server-derived user_id
    pub user_id: Option<String>,
}

#[derive(Deserialize)]
#[allow(dead_code)]
pub struct SearchPayload {
    pub query: String,
    pub limit: Option<u32>,
    // Explicitly ignored if passed by client
    pub user_id: Option<String>,
}

pub async fn chat(
    State(state): State<SharedState>,
    auth: MutatingAuthContext,
    Json(payload): Json<ChatPayload>,
) -> Result<impl IntoResponse, AppError> {
    if payload.message.trim().is_empty() {
        return Err(AppError::BadRequest("Chat message cannot be empty.".into()));
    }
    if payload.message.len() > 2000 {
        return Err(AppError::BadRequest("Chat message exceeds maximum allowed length of 2000 characters.".into()));
    }

    // Tenant isolation: Strictly inject authenticated user_id from session
    let upstream_payload = json!({
        "message": payload.message,
        "user_id": auth.user_id,
        "mode": payload.mode.unwrap_or_else(|| "auto".to_string())
    });

    let url = format!("{}/api/ai/chat", state.config.ai_service_url);
    let res = state
        .http_client
        .post(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .json(&upstream_payload)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to reach AI service: {e}")))?;

    if !res.status().is_success() {
        return Err(AppError::UpstreamError("AI Assistant currently unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse chat response: {e}")))?;

    Ok(Json(data))
}

pub async fn get_status(
    State(state): State<SharedState>,
    _auth: AuthContext,
) -> Result<impl IntoResponse, AppError> {
    let url = format!("{}/api/ai/status", state.config.ai_service_url);
    let res = state
        .http_client
        .get(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to reach AI service: {e}")))?;

    if !res.status().is_success() {
        return Err(AppError::UpstreamError("AI Assistant status currently unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse status response: {e}")))?;

    Ok(Json(data))
}

pub async fn search(
    State(state): State<SharedState>,
    auth: MutatingAuthContext,
    Json(payload): Json<SearchPayload>,
) -> Result<impl IntoResponse, AppError> {
    let q = payload.query.trim();
    if q.is_empty() {
        return Err(AppError::BadRequest("Search query cannot be empty.".into()));
    }
    if q.len() > 500 {
        return Err(AppError::BadRequest("Search query exceeds maximum allowed length of 500 characters.".into()));
    }

    // Tenant isolation: Strictly inject authenticated user_id from session
    let limit = payload.limit.unwrap_or(10).clamp(1, 50);
    let upstream_payload = json!({
        "query": q,
        "user_id": auth.user_id,
        "limit": limit
    });

    let url = format!("{}/api/ai/search", state.config.ai_service_url);
    let res = state
        .http_client
        .post(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .json(&upstream_payload)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to reach semantic search service: {e}")))?;

    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Semantic search currently unavailable.".into()));
    }

    let data: Value = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to parse search response: {e}")))?;

    Ok(Json(data))
}
