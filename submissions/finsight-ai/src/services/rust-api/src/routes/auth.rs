use crate::{
    auth::{Crypto, SessionManager, SESSION_COOKIE_NAME},
    errors::AppError,
    middleware::{AuthContext, MutatingAuthContext},
    state::SharedState,
};
use axum::{
    extract::State,
    http::HeaderMap,
    response::IntoResponse,
    Json,
};
use axum_extra::extract::CookieJar;
use serde::{Deserialize, Serialize};
use serde_json::json;
use uuid::Uuid;

#[derive(Deserialize)]
pub struct RegisterRequest {
    pub email: String,
    pub password: String,
    pub full_name: String,
}

#[derive(Deserialize)]
pub struct LoginRequest {
    pub email: String,
    pub password: String,
}

#[derive(Serialize)]
pub struct UserInfo {
    pub user_id: String,
    pub email: String,
    pub full_name: String,
}

#[derive(Serialize)]
pub struct AuthResponse {
    pub user: UserInfo,
    pub csrf_token: String,
}

#[derive(Deserialize)]
struct InternalUserResponse {
    pub user_id: String,
    pub email: String,
    pub full_name: String,
    pub password_hash: Option<String>,
    pub is_active: bool,
}

pub async fn register(
    State(state): State<SharedState>,
    jar: CookieJar,
    headers: HeaderMap,
    Json(payload): Json<RegisterRequest>,
) -> Result<impl IntoResponse, AppError> {
    let client_ip = crate::middleware::extract_client_ip_from_headers(&headers);
    if !state.auth_rate_limiter.check(client_ip).await {
        return Err(AppError::TooManyRequests("Too many registration attempts. Please wait.".into()));
    }

    let email = payload.email.trim().to_lowercase();
    let full_name = payload.full_name.trim().to_string();

    if email.is_empty() || !email.contains('@') {
        return Err(AppError::BadRequest("Invalid email address format.".into()));
    }
    if payload.password.len() < 8 {
        return Err(AppError::BadRequest("Password must be at least 8 characters long.".into()));
    }
    if full_name.len() < 2 {
        return Err(AppError::BadRequest("Full name must be at least 2 characters long.".into()));
    }

    // Hash password with Argon2id OWASP parameters
    let password_hash = Crypto::hash_password(&payload.password)?;

    let user_id = format!("usr_{}", Uuid::new_v4().simple());

    // Register user in Db2 via internal AI service
    let create_url = format!("{}/api/internal/users", state.config.ai_service_url);
    let create_payload = json!({
        "user_id": user_id,
        "email": email,
        "full_name": full_name,
        "password_hash": password_hash
    });

    let res = state
        .http_client
        .post(&create_url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .json(&create_payload)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to reach user service: {e}")))?;

    if res.status().as_u16() == 409 {
        return Err(AppError::Conflict("An account with this email address already exists.".into()));
    }
    if !res.status().is_success() {
        return Err(AppError::Internal("Failed to create user account.".into()));
    }

    // Generate CSPRNG tokens with deterministic session-bound CSRF derivation
    let raw_session_token = Crypto::generate_secure_token();
    let session_token_hash = Crypto::sha256_hex(&raw_session_token);

    let raw_csrf_token = Crypto::derive_csrf_token(&state.config.csrf_secret, &raw_session_token)?;
    let csrf_token_hash = Crypto::sha256_hex(&raw_csrf_token);

    let user_agent = headers.get("user-agent").and_then(|v| v.to_str().ok());

    SessionManager::persist_session(
        &state.http_client,
        &state.config.ai_service_url,
        &state.config.ai_service_internal_token,
        &session_token_hash,
        &csrf_token_hash,
        &user_id,
        state.config.session_ttl_hours,
        user_agent,
        None,
    )
    .await?;

    let cookie = SessionManager::build_session_cookie(
        &raw_session_token,
        state.config.cookie_secure,
        state.config.session_ttl_hours,
    );

    let response = AuthResponse {
        user: UserInfo {
            user_id,
            email,
            full_name,
        },
        csrf_token: raw_csrf_token,
    };

    Ok((jar.add(cookie), Json(response)))
}

pub async fn login(
    State(state): State<SharedState>,
    jar: CookieJar,
    headers: HeaderMap,
    Json(payload): Json<LoginRequest>,
) -> Result<impl IntoResponse, AppError> {
    let client_ip = crate::middleware::extract_client_ip_from_headers(&headers);
    if !state.auth_rate_limiter.check(client_ip).await {
        return Err(AppError::TooManyRequests("Too many login attempts. Please wait.".into()));
    }

    let email = payload.email.trim().to_lowercase();
    if email.is_empty() || payload.password.is_empty() {
        return Err(AppError::Unauthorized("Invalid email or password.".into()));
    }

    // Lookup user by email
    let url = format!(
        "{}/api/internal/users/by-email?email={}",
        state.config.ai_service_url,
        urlencoding::encode(&email)
    );

    let res = state
        .http_client
        .get(&url)
        .header("x-service-token", &state.config.ai_service_internal_token)
        .send()
        .await
        .map_err(|e| AppError::UpstreamError(format!("Failed to reach auth backend: {e}")))?;

    if res.status().as_u16() == 404 {
        return Err(AppError::Unauthorized("Invalid email or password.".into()));
    }
    if !res.status().is_success() {
        return Err(AppError::UpstreamError("Authentication service error.".into()));
    }

    let user: InternalUserResponse = res
        .json()
        .await
        .map_err(|e| AppError::Internal(format!("Failed to decode user response: {e}")))?;

    if !user.is_active {
        return Err(AppError::Unauthorized("Invalid email or password.".into()));
    }

    let stored_hash = user
        .password_hash
        .ok_or_else(|| AppError::Unauthorized("Invalid email or password.".into()))?;

    // Verify Argon2id password hash
    let password_valid = Crypto::verify_password(&payload.password, &stored_hash)?;
    if !password_valid {
        return Err(AppError::Unauthorized("Invalid email or password.".into()));
    }

    // Generate new CSPRNG session and deterministic session-bound CSRF token (session rotation)
    let raw_session_token = Crypto::generate_secure_token();
    let session_token_hash = Crypto::sha256_hex(&raw_session_token);

    let raw_csrf_token = Crypto::derive_csrf_token(&state.config.csrf_secret, &raw_session_token)?;
    let csrf_token_hash = Crypto::sha256_hex(&raw_csrf_token);

    let user_agent = headers.get("user-agent").and_then(|v| v.to_str().ok());

    SessionManager::persist_session(
        &state.http_client,
        &state.config.ai_service_url,
        &state.config.ai_service_internal_token,
        &session_token_hash,
        &csrf_token_hash,
        &user.user_id,
        state.config.session_ttl_hours,
        user_agent,
        None,
    )
    .await?;

    let cookie = SessionManager::build_session_cookie(
        &raw_session_token,
        state.config.cookie_secure,
        state.config.session_ttl_hours,
    );

    let response = AuthResponse {
        user: UserInfo {
            user_id: user.user_id,
            email: user.email,
            full_name: user.full_name,
        },
        csrf_token: raw_csrf_token,
    };

    Ok((jar.add(cookie), Json(response)))
}

pub async fn logout(
    State(state): State<SharedState>,
    _auth: MutatingAuthContext,
    jar: CookieJar,
) -> Result<impl IntoResponse, AppError> {
    if let Some(cookie) = jar.get(SESSION_COOKIE_NAME) {
        let token_hash = Crypto::sha256_hex(cookie.value());
        let _ = SessionManager::revoke_session(
            &state.http_client,
            &state.config.ai_service_url,
            &state.config.ai_service_internal_token,
            &token_hash,
        )
        .await;
    }

    let removal_cookie = SessionManager::build_removal_cookie(state.config.cookie_secure);
    Ok((jar.add(removal_cookie), Json(json!({ "message": "Logged out successfully." }))))
}

pub async fn me(
    State(state): State<SharedState>,
    auth: AuthContext,
) -> Result<impl IntoResponse, AppError> {
    // Deterministically derive session-bound CSRF token via HMAC-SHA-256
    let raw_csrf_token = Crypto::derive_csrf_token(&state.config.csrf_secret, &auth.raw_session_token)?;
    let derived_csrf_hash = Crypto::sha256_hex(&raw_csrf_token);

    // Self-heal/sync if session was persisted with an older non-derived hash
    if auth.csrf_token_hash != derived_csrf_hash {
        SessionManager::update_csrf_token(
            &state.http_client,
            &state.config.ai_service_url,
            &state.config.ai_service_internal_token,
            &auth.session_token_hash,
            &derived_csrf_hash,
        )
        .await?;
    }

    let mut headers = HeaderMap::new();
    headers.insert(
        axum::http::header::CACHE_CONTROL,
        axum::http::HeaderValue::from_static("no-store, no-cache, must-revalidate, private"),
    );
    headers.insert(
        axum::http::header::PRAGMA,
        axum::http::HeaderValue::from_static("no-cache"),
    );

    Ok((headers, Json(json!({
        "user": {
            "user_id": auth.user_id,
            "email": auth.email,
            "full_name": auth.full_name
        },
        "csrf_token": raw_csrf_token
    }))))
}
