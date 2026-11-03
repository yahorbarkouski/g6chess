# Game Analysis API

## Purpose

The game-analysis API lets a frontend start a full-game analysis job without
blocking the request for the full Stockfish, Maia, and OpenRouter runtime.

It is an orchestration layer over the existing one-move truth pipeline:

```text
Chess.com URL, Lichess game/study URL, or PGN -> canonical PGN + source metadata -> per-ply context
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
- `source: "lichess_study_chapter_url"` with `url` matching one public chapter
  such as `https://lichess.org/study/{study_id}/{chapter_id}`
- `source: "pgn"` with pasted `pgn`

It also accepts the same analysis knobs as `POST /api/game-analysis`:
`time_control`, `explain_significance`, `include_context`, and
`use_baseline_fallback`. Imported games derive player levels from source
ratings: Chess.com and standalone Lichess games require both side ratings from
source data. Study chapters and pasted PGNs use `WhiteElo` and `BlackElo`
headers when present and otherwise require explicit `white_player_level` and
`black_player_level`. The import endpoint must not invent a default rating.
Each source is a discriminated request variant, so URL requests cannot contain
PGN fields and PGN requests cannot contain URL fields.

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
- optional whole-game `accuracy` percentages for White and Black
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

### Game accuracy

Snapshot version `game_analysis_snapshot.v3` adds nullable `accuracy` with
`method: "mean_move_accuracy.v1"`, `white`, and `black`. It appears after all
plies have verified contexts, including when explanation generation fails.
Current snapshots return `accuracy: null` until then. The `white` and `black`
fields are nullable numbers on a 0..100 scale. Earlier cached snapshots without
this field have no accuracy.
A side with no moves or missing engine evidence has a null percentage.

The context engine computes each move's accuracy from the best and played
Stockfish scores, both in the moving player's perspective. Centipawns become
winning-chance percentages using `50 + 50 * tanh(0.00368208 * cp / 2)`.
Mate for the player is 100%; mate against the player is 0%. Mate distance stays
separate from centipawns. A non-positive winning-chance loss scores 100%.
Loss is the best line's winning-chance percentage minus the played line's
winning-chance percentage, measured in percentage points.
Otherwise, move accuracy is
`clamp(103.1668 * exp(-0.04354 * loss) - 3.1669, 0, 100)`.
These curves come from the [Lichess accuracy metric](https://lichess.org/page/accuracy).

Game analysis takes the arithmetic mean of every move accuracy for each side,
including opening-book and forced moves, and rounds once to one decimal place.
For example, move accuracies of 100% and 50% produce 75.0% for that player.
This aggregation is specific to g6; Lichess uses volatility and harmonic means
for its game score. Accuracy uses existing verified engine evidence and adds
no provider calls. Move labels and explanation policy remain independent.

The frontend displays these whole-game percentages beside each player. Board
navigation and orientation do not change them. Until accuracy is available,
each player bar displays a placeholder.

## Runtime Policy

Production-shaped local game analysis uses:

- Stockfish depth 16 or deeper
- Maia2 when available through the project Maia extra
- OpenRouter `openai/gpt-5.6-terra` with high reasoning through the existing
  provider adapter
- Redis for local job snapshots
- parallel context workers configured by
  `G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS`, defaulting to `8` in Modal
- OpenRouter concurrency configured by
  `G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY`, defaulting to `30` in
  Modal
- opening-book metadata enabled by default from the CC0 Lichess openings
  dataset; the backend downloads one immutable upstream revision and verifies
  every TSV against its committed SHA-256 digest before using or caching it

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
- `G6EXPLANATION_LICHESS_STUDY_MAX_RESPONSE_BYTES`

Study-chapter import resolves one public chapter through Lichess's chapter PGN
API. It keeps clock comments for timing evidence, removes study comments and
variations from the acquisition response, rejects non-standard or empty PGN,
and uses a cache identity containing both study and chapter ids.

The current local runner is single-process. Redis persists the latest snapshot,
but in-flight work is owned by the Python process that accepted the job.

## Source Rights

Chess.com URL imports, Lichess game and study imports, and manual PGN imports
are accepted only as user-requested analysis inputs. They must not enter global
eval or training manifests unless a future explicit source-rights policy
authorizes that source. Import source metadata always marks these jobs with
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
- missing, empty, oversized, or non-standard Lichess study chapters are rejected
- Lichess timeout, rate-limit, or export unavailability is reported as
  temporary unavailability
- unresolved archive records and invalid PGN are rejected
- pasted PGN must parse and contain at least one mainline move
