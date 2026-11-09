use crate::errors::AppError;
use axum_extra::extract::cookie::{Cookie, SameSite};
use chrono::{Duration, Utc};
use reqwest::Client;
use serde::{Deserialize, Serialize};

pub const SESSION_COOKIE_NAME: &str = "finsight_session";

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct AuthenticatedUser {
    pub user_id: String,
    pub email: String,
    pub full_name: String,
    pub csrf_token_hash: String,
}

#[derive(Serialize)]
struct CreateSessionPayload<'a> {
    session_token_hash: &'a str,
    user_id: &'a str,
    csrf_token_hash: &'a str,
    expires_at: String,
    user_agent: Option<&'a str>,
    ip_address: Option<&'a str>,
}

#[derive(Deserialize)]
struct InternalSessionResponse {
    pub user_id: String,
    pub email: String,
    pub full_name: String,
    pub csrf_token_hash: String,
}

pub struct SessionManager;

impl SessionManager {
    /// Builds the HTTP cookie for the raw session token.
    pub fn build_session_cookie(raw_token: &str, secure: bool, ttl_hours: i64) -> Cookie<'static> {
        let max_age_secs = (ttl_hours * 3600) as u32;
        Cookie::build((SESSION_COOKIE_NAME, raw_token.to_string()))
            .path("/")
            .http_only(true)
            .same_site(SameSite::Lax)
            .secure(secure)
            .max_age(cookie::time::Duration::seconds(max_age_secs as i64))
            .build()
    }

    /// Builds a cookie that deletes/invalidates the session in the client.
    pub fn build_removal_cookie(secure: bool) -> Cookie<'static> {
        let mut builder = Cookie::build((SESSION_COOKIE_NAME, ""))
            .path("/")
            .http_only(true)
            .same_site(SameSite::Lax)
            .max_age(cookie::time::Duration::seconds(0));
        if secure {
            builder = builder.secure(true);
        }
        builder.build()
    }

    /// Saves session record into Db2 via internal AI service endpoint.
    pub async fn persist_session(
        client: &Client,
        ai_service_url: &str,
        service_token: &str,
        session_token_hash: &str,
        csrf_token_hash: &str,
        user_id: &str,
        ttl_hours: i64,
        user_agent: Option<&str>,
        ip_address: Option<&str>,
    ) -> Result<(), AppError> {
        let expires_at = (Utc::now() + Duration::hours(ttl_hours))
            .format("%Y-%m-%d %H:%M:%S")
            .to_string();

        let payload = CreateSessionPayload {
            session_token_hash,
            user_id,
            csrf_token_hash,
            expires_at,
            user_agent,
            ip_address,
        };

        let url = format!("{ai_service_url}/api/internal/sessions");
        let res = client
            .post(&url)
            .header("x-service-token", service_token)
            .json(&payload)
            .send()
            .await
            .map_err(|e| AppError::UpstreamError(format!("Failed to reach session service: {e}")))?;

        if !res.status().is_success() {
            let status = res.status();
            let text = res.text().await.unwrap_or_default();
            tracing::error!("Failed to persist session: status={status}, body={text}");
            return Err(AppError::Internal("Failed to store user session".into()));
        }

        Ok(())
    }

    /// Validates session hash with internal endpoint.
    pub async fn validate_session(
        client: &Client,
        ai_service_url: &str,
        service_token: &str,
        session_token_hash: &str,
    ) -> Result<AuthenticatedUser, AppError> {
        let url = format!("{ai_service_url}/api/internal/sessions/{session_token_hash}");
        let res = client
            .get(&url)
            .header("x-service-token", service_token)
            .send()
            .await
            .map_err(|e| AppError::UpstreamError(format!("Internal session validation failed: {e}")))?;

        if res.status().as_u16() == 401 || res.status().as_u16() == 404 {
            return Err(AppError::Unauthorized("Session expired or invalid".into()));
        }

        if !res.status().is_success() {
            return Err(AppError::UpstreamError("Session lookup error".into()));
        }

        let sess: InternalSessionResponse = res
            .json()
            .await
            .map_err(|e| AppError::Internal(format!("Failed to parse session response: {e}")))?;

        Ok(AuthenticatedUser {
            user_id: sess.user_id,
            email: sess.email,
            full_name: sess.full_name,
            csrf_token_hash: sess.csrf_token_hash,
        })
    }

    /// Revokes session in Db2.
    pub async fn revoke_session(
        client: &Client,
        ai_service_url: &str,
        service_token: &str,
        session_token_hash: &str,
    ) -> Result<(), AppError> {
        let url = format!("{ai_service_url}/api/internal/sessions/{session_token_hash}");
        let _ = client
            .delete(&url)
            .header("x-service-token", service_token)
            .send()
            .await;
        Ok(())
    }

    /// Updates the CSRF token hash for an active session.
    pub async fn update_csrf_token(
        client: &Client,
        ai_service_url: &str,
        service_token: &str,
        session_token_hash: &str,
        csrf_token_hash: &str,
    ) -> Result<(), AppError> {
        let url = format!("{ai_service_url}/api/internal/sessions/{session_token_hash}/csrf");
        let payload = serde_json::json!({ "csrf_token_hash": csrf_token_hash });
        let res = client
            .put(&url)
            .header("x-service-token", service_token)
            .json(&payload)
            .send()
            .await
            .map_err(|e| AppError::UpstreamError(format!("Failed to update session CSRF token: {e}")))?;

        if !res.status().is_success() {
            let status = res.status();
            let text = res.text().await.unwrap_or_default();
            tracing::error!("Failed to update session CSRF in Db2: status={status}, body={text}");
            return Err(AppError::Internal("Failed to update session CSRF token in database".into()));
        }

        Ok(())
    }
}
