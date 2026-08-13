#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
    return
  fi

  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
    return
  fi

  echo "Docker Compose is required. Install Docker Desktop or docker-compose." >&2
  exit 1
}

compose up -d redis

export G6EXPLANATION_REDIS_URL="${G6EXPLANATION_REDIS_URL:-redis://localhost:6379/0}"
export G6EXPLANATION_API_HOST="${G6EXPLANATION_API_HOST:-127.0.0.1}"
export G6EXPLANATION_API_PORT="${G6EXPLANATION_API_PORT:-8001}"

exec uv run uvicorn g6explanation.api:app \
  --host "$G6EXPLANATION_API_HOST" \
  --port "$G6EXPLANATION_API_PORT" \
  --reload
