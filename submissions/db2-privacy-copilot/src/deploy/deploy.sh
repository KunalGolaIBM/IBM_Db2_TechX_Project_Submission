#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR=/opt/copilot
COMPOSE_FILE=deploy/docker-compose.prod.yml
cd "$APP_DIR"

NEW_TAG="${1:?Usage: deploy.sh <commit-sha>}"
if [[ ! "$NEW_TAG" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Expected a 40-character lowercase commit SHA." >&2
    exit 2
fi

PREV_TAG="$(awk -F= '$1 == "TAG" { print substr($0, index($0, "=") + 1); exit }' .env)"
DOMAIN="$(awk -F= '$1 == "DOMAIN" { print substr($0, index($0, "=") + 1); exit }' .env)"
if [[ -z "$DOMAIN" ]]; then
    echo "DOMAIN must be set in /opt/copilot/.env." >&2
    exit 2
fi
COMPOSE=(docker compose -f "$COMPOSE_FILE" --env-file .env)

write_tag() {
    local tag="$1"
    if grep -q '^TAG=' .env; then
        sed -i "s/^TAG=.*/TAG=${tag}/" .env
    else
        printf '\nTAG=%s\n' "$tag" >> .env
    fi
}

rollback_on_error() {
    local status=$?
    trap - ERR
    if [[ -n "$PREV_TAG" && "$PREV_TAG" != "$NEW_TAG" ]]; then
        echo "Deployment failed; restoring ${PREV_TAG}." >&2
        write_tag "$PREV_TAG"
        "${COMPOSE[@]}" up -d --remove-orphans || \
            echo "Rollback command failed; inspect the Compose logs." >&2
    else
        echo "Deployment failed and no previous image tag is available to roll back to." >&2
    fi
    exit "$status"
}
trap rollback_on_error ERR

echo "Deploying ${NEW_TAG} (previous: ${PREV_TAG:-none})"
write_tag "$NEW_TAG"
"${COMPOSE[@]}" pull api ui
"${COMPOSE[@]}" up -d --remove-orphans

for _ in $(seq 1 30); do
    if "${COMPOSE[@]}" exec -T api python -c \
        "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=5)" \
        >/dev/null 2>&1 && \
        curl --fail --silent --show-error --max-time 10 \
            "https://${DOMAIN}/api/healthz" >/dev/null 2>&1; then
        echo "Internal and public health checks passed."
        docker image prune -f >/dev/null
        exit 0
    fi
    sleep 10
done

echo "API health check failed after 5 minutes." >&2
false
