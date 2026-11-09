use crate::{
    auth::{Crypto, SessionManager, SESSION_COOKIE_NAME},
    errors::AppError,
    state::SharedState,
};
use axum::{
    async_trait,
    extract::{FromRef, FromRequestParts},
    http::request::Parts,
};
use axum_extra::extract::CookieJar;

#[derive(Clone)]
pub struct AuthContext {
    pub raw_session_token: String,
    pub session_token_hash: String,
    pub user_id: String,
    pub email: String,
    pub full_name: String,
    pub csrf_token_hash: String,
}

impl std::fmt::Debug for AuthContext {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("AuthContext")
            .field("user_id", &self.user_id)
            .field("email", &self.email)
            .field("full_name", &self.full_name)
            .field("raw_session_token", &"[REDACTED]")
            .field("session_token_hash", &"[REDACTED]")
            .field("csrf_token_hash", &"[REDACTED]")
            .finish()
    }
}

#[derive(Clone, Debug)]
#[allow(dead_code)]
pub struct MutatingAuthContext {
    pub user_id: String,
    pub email: String,
    pub full_name: String,
}

#[async_trait]
impl<S> FromRequestParts<S> for AuthContext
where
    SharedState: FromRef<S>,
    S: Send + Sync,
{
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        let shared_state = SharedState::from_ref(state);
        let jar = CookieJar::from_headers(&parts.headers);

        let session_cookie = jar
            .get(SESSION_COOKIE_NAME)
            .ok_or_else(|| AppError::Unauthorized("Authentication required. Please log in.".into()))?;

        let raw_token = session_cookie.value();
        if raw_token.is_empty() {
            return Err(AppError::Unauthorized("Authentication required. Please log in.".into()));
        }

        let session_token_hash = Crypto::sha256_hex(raw_token);

        let user = SessionManager::validate_session(
            &shared_state.http_client,
            &shared_state.config.ai_service_url,
            &shared_state.config.ai_service_internal_token,
            &session_token_hash,
        )
        .await?;

        Ok(AuthContext {
            raw_session_token: raw_token.to_string(),
            session_token_hash,
            user_id: user.user_id,
            email: user.email,
            full_name: user.full_name,
            csrf_token_hash: user.csrf_token_hash,
        })
    }
}

#[async_trait]
impl<S> FromRequestParts<S> for MutatingAuthContext
where
    SharedState: FromRef<S>,
    S: Send + Sync,
{
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        let auth = AuthContext::from_request_parts(parts, state).await?;

        // Validate CSRF token header
        let csrf_header = parts
            .headers
            .get("x-csrf-token")
            .and_then(|val| val.to_str().ok())
            .ok_or_else(|| AppError::Forbidden("Missing required X-CSRF-Token header.".into()))?;

        let submitted_hash = Crypto::sha256_hex(csrf_header);
        if !Crypto::constant_time_eq_hex(&submitted_hash, &auth.csrf_token_hash) {
            tracing::warn!("CSRF token mismatch for user {}", auth.user_id);
            return Err(AppError::Forbidden("Invalid CSRF token.".into()));
        }

        Ok(MutatingAuthContext {
            user_id: auth.user_id,
            email: auth.email,
            full_name: auth.full_name,
        })
    }
}
