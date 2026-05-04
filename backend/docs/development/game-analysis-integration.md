# Real-World Game Analysis Integration

## When To Use This API

Use the async game-analysis API when an application needs full-game review
without making the user wait for a long synchronous request.

The intended product flow is:

```text
Frontend submits Chess.com live-game URL or PGN
  -> backend import layer resolves canonical PGN + source metadata
  -> backend starts analysis
  -> API returns analysis_id immediately
  -> frontend polls analysis_id
  -> frontend renders completed move classifications first
  -> critical explanations appear as they pass verification
```

This API is not a separate chess engine. It repeats the verified one-move
pipeline for every ply and stores the latest job snapshot in Redis.

Chess.com import belongs in the Python API, not the browser. The browser starts
from a user-provided URL, but the API owns URL validation, callback/archive
resolution, PGN parsing, cache policy, retry/backoff, and source-rights
metadata. The frontend must keep a PGN paste fallback for cases where Chess.com
cannot be reached, rate-limits the import, the game is unfinished, or the
archive record cannot be resolved.

## Runtime Components

A local real-provider deployment needs:

- Python API process running `g6explanation.visualization.http_api:app`
- Redis for job snapshots
- Stockfish available on `PATH` or configured by environment
- Maia2 installed with local model files
- `OPENROUTER_API_KEY` in `.env` or the process environment

The current runner is single-process: the Python process that accepts the job
owns the in-flight work. Redis stores partial snapshots for polling, but it is
not yet a durable distributed queue.

## Start Locally

Install dependencies:

```text
uv sync --extra maia
```

Start Redis:

```text
redis-server
```

Start the API:

```text
uv run uvicorn g6explanation.visualization.http_api:app \
  --host 127.0.0.1 \
  --port 8001 \
  --reload
```

Check health:

```text
curl http://127.0.0.1:8001/api/visualization/health
```

## Required Environment

Minimum:

```text
OPENROUTER_API_KEY=...
G6EXPLANATION_REDIS_URL=redis://localhost:6379/0
```

Useful local overrides:

```text
G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS=8
G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY=30
G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_BINARY=/path/to/stockfish
G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_MULTIPV=5
G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_THREADS=1
G6EXPLANATION_GAME_ANALYSIS_STOCKFISH_HASH_MB=128
G6EXPLANATION_GAME_ANALYSIS_MAIA2_MODEL=auto
G6EXPLANATION_GAME_ANALYSIS_MAIA2_DEVICE=cpu
MAIA2_MODEL_ROOT=./maia2_models
G6EXPLANATION_CHESS_COM_USER_AGENT=g6explanation-local/0.1
G6EXPLANATION_CHESS_COM_TIMEOUT_SECONDS=20
G6EXPLANATION_CHESS_COM_MAX_RETRIES=2
G6EXPLANATION_CHESS_COM_RETRY_BACKOFF_SECONDS=0.5
G6EXPLANATION_GAME_IMPORT_REDIS_PREFIX=g6:game_import
G6EXPLANATION_GAME_IMPORT_CACHE_TTL_SECONDS=86400
```

Keep Stockfish depth at 16 or deeper. Do not lower depth for production-shaped
analysis.

## Start A Job

Submit PGN and player-level information:

```text
curl -X POST http://127.0.0.1:8001/api/game-analysis \
  -H 'Content-Type: application/json' \
  -d '{
    "pgn": "[Event \"Example\"]\n\n1. e4 e5 2. Nf3 Nc6 *",
    "player_level": {"kind": "rating", "value": 1500},
    "time_control": "rapid",
    "explain_significance": ["critical"],
    "include_context": false,
    "use_baseline_fallback": false
  }'
```

Response:

```json
{
  "analysis_id": "3c3f4d9b5b6540ec8e2df0f66f0af61c",
  "status": "pending",
  "status_url": "/api/game-analysis/3c3f4d9b5b6540ec8e2df0f66f0af61c"
}
```

