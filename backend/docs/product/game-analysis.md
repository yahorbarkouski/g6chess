# Game Analysis API

## Purpose

The game-analysis API lets a frontend start a full-game analysis job without
blocking the request for the full Stockfish, Maia, and OpenRouter runtime.

It is an orchestration layer over the existing one-move truth pipeline:

```text
Chess.com URL, Lichess URL, or PGN -> canonical PGN + source metadata -> per-ply context
packets -> deterministic classifications -> verified critical-move explanations
-> Redis snapshot -> polling frontend
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

Import a user-provided source and start the same job:

```text
POST /api/game-analysis/import
```

The request provides either:

- `source: "chess_com_live_url"` with `url` matching
  `/game/{id}`, `/game/live/{id}`, `/analysis/game/{id}`, or
  `/analysis/game/live/{id}`
- `source: "lichess_game_url"` with `url` matching a public standard Lichess
  game such as `https://lichess.org/{id}` or
  `https://lichess.org/game/export/{id}`
- `source: "pgn"` with pasted `pgn`

It also accepts the same analysis knobs as `POST /api/game-analysis`:
`time_control`, `explain_significance`, `include_context`, and
`use_baseline_fallback`. Imported games derive player levels from source
ratings: Chess.com and Lichess imports require both side ratings from source
data, and pasted PGNs use `WhiteElo` and `BlackElo` headers when present. Only
unrated pasted PGNs may provide explicit `white_player_level` and
`black_player_level`; the import endpoint must not invent a default rating.

The response returns the normal `analysis_id`, `status`, and `status_url` plus
source metadata such as source kind, external game id when known, title,
players, ratings, time control, result, and
`allows_global_training=false`.
PGN clock comments such as `[%clk 0:02:59.1]` are parsed into
per-ply clock fields so snapshots can expose the clock before the move,
remaining clock after the move, increment, and computed think time.

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
- per-move compact board, engine, main-point, candidate, and metadata fields
  needed by the frontend without requiring full context packets
- per-move clock-before, remaining-clock, and think-time fields when PGN clock
  comments are available
- optional per-move `opening_book` metadata with book status, novelty status,
  ECO/opening name, and compact continuation lines for UI preview
- verified explanation metadata when an explanation has completed
- optional full `ContextResult` when `include_context=true` for internal
  inspection

The move list is sorted by ply even though work completes in parallel.

## Runtime Policy

Production-shaped local game analysis uses:

- Stockfish depth 16 or deeper
- Maia2 when available through the project Maia extra
- OpenRouter `openai/gpt-5.5` through the existing provider adapter
- Redis for local job snapshots
- parallel context workers configured by
  `G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS`, defaulting to `8` in Modal
- OpenRouter concurrency configured by
  `G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY`, defaulting to `30` in
  Modal
- opening-book metadata enabled by default from the CC0 Lichess openings
  dataset; the backend downloads and caches the TSV source automatically when
  local data is missing

Redis defaults to `redis://localhost:6379/0` and can be overridden with
`G6EXPLANATION_REDIS_URL`.

Chess.com URL import is a user-requested acquisition boundary. The import layer
uses the live-game callback only to discover finished-game metadata, then
resolves the canonical PGN from Chess.com's public monthly archives. Resolved
PGNs are cached for 24 hours under `g6:game_import` by default. Useful import
configuration:

- `G6EXPLANATION_CHESS_COM_USER_AGENT`
- `G6EXPLANATION_CHESS_COM_TIMEOUT_SECONDS`
- `G6EXPLANATION_CHESS_COM_MAX_RETRIES`
- `G6EXPLANATION_CHESS_COM_RETRY_BACKOFF_SECONDS`
- `G6EXPLANATION_GAME_IMPORT_REDIS_PREFIX`
- `G6EXPLANATION_GAME_IMPORT_CACHE_TTL_SECONDS`

Lichess URL import is also a user-requested acquisition boundary. The import
layer resolves one public standard game through Lichess's one-game export API,
requests JSON with a full PGN field and clock comments, rejects ongoing or
non-standard-variant games, and caches resolved PGNs under the same import cache
prefix. Useful Lichess configuration:

- `G6EXPLANATION_LICHESS_USER_AGENT`
- `G6EXPLANATION_LICHESS_TIMEOUT_SECONDS`
- `G6EXPLANATION_LICHESS_MAX_RETRIES`
- `G6EXPLANATION_LICHESS_RETRY_BACKOFF_SECONDS`

The current local runner is single-process. Redis persists the latest snapshot,
but in-flight work is owned by the Python process that accepted the job.

## Source Rights

Chess.com URL imports, Lichess URL imports, and manual PGN imports are accepted
only as user-requested analysis inputs. They must not enter global eval or
training manifests unless a future explicit source-rights policy authorizes
that source. Import source metadata always marks these jobs with
`allows_global_training=false`.

## Failure Policy

Context-building failure fails the job because classification would be
incomplete.

Critical explanation failures are recorded per move. The job finishes with
status `failed` if any required explanation failed, while still returning the
partial move data and successful explanations.

Deterministic baseline fallback is disabled by default for this API so real
provider failures remain visible. It can be enabled only when the product
surface explicitly accepts fallback wording.

Import failures happen before the job starts:

- invalid or unsupported Chess.com URLs are rejected
- unfinished Chess.com live games are rejected
- Chess.com timeout, rate-limit, or archive unavailability is reported as
  temporary unavailability
- invalid or unsupported Lichess URLs are rejected
- unfinished or non-standard Lichess games are rejected
- Lichess timeout, rate-limit, or export unavailability is reported as
  temporary unavailability
- unresolved archive records and invalid PGN are rejected
- pasted PGN must parse and contain at least one mainline move
