# g6 backend

Python services for importing chess games, analyzing every ply, and returning
progressive move reviews to the g6 frontend.

## Packages

Implemented:

- `g6explanation.context_engine`: builds verified evidence packets and compact
  `LLMContext` objects.
- `g6explanation.explanation_generation`: turns verified context into one
  schema-valid, deterministically verified explanation string. The OpenRouter
  adapter defaults to `openai/gpt-5.6-terra` with high reasoning.
- `g6explanation.game_analysis`: submits asynchronous full-game analysis to a
  local thread or Modal worker, stores progressive snapshots in Redis,
  classifies every completed ply, and adds verified explanations for configured
  significance labels.
- `g6explanation.game_imports`: resolves user-requested Chess.com URLs, Lichess
  URLs, or pasted PGN into canonical PGN plus source-rights metadata for game
  analysis.
- `g6explanation.real_game_evaluation`: no-mock real Stockfish, Maia, and
  OpenRouter explanation evals with JSONL records.
- `g6explanation.visualization`: local inspection API for real-game experiment
  metadata and fresh per-ply context packets.

## Technology

| Technology | Purpose in the backend |
| --- | --- |
| Python 3.11+ | Runs the API, analysis pipeline, provider adapters, verification, and evaluation tools. |
| FastAPI | Exposes health, import, analysis-start, and polling endpoints. |
| Pydantic 2 | Validates API and internal contracts and produces the authoritative OpenAPI schema. |
| python-chess | Parses PGN, reconstructs legal positions, converts UCI and SAN, and communicates with Stockfish. |
| Stockfish | Produces objective evaluations and principal variations at depth 16 or deeper. |
| Maia2 0.9 | Estimates move likelihoods by player rating and time control. |
| OpenRouter | Sends structured explanation requests to `openai/gpt-5.6-terra` with high reasoning by default. |
| Redis | Stores expiring analysis snapshots, resolved-import caches, import-to-analysis indexes, and fixed-window rate-limit counters. |
| Modal | Runs a lightweight FastAPI container and separate Stockfish/Maia analysis workers in production. |
| Cloudflare | Forwards the public API hostname to Modal and validates Turnstile tokens for protected imports. |
| OpenAPI | Carries the backend contract into generated TypeScript transport types in the frontend. |
| uv and Hatchling | Resolve locked Python environments and build the Python package. |
| Ruff, mypy, Pyright, and pytest | Enforce formatting, lint, static typing, and behavior. |

Stockfish supplies objective chess evidence. Maia supplies human move
likelihoods. Deterministic classifiers and verifiers turn that evidence into
move labels and validate the explanation returned by the model provider.

## Start here

- Agent operating rules: `AGENTS.md`
- Documentation map: `docs/README.md`
- Product concepts and boundary: `docs/product/product-understanding.md`
- Current next slice: `docs/product/explanation-generation.md`
- Real-world game-analysis integration:
  `docs/development/game-analysis-integration.md`
- No-mock and opt-in provider gates: `docs/development/quality-gates.md`
- Development flow and checks: `docs/development/development-flow.md`

Read the slice-specific docs named in `AGENTS.md` before implementation work.

## Setup

Install project dependencies:

```text
uv sync
```

Install Maia dependencies for real game analysis:

```text
uv sync --extra maia
```

Keep local secrets and machine-specific paths in `.env`. Git ignores this file.

## Local tools

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

- Maia estimates the moves a similarly rated player may choose. Stockfish
  supplies objective move evaluation.
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

Redis state:

- Use the Docker Compose Redis service with the asynchronous game-analysis API.
- Override Redis with `G6EXPLANATION_REDIS_URL`.
- Analysis runs in a local worker thread during development and in a spawned
  Modal worker in production. Redis holds the state shared with polling clients.
- Tune context workers with `G6EXPLANATION_GAME_ANALYSIS_CONTEXT_WORKERS`.
- Tune OpenRouter fan-out with
  `G6EXPLANATION_GAME_ANALYSIS_OPENROUTER_CONCURRENCY`.
- Run the no-mock endpoint gate with
  `G6EXPLANATION_RUN_REAL_GAME_ANALYSIS=1`.

Game imports:

- Chess.com and Lichess URL imports resolve a user-requested game into canonical
  PGN and source-rights metadata for analysis.
- Useful overrides include `G6EXPLANATION_CHESS_COM_USER_AGENT`,
  `G6EXPLANATION_CHESS_COM_TIMEOUT_SECONDS`,
  `G6EXPLANATION_LICHESS_USER_AGENT`,
  `G6EXPLANATION_LICHESS_TIMEOUT_SECONDS`, and
  `G6EXPLANATION_GAME_IMPORT_CACHE_TTL_SECONDS`.
- Run the opt-in live import smoke with `G6EXPLANATION_RUN_CHESSCOM_IMPORT=1`.
- Run the opt-in Lichess import smoke with `G6EXPLANATION_RUN_LICHESS_IMPORT=1`.

Visualization API:

```text
./run.sh
```

The context endpoint needs local Stockfish and Maia setup. Catalog metadata tests
use deterministic fixtures.

## Start local game analysis

Start Redis and the API:

```text
./run.sh
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
running. The start/import response and snapshot include a `game` skeleton with
PGN-derived SAN, UCI, and FEN data, so clients can render the board immediately
before context generation finishes. Completed moves additionally include
quality, significance, beauty, and explanations when they are ready.

## Deploy on Modal

The first public deployment path is documented in
`docs/development/modal-deployment.md`.

It deploys one Modal App with:

- a lightweight FastAPI web endpoint for job start, import, health, and polling
- a spawned worker function for real Stockfish, Maia2, and OpenRouter analysis
- Redis snapshots shared between API, worker, and frontend polling
- a Modal Volume for Maia model files

The deploy workflow is `.github/workflows/deploy-modal.yml`.

## Required checks

Run before checkpoint commits:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
```

Use static providers for cheap deterministic tests. Real Stockfish checks run at
depth 16 or deeper.