Use `player_level` when one rating should apply to both sides. Use
`white_player_level` and `black_player_level` when the ratings differ.

Use `explain_significance` to control cost and latency. Recommended defaults:

- `["critical"]` for product usage
- `["critical", "high"]` for deeper review
- all labels only for internal inspection or expensive QA

Keep `include_context=false` for normal frontend polling. Set it to `true` only
for internal tools because full context packets are large.

## Import A Chess.com Live Game

Submit the user-provided URL to the import endpoint:

```text
curl -X POST http://127.0.0.1:8001/api/game-analysis/import \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "chess_com_live_url",
    "url": "https://www.chess.com/game/live/168193636078",
    "player_level": {"kind": "rating", "value": 1500},
    "time_control": "rapid",
    "explain_significance": ["critical"],
    "include_context": true,
    "use_baseline_fallback": false
  }'
```

The response mirrors `POST /api/game-analysis` and includes source metadata:

```json
{
  "analysis_id": "3c3f4d9b5b6540ec8e2df0f66f0af61c",
  "status": "pending",
  "status_url": "/api/game-analysis/3c3f4d9b5b6540ec8e2df0f66f0af61c",
  "source": {
    "source": "chess_com_live_url",
    "source_url": "https://www.chess.com/game/live/168193636078",
    "external_game_id": "168193636078",
    "title": "White vs Black",
    "allows_global_training": false
  }
}
```

The frontend integration should set `include_context=true` while it still needs
FENs and principal variation data to hydrate the existing board UI.

If URL import fails, reveal the PGN paste fallback and submit the same endpoint
with `source: "pgn"`:

```text
curl -X POST http://127.0.0.1:8001/api/game-analysis/import \
  -H 'Content-Type: application/json' \
  -d '{
    "source": "pgn",
    "pgn": "[Event \"Example\"]\n\n1. e4 e5 2. Nf3 Nc6 *",
    "player_level": {"kind": "rating", "value": 1500},
    "explain_significance": ["critical"],
    "include_context": true
  }'
```

## Poll A Job

Poll until `status` is `succeeded` or `failed`:

```text
curl http://127.0.0.1:8001/api/game-analysis/3c3f4d9b5b6540ec8e2df0f66f0af61c
```

The response is a `GameAnalysisSnapshot`. It is intentionally useful before the
job is complete:

```json
{
  "status": "running",
  "total_plies": 82,
  "context_completed": 37,
  "explanation_required": 9,
  "explanation_completed": 4,
  "explanation_failed": 0,
  "moves": [
    {
      "ply": 13,
      "san": "Qxc4",
      "uci": "b3c4",
      "player_color": "white",
      "state": "explained",
      "requires_explanation": true,
      "quality": "best",
      "significance": {"label": "critical", "score": 1.0},
      "beauty": {"label": "notable", "score": 0.55},
      "explanation": "Qxc4 was the key capture in the critical position, winning a pawn immediately."
    }
  ]
}
```

The `moves` array is sorted by ply. A move appears after its context is ready.
Critical explanations may arrive later.

## Frontend Polling Pattern

Use a short interval while work is active and stop polling on terminal status:

```ts
async function startAnalysis(pgn: string) {
  const response = await fetch("/api/game-analysis/import", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      source: "pgn",
      pgn,
      player_level: {kind: "rating", value: 1500},
      time_control: "rapid",
      explain_significance: ["critical"],
      include_context: true,
    }),
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<{analysis_id: string; status_url: string}>;
}

async function pollAnalysis(statusUrl: string) {
  const response = await fetch(statusUrl);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json();
}
```

Recommended frontend behavior:

- Keep demo/mock data visible until a real job has started.
- Store `analysis_id` and `status_url` in local storage so refreshes can resume
  polling while the single API process still owns the job.
- Reveal the PGN paste fallback when URL import returns invalid URL, unresolved
  archive, unfinished game, Chess.com unavailable, timeout, or rate-limit.
