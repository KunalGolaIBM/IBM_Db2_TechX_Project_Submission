mod auth;
mod config;
mod errors;
mod middleware;
mod routes;
mod state;

use std::{net::SocketAddr, sync::Arc, time::Duration};

use axum::{
    routing::{get, post},
    Router,
};
use config::Config;
use state::AppState;
use tower_http::{
    cors::{AllowOrigin, CorsLayer},
    limit::RequestBodyLimitLayer,
    timeout::TimeoutLayer,
    trace::TraceLayer,
};
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

#[tokio::main]
async fn main() {
    tracing_subscriber::registry()
        .with(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info,finsight_rust_api=debug,tower_http=info".into()),
        )
        .with(tracing_subscriber::fmt::layer())
        .init();

    let config = Config::from_env();
    tracing::info!("FinSight AI Rust API Gateway initializing...");
    tracing::info!("Target AI Service: {}", config.ai_service_url);
    tracing::info!("CORS Allowed Origins: {:?}", config.cors_allowed_origins);

    let state = Arc::new(AppState::new(config.clone()));

    // CORS configuration
    let allowed_origins: Vec<axum::http::HeaderValue> = config
        .cors_allowed_origins
        .iter()
        .filter_map(|o| o.parse().ok())
        .collect();

    let cors = CorsLayer::new()
        .allow_origin(AllowOrigin::list(allowed_origins))
        .allow_methods([
            axum::http::Method::GET,
            axum::http::Method::POST,
            axum::http::Method::PUT,
            axum::http::Method::PATCH,
            axum::http::Method::DELETE,
            axum::http::Method::OPTIONS,
        ])
        .allow_headers([
            axum::http::header::CONTENT_TYPE,
            axum::http::header::AUTHORIZATION,
            axum::http::header::ACCEPT,
            axum::http::header::COOKIE,
            axum::http::HeaderName::from_static("x-csrf-token"),
        ])
        .allow_credentials(true);

    let auth_routes = Router::new()
        .route("/register", post(routes::auth::register))
        .route("/login", post(routes::auth::login))
        .route("/logout", post(routes::auth::logout))
        .route("/me", get(routes::auth::me));

    let ai_routes = Router::new()
        .route("/chat", post(routes::ai::chat))
        .route("/search", post(routes::ai::search))
        .route("/status", get(routes::ai::get_status));

    let api_v1_routes = Router::new()
        .nest("/auth", auth_routes)
        .nest("/ai", ai_routes)
        .route("/dashboard/summary", get(routes::financial::get_dashboard_summary))
        .route("/transactions", get(routes::financial::get_transactions))
        .route("/anomalies", get(routes::financial::get_anomalies))
        .route("/anomalies/:alert_id", get(routes::financial::get_anomaly))
        .route(
            "/anomalies/:alert_id/explain",
            post(routes::financial::explain_anomaly),
        )
        .route(
            "/anomalies/:alert_id/status",
            axum::routing::patch(routes::financial::update_anomaly_status),
        )
        .route("/insights", get(routes::financial::get_insights))
        .route("/reports/monthly", get(routes::financial::get_monthly_report))
        .route("/imports/preview", post(routes::financial::preview_import))
        .route("/imports/commit", post(routes::financial::commit_import))
        .route("/imports/history", get(routes::financial::list_imports))
        .route("/imports/:import_id", get(routes::financial::get_import))
        .route(
            "/imports/:import_id/retry-indexing",
            post(routes::financial::retry_import_indexing),
        );

    let app = Router::new()
        .route("/health", get(routes::health::health_check))
        .nest("/api/v1", api_v1_routes)
        .layer(cors)
        .layer(TraceLayer::new_for_http())
        .layer(RequestBodyLimitLayer::new(6 * 1024 * 1024))
        .layer(TimeoutLayer::new(Duration::from_secs(30)))
        .with_state(state);

    let addr = SocketAddr::from(([0, 0, 0, 0], config.server_port));
    tracing::info!("FinSight AI Rust API Gateway listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .unwrap_or_else(|e| panic!("Failed to bind TCP listener on {addr}: {e}"));

    axum::serve(listener, app)
        .await
        .unwrap_or_else(|e| panic!("Server runtime error: {e}"));
}
