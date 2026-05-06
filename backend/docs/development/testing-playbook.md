# Testing Playbook

## Philosophy

Test the contracts that keep explanations truthful:

```text
board state -> evidence -> LLM context -> explanation -> verifier
```

Prefer small deterministic tests until the core contracts are stable.

## Test First

Prioritize:

- PGN/FEN parsing and move replay
- UCI to SAN conversion
- legal move generation
- Stockfish output parsing
- score normalization from player perspective
- mate score representation
- already-lost forced-mate positions where the engine-best defense is not a
  blunder
- `forced` quality for exactly-one-legal-move positions
- immediate checkmate quality/significance when multiple mates are available
- high-WDL winning moves protected from ordinary mistake/blunder labels
- absolute WDL validation, signed WDL delta validation, and MultiPV parsing
- played-move forced analysis
- evidence, LLM context, explanation, and verifier schemas
- deterministic verifier failures

## Test Data

- Use tiny fixed PGNs and FENs checked into the repo.
- Include White and Black perspective cases.
- Include mate, promotion, castling rights, and en passant.
- Include hard engine moves and human-common bad moves.
- Avoid tests that need internet access.
- Engine-dependent tests should use tiny fixed budgets and skip cleanly when the
  binary is unavailable.

## Local Environment

Use `uv sync` for default development dependencies. Use `uv sync --extra maia`
only when work needs actual Maia behavior.

Keep local secrets and machine-specific paths in `.env`; do not commit it.

Stockfish:

- `StockfishAnalysisProvider` defaults to `stockfish` on `PATH`.
- Stockfish context tests can override the binary with
  `G6EXPLANATION_STOCKFISH_BINARY`.
- Visualization context generation can override the binary with
  `G6_VISUALIZATION_STOCKFISH_BINARY`.
- Opera full-game evaluation can override the binary with
  `G6_OPERA_EVAL_STOCKFISH_BINARY`.
- Every depth-limited real Stockfish context remains depth 16 or deeper.

Maia:

- Model files default to `./maia2_models`.
- Override model location with `MAIA2_MODEL_ROOT`.
- Real Maia tests are opt-in with `G6EXPLANATION_RUN_MAIA2=1`.
- Opera full-game evaluation is opt-in with `G6EXPLANATION_RUN_OPERA_EVAL=1`.

OpenRouter:

- Keep `OPENROUTER_API_KEY` in `.env` or the environment.
- The default model adapter uses `openai/gpt-5.5`.
- Override model or reasoning effort with `G6EXPLANATION_OPENROUTER_MODEL` and
  `G6EXPLANATION_OPENROUTER_REASONING_EFFORT`.
- Tune provider resilience with `G6EXPLANATION_OPENROUTER_TIMEOUT_SECONDS`,
  `G6EXPLANATION_OPENROUTER_MAX_RETRIES`,
  `G6EXPLANATION_OPENROUTER_RETRY_BACKOFF_SECONDS`, and optional
  `G6EXPLANATION_OPENROUTER_MAX_TOKENS`. The provider has no default
  completion-token cap; set the env var only when a specific experiment needs
  one.
- Real provider smoke is opt-in with `G6EXPLANATION_RUN_OPENROUTER=1`.
- Real provider plus Stockfish smoke is opt-in with
  `G6EXPLANATION_RUN_OPENROUTER_STOCKFISH=1`.
- Real Stockfish plus Maia plus OpenRouter eval is opt-in with
  `G6EXPLANATION_RUN_REAL_LLM_EVAL=1`.
- Real eval records can be written with
  `G6EXPLANATION_REAL_LLM_EVAL_OUTPUT=.evals/real-explanations.jsonl`.
- Real eval summary reports can be written with
  `G6EXPLANATION_REAL_LLM_EVAL_REPORT=.evals/real-explanations.md`.
- Real eval manual-review annotations default to
  `docs/development/real-explanation-manual-reviews.json`; override them with
  `G6EXPLANATION_REAL_LLM_EVAL_MANUAL_REVIEWS`.
- Batched real eval builds Stockfish/Maia context packets deterministically,
  then runs OpenRouter generation concurrently. Override the default 30
  in-flight OpenRouter requests with
  `G6EXPLANATION_REAL_LLM_EVAL_OPENROUTER_CONCURRENCY`.

Redis and game analysis:

- Local game-analysis snapshots default to `redis://localhost:6379/0`.
- Override Redis with `G6EXPLANATION_REDIS_URL`.
- The default test suite skips Redis-dependent tests when Redis is unavailable.
- The no-mock endpoint gate is opt-in with
  `G6EXPLANATION_RUN_REAL_GAME_ANALYSIS=1`; it requires Redis, Stockfish,
  Maia2, local Maia model files, and OpenRouter credentials.
- Tune full-game analysis with `G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS`
  and `G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY`.

Game imports:

- Deterministic import tests cover URL validation, PGN parsing, source metadata,
  cache behavior, and the import endpoint without live providers.
