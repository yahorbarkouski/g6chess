# Modal Deployment

## Purpose

This is the first public deployment path for the FastAPI game-analysis backend.
It keeps the repo's product boundary intact:

```text
FastAPI request -> Redis pending snapshot -> Modal worker spawn
  -> GameAnalysisRunner -> Redis partial snapshots -> frontend polling
```

The API process does not own in-flight full-game analysis in production. It
spawns a Modal worker and returns `analysis_id` immediately.

## Files

- `.github/workflows/ci.yml`: required local quality gates on pull requests,
  `main`, and manual dispatch.
- `.github/workflows/deploy-modal.yml`: automatic `main` deploy workflow that
  repeats the required gates, syncs the Modal runtime secret, and runs
  `modal deploy`. Manual dispatch remains available for warm-container and
  worker-cap overrides.
- `deploy/modal_app.py`: Modal App with a lightweight FastAPI endpoint and a
  heavier Stockfish/Maia worker function.
- `src/g6explanation/game_analysis/modal_job_executor.py`: testable executor
  that serializes a `GameAnalysisStartRequest` and calls a spawn function.

## Runtime Shape

The Modal App is named `g6explanation`.

The FastAPI function uses the base project dependencies plus the Modal SDK. It
reads and writes Redis snapshots and uses `ModalSpawnGameAnalysisExecutor` to
spawn `run_game_analysis_job`.

The worker function installs Stockfish and the Maia extra, mounts the
`g6explanation-maia-models` Modal Volume at `/models/maia2`, and runs the
existing `GameAnalysisRunner`.

The worker image also prefetches the default CC0 Lichess openings dataset during
image build so opening-book metadata is available without a runtime source-data
download on the first analysis job.

## Required GitHub Secrets

Add these repository or environment secrets before merging to `main` or running
`Deploy Modal` manually:

```text
MODAL_TOKEN_ID
MODAL_TOKEN_SECRET
OPENROUTER_API_KEY
G6EXPLANATION_REDIS_URL
```

`G6EXPLANATION_REDIS_URL` should point at a managed Redis service reachable from
Modal.

Optional GitHub environment variable:

```text
G6EXPLANATION_CORS_ORIGINS=https://your-frontend.example
G6EXPLANATION_MODAL_CUSTOM_DOMAINS=api.your-frontend.example
G6EXPLANATION_MODAL_REQUIRES_PROXY_AUTH=true
```

Use a comma-separated list for multiple frontend origins.

Optional GitHub secret:

```text
G6EXPLANATION_TURNSTILE_SECRET_KEY
```

When this secret is present, the deploy workflow syncs it into the Modal runtime
secret and requires Turnstile validation for expensive anonymous starts.

The deploy workflow syncs these values into the Modal secret named
`g6explanation-runtime`.

## Cloudflare Gateway

For public traffic, put the API hostname behind Cloudflare and enable Modal
proxy auth:

```text
G6EXPLANATION_MODAL_CUSTOM_DOMAINS=api.your-frontend.example
G6EXPLANATION_MODAL_REQUIRES_PROXY_AUTH=true
```

The generated `.modal.run` URL remains reachable unless proxy auth is enabled.
With proxy auth on, Cloudflare must add `Modal-Key` and `Modal-Secret` as origin
request headers. A Worker template is provided at
`deploy/cloudflare/modal-proxy-worker.js`.

Worker secrets:

```text
MODAL_ORIGIN_HOST=<workspace>--g6explanation-fastapi-app.modal.run
MODAL_KEY=<Modal proxy auth key>
MODAL_SECRET=<Modal proxy auth secret>
```

After deployment, verify:

```text
curl https://<workspace>--g6explanation-fastapi-app.modal.run/api/visualization/health
# expected: rejected by Modal proxy auth

curl https://api.your-frontend.example/api/visualization/health
# expected: 200 through Cloudflare
```

## Deploy

Merging to `main` automatically runs `Deploy Modal`. The deploy happens only
after formatting, linting, typing, and tests pass in that workflow.

Run the workflow manually when you need to override warm-container or worker-cap
settings without merging code.

Useful inputs:

- `modal_environment`: Modal environment, default `main`.
- `api_min_containers`: set to `1` during a public demo if cold-start latency
  matters; set back to `0` after.
- `worker_min_containers`: set to `1` shortly before a launch window if the
  first analysis must avoid worker cold start; set back to `0` after.
- `worker_max_containers`: hard cap on concurrent analysis workers. Keep this
  conservative until rate limits, cost accounting, and abuse controls are in
  place.

## Launch Defaults

Recommended first public launch settings:

```text
api_min_containers=1
worker_min_containers=0
worker_max_containers=5
```

Raise `worker_min_containers` to `1` only for a scheduled presentation window.

Keep product requests at:

```text
explain_significance=["critical"]
include_context=false
use_baseline_fallback=false
```

Use `include_context=true` only for internal inspection tools. Normal frontend
polling uses compact per-move board, engine, label, and explanation fields
without downloading full context packets.

## Runtime Knobs

Modal deployment-time environment variables:

```text
G6EXPLANATION_MODAL_API_MIN_CONTAINERS
G6EXPLANATION_MODAL_API_MAX_CONTAINERS
G6EXPLANATION_MODAL_WORKER_MIN_CONTAINERS
G6EXPLANATION_MODAL_WORKER_MAX_CONTAINERS
G6EXPLANATION_MODAL_WORKER_CPU
G6EXPLANATION_MODAL_WORKER_MEMORY_MB
G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS
G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY
G6EXPLANATION_LOG_LEVEL
```

Worker function defaults request `16` CPU cores and `16384` MiB memory for one
analysis container.

Worker image defaults:

```text
G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_BINARY=/usr/games/stockfish
G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_DEPTH=16
G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_THREADS=1
G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_HASH_MB=128
G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS=8
G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY=30
MAIA2_MODEL_ROOT=/models/maia2
```

Override these only after measuring latency, memory, provider failures, and
cost.

Public API protection defaults on Modal:

```text
G6EXPLANATION_API_PROTECTION_ENABLED=true
G6EXPLANATION_ENABLE_OPENAPI_DOCS=false
G6EXPLANATION_ENABLE_VISUALIZATION_CONTEXTS=false
G6EXPLANATION_ALLOW_PUBLIC_INCLUDE_CONTEXT=true
```

`include_context=true` remains allowed for trusted debugging and internal
inspection. Keep ordinary product requests on the compact snapshot path.

## Verification

CI and deploy workflows run:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
```

After deployment, verify:

```text
curl https://<modal-app-url>/api/visualization/health
```

Then run one small PGN through `/api/game-analysis/import` or
`/api/game-analysis` with `explain_significance=["critical"]` and poll until a
terminal snapshot.

Run the no-mock game-analysis gate before calling a deployment product-ready:

```text
G6EXPLANATION_RUN_REAL_GAME_ANALYSIS=1 \
uv run pytest tests/g6explanation/game_analysis/test_game_analysis_redis.py -q -s
```

That gate requires Redis, real Stockfish, Maia2 model files, and OpenRouter
credentials.

## Known Limits

This deployment still depends on Redis snapshot state and does not add durable
distributed queue semantics, cancellation, user ownership, or cost accounting.
Those remain production-hardening work before broad multi-user traffic.
