use crate::{config::Config, middleware::RateLimiter};
use reqwest::Client;
use std::{sync::Arc, time::Duration};

#[derive(Clone)]
pub struct AppState {
    pub config: Config,
    pub http_client: Client,
    pub auth_rate_limiter: RateLimiter,
}

impl AppState {
    pub fn new(config: Config) -> Self {
        let http_client = Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("Failed to initialize reqwest HTTP client");

        // Auth rate limit: 10 attempts per minute per IP
        let auth_rate_limiter = RateLimiter::new(10, Duration::from_secs(60));

        Self {
            config,
            http_client,
            auth_rate_limiter,
        }
    }
}

pub type SharedState = Arc<AppState>;
