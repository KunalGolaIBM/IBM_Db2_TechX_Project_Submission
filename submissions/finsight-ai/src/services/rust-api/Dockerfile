# Multi-stage Dockerfile for FinSight AI Rust API Gateway
FROM rust:1.85-slim-bookworm AS builder

WORKDIR /usr/src/app

# Pre-cache dependencies
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && cargo build --release --locked && rm -rf src

# Copy real source code
COPY src ./src
# Touch main.rs to invalidate dummy build
RUN touch src/main.rs && cargo build --release --locked

# Runtime image
FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 -s /bin/bash appuser

WORKDIR /app
COPY --from=builder /usr/src/app/target/release/finsight-rust-api /app/finsight-rust-api
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

ENV RUST_LOG=info \
    RUST_SERVER_PORT=8080 \
    AI_SERVICE_URL=http://ai-service:8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

ENTRYPOINT ["/app/finsight-rust-api"]
