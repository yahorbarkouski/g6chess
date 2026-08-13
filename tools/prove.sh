#!/bin/sh
set -eu

repository_root=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)

cd "$repository_root/backend"
uv sync --locked --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
uv run python scripts/export_openapi.py

cd "$repository_root/frontend"
bun install --frozen-lockfile
bun audit
bun run contracts:generate
bun run typecheck
bun run lint
bun run test
bun run build

cd "$repository_root"
git diff --exit-code -- contracts/openapi.json frontend/src/generated/g6-api.ts
