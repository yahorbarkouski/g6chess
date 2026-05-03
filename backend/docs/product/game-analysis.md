# Game Analysis API

## Purpose

The game-analysis API lets a frontend start a full-game analysis job without
blocking the request for the full Stockfish, Maia, and OpenRouter runtime.

It is an orchestration layer over the existing one-move truth pipeline:

```text
PGN -> per-ply context packets -> deterministic classifications -> verified
critical-move explanations -> Redis snapshot -> polling frontend
```

It must not define new chess truth. Move quality, significance, beauty,
candidates, concepts, and explanation safety still come from
`context_engine` and `explanation_generation`.

## Endpoints

Start a job:

```text
POST /api/game-analysis
```

The request provides:

- `pgn`
- either `player_level` for both sides or `white_player_level` and
  `black_player_level`
- `time_control`
- `explain_significance`, defaulting to `["critical"]`
- `include_context`, defaulting to `false`
- `use_baseline_fallback`, defaulting to `false`

Poll a job:

```text
GET /api/game-analysis/{analysis_id}
```

The response is the latest `GameAnalysisSnapshot`. It can be incomplete while
the job is running. The frontend may render completed move classifications
before all critical explanations are ready.

## Snapshot Contract

Each snapshot includes:

- job status: `pending`, `running`, `succeeded`, or `failed`
- total plies
- context completion count
- explanation required, completed, and failed counts
- one `GameMoveAnalysis` per completed context
- per-move quality, significance, beauty, SAN, UCI, color, and latency
- verified explanation metadata when an explanation has completed
- optional full `ContextResult` when `include_context=true`

The move list is sorted by ply even though work completes in parallel.

## Runtime Policy

Production-shaped local game analysis uses:

- Stockfish depth 16 or deeper
- Maia2 when available through the project Maia extra
- OpenRouter `openai/gpt-5.5` through the existing provider adapter
- Redis for local job snapshots
- parallel context workers configured by
  `G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS`
- OpenRouter concurrency configured by
  `G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY`

Redis defaults to `redis://localhost:6379/0` and can be overridden with
`G6EXPLANATION_REDIS_URL`.

The current local runner is single-process. Redis persists the latest snapshot,
but in-flight work is owned by the Python process that accepted the job.

## Failure Policy

Context-building failure fails the job because classification would be
incomplete.

Critical explanation failures are recorded per move. The job finishes with
status `failed` if any required explanation failed, while still returning the
partial move data and successful explanations.

Deterministic baseline fallback is disabled by default for this API so real
provider failures remain visible. It can be enabled only when the product
surface explicitly accepts fallback wording.
