use std::env;

#[derive(Clone, Debug)]
#[allow(dead_code)]
pub struct Config {
    pub server_host: String,
    pub server_port: u16,
    pub ai_service_url: String,
    pub ai_service_internal_token: String,
    pub csrf_secret: String,
    pub session_ttl_hours: i64,
    pub cookie_secure: bool,
    pub cors_allowed_origins: Vec<String>,
    pub environment: String,
}

impl Config {
    pub fn from_env() -> Self {
        let server_host = env::var("RUST_SERVER_HOST").unwrap_or_else(|_| "0.0.0.0".to_string());
        let server_port = env::var("RUST_SERVER_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(8080);
        let ai_service_url = env::var("AI_SERVICE_URL")
            .unwrap_or_else(|_| "http://ai-service:8000".to_string());
        let ai_service_internal_token = env::var("AI_SERVICE_INTERNAL_TOKEN")
            .unwrap_or_else(|_| "GLtWRU3gWNfGYzxpMFm9vt7yytyxKer8".to_string());
        let csrf_secret = env::var("CSRF_SECRET").unwrap_or_else(|_| {
            "finsight_csrf_secret_dev_32bytes_min_key_len!".to_string()
        });
        let session_ttl_hours = env::var("SESSION_TTL_HOURS")
            .ok()
            .and_then(|h| h.parse().ok())
            .unwrap_or(24);
        let environment = env::var("ENVIRONMENT").unwrap_or_else(|_| "development".to_string());
        let cookie_secure = env::var("COOKIE_SECURE")
            .map(|v| v.to_lowercase() == "true")
            .unwrap_or(false);

        // Security Invariant: Production requires Secure cookies over HTTPS and explicit CSRF secret >= 32 chars
        if environment.to_lowercase() == "production" {
            if !cookie_secure {
                panic!("FATAL SECURITY CONFIGURATION: In production environment (ENVIRONMENT=production), COOKIE_SECURE must be set to 'true'. Refusing to start in insecure state.");
            }
            if csrf_secret.len() < 32 || csrf_secret == "finsight_csrf_secret_dev_32bytes_min_key_len!" {
                panic!("FATAL SECURITY CONFIGURATION: In production environment (ENVIRONMENT=production), CSRF_SECRET must be explicitly set and at least 32 characters long. Refusing to start.");
            }
        }
        let origins_raw = env::var("CORS_ALLOWED_ORIGINS")
            .unwrap_or_else(|_| "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080".to_string());
        let cors_allowed_origins = origins_raw
            .split(',')
            .map(|s| s.trim().to_string())
            .filter(|s| !s.is_empty())
            .collect();

        Self {
            server_host,
            server_port,
            ai_service_url,
            ai_service_internal_token,
            csrf_secret,
            session_ttl_hours,
            cookie_secure,
            cors_allowed_origins,
            environment,
        }
    }
}