- Chess.com live callback/archive behavior is opt-in with
  `G6EXPLANATION_RUN_CHESSCOM_IMPORT=1`; use it only when changing real import
  behavior or validating integration drift.
- Lichess one-game export behavior is opt-in with
  `G6EXPLANATION_RUN_LICHESS_IMPORT=1`; use it only when changing real Lichess
  import behavior or validating integration drift.
- Chess.com, Lichess, and user-pasted PGNs are user-requested analysis inputs
  only. They are not global training data unless a future source-rights policy
  explicitly allows it.

## Unit Tests

Use unit tests for pure logic: score parsing, normalization, classification,
WDL deltas, phase, material, concept rules, schema validators, and verifier
checks.

Each fixed bug leaves a regression test.

## Integration Tests

Use integration tests for external binaries and model adapters:

- Stockfish startup and readiness at depth 16 or deeper
- MultiPV and WDL parsing at depth 16 or deeper
- `searchmoves` forced played-move analysis at depth 16 or deeper
- Maia inference returns legal move probabilities
- Maia stronger-player comparison is unavailable when both ratings map to the
  same public Maia bucket

Keep normal CI budgets small by limiting the number of real-engine fixtures, not
by lowering Stockfish below depth 16. Use static providers when a test does not
need real engine behavior. Deeper stability analysis belongs in offline evals.

Real Maia evaluation is opt-in:

```text
G6EXPLANATION_RUN_MAIA2=1 uv run pytest tests/g6explanation/context_engine/test_real_game_maia_evaluation.py -q
```

Use actual Maia in integration/evaluation tests, not ordinary unit tests. Static
human-likelihood providers remain the default for deterministic policy tests.

Real game-analysis endpoint evaluation is opt-in:

```text
G6EXPLANATION_RUN_REAL_GAME_ANALYSIS=1 \
uv run pytest tests/g6explanation/game_analysis/test_game_analysis_redis.py -q -s
```

It exercises the Redis-backed POST/poll flow with real Stockfish, real Maia, and
real OpenRouter output. Keep it outside default CI because it is intentionally
slow and provider-dependent.

Real Chess.com import smoke is opt-in:

```text
G6EXPLANATION_RUN_CHESSCOM_IMPORT=1 \
uv run pytest tests/g6explanation/game_imports/test_chess_com_live_games.py -q -s
```

It exercises live import resolution without Stockfish or OpenRouter. Treat
network, rate-limit, and upstream failures as integration evidence, not unit-test
failures.

Real Lichess import smoke is opt-in:

```text
G6EXPLANATION_RUN_LICHESS_IMPORT=1 \
uv run pytest tests/g6explanation/game_imports/test_lichess_games.py -q -s
```

It exercises live one-game export without Stockfish or OpenRouter. Treat
network, rate-limit, and upstream failures as integration evidence, not
unit-test failures.

## Golden Tests

Golden tests should assert stable structured fields and supported claims, not
exact free-form explanation wording unless the wording is a product contract.

For heuristic scalar fields, assert labels and threshold behavior instead of
exact floats, except when a pure formula itself is the contract.

## Adversarial Tests

Create fixtures for:

- illegal move mention
- move outside supplied evidence
- mate/centipawn confusion
- unsupported material claim
- wrong side attribution
- unsupported follow-up recommendation
- hard move presented as obvious
- Maia probability treated as quality
- absent tactic tag used as fact
- unsupported attack, bishop-route, or opening-label wording used as fact

## Evaluation Tests

Prompt or model changes require evals:

- frozen gold set
- regression set
- rating ladder set
- concept set
- representative product set

Compare against the current baseline.

## First Explanation Generation Tests

Before calling a real model, add tests for:

- strict rich output schema with visible segments and optional verified line cards
- deterministic baseline explanations from existing context packets
- verifier rejection of unsupported moves, PVs, mate claims, material claims,
  tactic claims, wrong-side language, and recommendation-policy violations
- static provider retry and fallback behavior
- frozen Opera Game and Game of the Century contexts as representative evals
- opt-in real OpenRouter smoke where raw model output must pass deterministic
  verification without fallback
- opt-in no-mock real-game eval over Opera Game, Game of the Century,
  Kasparov-Topalov, Capablanca-Tartakower, synthetic forced-move cases,
  synthetic blunder, high-WDL non-best, castling, en passant, promotion,
  low-time, rating-ladder, Black-perspective, missed-win cases, and Lichess CC0
  puzzle-source and puzzle-solution cases using real Stockfish, real Maia, and
  real OpenRouter
- durable real-eval reporting for pass/fallback/retry rates, failure codes,
  latency, provider metadata, and manual-review categories

## Test Names

Name tests by behavior:

```text
test_normalizes_black_player_eval_from_player_perspective
test_rejects_explanation_with_unprovided_pv_move
test_represents_mate_score_without_centipawn_conversion
```
