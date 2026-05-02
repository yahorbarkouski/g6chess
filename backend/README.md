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
- `g6explanation.visualization`: local inspection API for real-game experiment
  metadata and fresh per-ply context packets.

Next:

- `g6explanation.explanation_generation`: strict explanation output contracts,
  deterministic baseline rendering, explanation-text verification, static
  provider tests, retry or fallback behavior, real model adapter, and then the
  public `explain_move(...) -> str` wrapper.

Do not move chess truth into the generation layer.

## Start Here

- Agent operating rules: `AGENTS.md`
- Documentation map: `docs/README.md`
- Product concepts and boundary: `docs/product/product-understanding.md`
- Current next slice: `docs/product/explanation-generation.md`
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

Visualization API:

```text
uv run uvicorn g6explanation.visualization.http_api:app --reload
```

The context endpoint needs local Stockfish and Maia setup. Catalog metadata tests
use deterministic fixtures and do not require those optional tools.

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
