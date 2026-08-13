# Quality Gates

Quality gates prevent fluent but unreliable chess explanations.

## Gate 0: Decision

Update the concise ADR set before changing data rights, schema contracts,
Stockfish or Maia configuration, verifier policy, training data, model promotion
criteria, or production explanation behavior.

## Gate 1: Schema

Version and validate externally meaningful objects:

- evidence packet
- LLM context
- explanation output
- verifier result
- dataset manifest
- evaluation result

Schema failures are hard failures.

## Gate 2: Chess Truth

Before explanation, verify:

- valid FEN
- legal played move from `fen_before`
- correct `fen_after`
- side-to-move, player color, and perspective consistency
- separate centipawn and mate representations
- Stockfish version, options, budget, and MultiPV metadata, with depth-limited
  real-engine analysis at depth 16 or deeper
- legal PV replay

## Gate 3: Explanation

Every production explanation must pass:

- schema validation
- deterministic explanation-output verification
- legal move validation for mentioned moves
- line-card id and move-sequence validation against supplied verified line evidence
- best-move and practical-alternative consistency
- no unsupported PV moves
- no unsupported tactic, material, or mate claims
- correct side attribution
- hard alternatives caveated when context marks them hard

Failure blocks raw model output. The generation layer may retry once with
verifier issues, then return a verified deterministic fallback or a controlled
failure.

## Gate 4: Tests And Types

Run the required local checks:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
```

Add tests where the risk lives: parsers, score normalization, move legality,
schemas, verifiers, provider adapters, and prompt/eval regressions.

## Gate 4a: No-Mock Selection

Default tests may use static providers when the behavior under test is
deterministic policy. Run the no-mock gate for the boundary being changed when
real runtime behavior matters:

- Stockfish/Maia provider or real-context changes: run the relevant real
  Stockfish or Maia integration/eval gate at Stockfish depth 16 or deeper.
- Prompt, verifier, model-provider, model-default, real-eval, or model-behavior
  changes: run the real LLM eval gate unless the user explicitly accepts a
  narrower checkpoint.
- Game-analysis orchestration, Redis, provider setup, or polling changes: run
  the no-mock game-analysis API gate.
- Chess.com callback/archive import behavior: run deterministic import tests and
  the opt-in real Chess.com import smoke.

Mocked or static-provider tests can prove policy logic. They cannot prove a
provider-facing change is complete.

## Gate 5: Dataset

A sample can enter training only if source rights allow global training, schemas
pass, deterministic chess verification passes, explanation verification passes,
quality review marks it `accepted`, `LLMContext` is stored, Stockfish depth is
16 or deeper, and all generation/provider/verifier versions are recorded.

## Gate 6: Model Promotion

Promote prompts, fine-tunes, judges, or rewriters only when they match or beat
the current baseline on frozen evals and deterministic verification.

Minimum metrics: schema pass rate, verification pass rate, unsupported-claim
rate, wrong best-move rate, illegal-move rate, rating fit, usefulness, latency,
and cost.

## Gate 7: Product

A feature is product-ready only if it improves the user's understanding of the
requested move, supported better idea, or explanation clarity.

## Optional Maia Evaluation Gate

Run this gate only when work depends on real Maia behavior:

```text
G6EXPLANATION_RUN_MAIA2=1 uv run pytest tests/g6explanation/context_engine/test_real_game_maia_evaluation.py -q
```

It is intentionally outside the default required check set.

## Optional OpenRouter Evaluation Gates

Run these gates only when work depends on actual LLM provider behavior:

```text
G6EXPLANATION_RUN_OPENROUTER=1 uv run pytest tests/g6explanation/explanation_generation/test_real_openrouter_generation.py -q
G6EXPLANATION_RUN_OPENROUTER_STOCKFISH=1 uv run pytest tests/g6explanation/explanation_generation/test_real_openrouter_generation.py -q
G6EXPLANATION_RUN_REAL_LLM_EVAL=1 uv run pytest tests/g6explanation/real_game_evaluation/test_real_explanation_evaluation.py -q -s
```

They require `OPENROUTER_API_KEY` in the environment or `.env`. The real LLM eval
also requires local Stockfish, `maia2`, and local Maia model files. It disables
deterministic fallback, so every passing case used real model output.

Use `G6EXPLANATION_REAL_LLM_EVAL_OUTPUT=.evals/real-explanations.jsonl` to keep
JSONL records for manual review. Use `G6EXPLANATION_REAL_LLM_EVAL_CASES` only for
local debugging; the product gate should run the full curated case list.
Use `G6EXPLANATION_REAL_LLM_EVAL_REPORT=.evals/real-explanations.md` to create
the durable summary report used for manual review and promotion comparisons.
OpenRouter generation in the real eval is batched concurrently after
Stockfish/Maia context building; the default is 30 in-flight requests and can be
overridden with `G6EXPLANATION_REAL_LLM_EVAL_OPENROUTER_CONCURRENCY`.
Manual-review annotations default to
`docs/development/real-explanation-manual-reviews.json` and can be overridden
with `G6EXPLANATION_REAL_LLM_EVAL_MANUAL_REVIEWS`.
Failed, retried, fallback, or surprising records must be reviewed before
changing prompt, verifier, model, or context policy.

## Optional Game Analysis API Gate

Run this gate when changing the async full-game API, Redis snapshot contract,
provider setup, or background orchestration:

```text
G6EXPLANATION_RUN_REAL_GAME_ANALYSIS=1 \
uv run pytest tests/g6explanation/game_analysis/test_game_analysis_redis.py -q -s
```

It requires local Redis, real Stockfish, Maia2 with local model files, and
OpenRouter credentials. It starts a real HTTP job, polls Redis-backed state, and
expects Stockfish depth 16 or deeper, Maia evidence, and verified GPT
explanations for critical moves.

## Optional Game Import Gates

Run the deterministic import tests when changing URL validation, PGN import,
source metadata, cache behavior, or the game-analysis import endpoint:

```text
uv run pytest tests/g6explanation/game_imports -q
```

Run the real Chess.com import smoke when changing live callback/archive
resolution or retry behavior:

```text
G6EXPLANATION_RUN_CHESSCOM_IMPORT=1 \
uv run pytest tests/g6explanation/game_imports/test_chess_com_live_games.py -q -s
```

The real import smoke does not use Stockfish or OpenRouter. It does use
Chess.com's live public surfaces, so failures can reflect network, rate-limit,
or upstream availability issues.

Run the real Lichess import smoke when changing Lichess URL parsing, export
resolution, retry behavior, or source metadata:

```text
G6EXPLANATION_RUN_LICHESS_IMPORT=1 \
uv run pytest tests/g6explanation/game_imports/test_lichess_games.py -q -s
```

The real Lichess smoke does not use Stockfish or OpenRouter. It does use
Lichess's public export API, so failures can reflect network, rate-limit, or
upstream availability issues.

Run the chapter-specific smoke when changing Lichess study acquisition:

```text
G6EXPLANATION_RUN_LICHESS_STUDY_IMPORT=1 \
uv run pytest tests/g6explanation/game_imports/test_lichess_study_chapters.py -q -s
```

## Completion Note

Report checks run, gates passed, skipped gates with reasons, and residual risk.
