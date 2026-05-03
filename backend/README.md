# g6explanation

Evidence-grounded context engine for single-move chess explanations.

This product is not an LLM chess calculator. Chess truth comes from deterministic
position reconstruction, Stockfish, optional Maia or clean human-frequency
evidence, rules, and verifiers. The LLM only words one verified explanation.

```text
Stockfish + Maia + rules + verifiers = truth and diagnosis
LLM = wording for one verified move explanation
```

## Current Slice

Implemented:

- `g6explanation.context_engine`: builds verified evidence packets and compact
  `LLMContext` objects.
- `g6explanation.explanation_generation`: turns verified context into one
  schema-valid, deterministically verified explanation string. The OpenRouter
  adapter defaults to `openai/gpt-5.5`.
- `g6explanation.game_analysis`: starts Redis-backed asynchronous full-game
  jobs, classifies every completed ply, and adds verified GPT explanations for
  configured criticality labels.
- `g6explanation.real_game_evaluation`: no-mock real Stockfish, Maia, and
  OpenRouter explanation evals with JSONL records.
- `g6explanation.visualization`: local inspection API for real-game experiment
  metadata and fresh per-ply context packets.

Next:

- review real LLM eval records, harden verifier gaps, and broaden the case list
  where failures reveal missing context or unsupported wording.

Do not move chess truth into the generation layer.

## Start Here

- Agent operating rules: `AGENTS.md`
- Documentation map: `docs/README.md`
- Product concepts and boundary: `docs/product/product-understanding.md`
- Current next slice: `docs/product/explanation-generation.md`
- Real-world game-analysis integration:
  `docs/development/game-analysis-integration.md`
- Development flow and checks: `docs/development/development-flow.md`

Read the slice-specific docs named in `AGENTS.md` before implementation work.

## Setup

Install project dependencies:

```text
uv sync
```

Install optional Maia dependencies only when work needs real Maia behavior:

```text
uv sync --extra maia
```

Keep local secrets and machine-specific paths in `.env`. Do not commit `.env`.

## Local Tools

Stockfish:

- `StockfishAnalysisProvider` defaults to `stockfish` on `PATH`.
- Depth-limited real Stockfish contexts must use depth 16 or deeper.
- Stockfish context tests can override the binary with
  `G6EXPLANATION_STOCKFISH_BINARY`.
- Visualization contexts can override the binary with
  `G6_VISUALIZATION_STOCKFISH_BINARY`.
- Opera evaluation can override the binary with
  `G6_OPERA_EVAL_STOCKFISH_BINARY`.

Maia:

- Maia is optional human-likeness evidence, not move quality.
- Model files default to `./maia2_models`.
- Override model location with `MAIA2_MODEL_ROOT`.
- Real Maia tests are opt-in with `G6EXPLANATION_RUN_MAIA2=1`.
- Opera full-game evaluation is opt-in with `G6EXPLANATION_RUN_OPERA_EVAL=1`.

OpenRouter:

- `OpenRouterCoachModelProvider` reads `OPENROUTER_API_KEY` from the environment
  or `.env`.
- Override the model with `G6EXPLANATION_OPENROUTER_MODEL`.
- Override reasoning effort with `G6EXPLANATION_OPENROUTER_REASONING_EFFORT`.
- Real OpenRouter tests are opt-in with `G6EXPLANATION_RUN_OPENROUTER=1`.
- Real OpenRouter plus Stockfish tests are opt-in with
  `G6EXPLANATION_RUN_OPENROUTER_STOCKFISH=1`.
- Real Stockfish plus Maia plus OpenRouter eval is opt-in with
  `G6EXPLANATION_RUN_REAL_LLM_EVAL=1`.
- Write real eval JSONL records with `G6EXPLANATION_REAL_LLM_EVAL_OUTPUT`.

Redis game analysis:

- Start local Redis before using the async game-analysis API.
- Override Redis with `G6EXPLANATION_REDIS_URL`.
- Tune context workers with `G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS`.
- Tune OpenRouter fan-out with
  `G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY`.
- Run the no-mock endpoint gate with
  `G6EXPLANATION_RUN_REAL_GAME_ANALYSIS=1`.

Visualization API:

```text
uv run uvicorn g6explanation.visualization.http_api:app --reload
```

The context endpoint needs local Stockfish and Maia setup. Catalog metadata tests
use deterministic fixtures and do not require those optional tools.

## Start Local Game Analysis

Start Redis:

```text
redis-server
```

Start the API:

```text
uv run uvicorn g6explanation.visualization.http_api:app --host 127.0.0.1 --port 8001 --reload
```

Submit a game-analysis job:

```text
curl -X POST http://127.0.0.1:8001/api/game-analysis \
  -H 'Content-Type: application/json' \
  -d '{
    "pgn": "[Event \"Example\"]\n\n1. e4 e5 2. Nf3 Nc6 *",
    "player_level": {"kind": "rating", "value": 1500},
    "time_control": "rapid",
    "explain_significance": ["critical"],
    "include_context": false
  }'
```

Poll the returned `analysis_id`:

```text
curl http://127.0.0.1:8001/api/game-analysis/<analysis_id>
```

The polling response is a partial `GameAnalysisSnapshot` while the job is
running. Completed moves already include SAN, UCI, quality, significance,
beauty, and explanations when they are ready.

## Required Checks

Run before checkpoint commits:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
```

Use static providers for cheap deterministic tests. Do not lower real Stockfish
depth below 16 for speed.