- Overlay classification badges as `moves` arrive.
- Show explanation placeholders only for moves where `requires_explanation` is
  true.
- Treat `failed` as a partial-result state, not a blank screen.
- Convert context packet evaluation scores into the UI's white-point-of-view
  convention before rendering engine bars or line scores.

## Backend Integration Pattern

In a real product, put this API behind your own authenticated backend.

Recommended responsibilities:

- authenticate users before accepting PGNs
- enforce PGN size and ply-count limits
- rate-limit job creation
- reject unsupported data sources for training
- preserve `allows_global_training=false` for Chess.com and manual PGN imports
- decide whether user games may be stored and for how long
- proxy the polling endpoint or expose it only to authorized users

Do not expose `include_context=true` to ordinary users unless the product
intentionally needs full evidence packets. Context packets contain detailed
engine and model metadata that are useful for debugging but heavy for UI traffic.

## Error Handling

HTTP failures:

- `400`: bad PGN or invalid request shape
- `404`: unknown `analysis_id`
- `404`: Chess.com URL is syntactically supported but cannot be resolved
- `409`: Chess.com live game exists but is unfinished
- `422`: unsupported URL shape, invalid pasted PGN, unresolved archive match, or
  non-chess archive record
- `503`: Redis or local provider setup is unavailable
- `503`: Chess.com callback/archive is temporarily unavailable, timed out,
  rate-limited after retries, or malformed

Snapshot failures:

- `status=failed` with `context_completed < total_plies` means context building
  failed and classifications are incomplete.
- `status=failed` with completed contexts and `explanation_failed > 0` means at
  least one required explanation failed verification or provider I/O, while
  successful move data remains usable.

By default, `use_baseline_fallback=false`, so GPT/provider failures stay visible.
Use fallback only for a product surface that explicitly prefers deterministic
safe wording over surfacing the model failure.

## Latency And Cost

Measured on the local 16-core machine:

- Game of the Century, 82 plies, real Stockfish, Maia, GPT-5.5 critical
  explanations: about 40 seconds with parallel context workers.
- Opera Game real endpoint gate: about 18 seconds.

Primary latency comes from Stockfish. OpenRouter calls are already run with high
bounded concurrency.

Cost is controlled mainly by:

- `explain_significance`
- OpenRouter model and reasoning settings
- PGN length
- context worker count

Do not set context workers blindly higher than CPU capacity. For this machine,
8 to 16 workers is the useful range.

## Production Hardening Checklist

Before using this as a multi-user production service, add or decide:

- durable queue semantics for job ownership and retries
- separate worker process or worker pool instead of in-process background work
- cancellation and timeout policy
- user/job ownership in Redis keys or a database table
- request size, ply count, and rate limits
- Redis persistence and eviction policy
- structured latency and failure metrics
- cost accounting per job
- API auth and authorization
- result retention policy
- privacy policy for user-imported games

The current implementation is suitable for local product integration and
single-process deployment experiments. It is intentionally not yet a distributed
job system.

## Verification

Run the deterministic API tests:

```text
uv run pytest tests/g6explanation/game_analysis -q
uv run pytest tests/g6explanation/game_imports -q
```

Run the opt-in real Chess.com import smoke without Stockfish/OpenRouter:

```text
G6EXPLANATION_RUN_CHESSCOM_IMPORT=1 \
uv run pytest tests/g6explanation/game_imports/test_chess_com_live_games.py -q -s
```

Run the no-mock real endpoint gate:

```text
G6EXPLANATION_RUN_REAL_GAME_ANALYSIS=1 \
uv run pytest tests/g6explanation/game_analysis/test_game_analysis_redis.py -q -s
```

The real gate requires Redis, Stockfish, Maia2, local Maia model files, and
OpenRouter credentials. It verifies the POST/poll flow with real providers and
requires Stockfish depth 16 or deeper.
