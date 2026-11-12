# syntax=docker/dockerfile:1
# ---- 1. Build the web UI ------------------------------------------------------
FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---- 2. Python runtime (API + UI + CLI + MCP) -------------------------------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SHIPSAFE_API_HOST=0.0.0.0 \
    SHIPSAFE_API_PORT=8080 \
    SHIPSAFE_LOG_FORMAT=json \
    SHIPSAFE_ALLOWED_ROOTS=/workspaces:/app/fixtures
# git: workspace discovery. libxml2: required by the IBM Db2 CLI driver bundled with ibm_db.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git libxml2 \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 shipsafe
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY fixtures ./fixtures
RUN pip install -e ".[scanners]"
COPY --from=web /web/dist ./web/dist
USER shipsafe
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=4)"
CMD ["shipsafe", "serve"]
