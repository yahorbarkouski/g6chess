# Implementation Quality

## Design Rules

- Keep the LLM outside the context engine.
- Make board reconstruction deterministic and testable.
- Keep Stockfish and Maia behind small provider protocols.
- Prefer typed dataclasses, Pydantic contracts, and pure functions over broad
  framework abstractions.
- Add abstractions only for real boundaries, such as provider I/O or stable
  schema contracts.
- Build structured evidence and LLM context before explanation generation.

## Current Package Boundary

Use the Python `src/` layout:

```text
src/g6explanation/
  __init__.py
  py.typed
  context_engine/
    candidate_moves/
    signals/
  explanation_generation/
  real_game_evaluation/
  visualization/

tests/g6explanation/context_engine/
tests/g6explanation/explanation_generation/
tests/g6explanation/real_game_evaluation/
tests/g6explanation/visualization/
```

The implemented bounded contexts are:

- `g6explanation.context_engine`: chess truth, evidence packets, compact LLM
  context, and evidence verification
- `g6explanation.explanation_generation`: verified explanation output, prompt
  construction, model provider I/O, retry behavior, and fallback behavior
- `g6explanation.real_game_evaluation`: no-mock real Stockfish, Maia, and LLM
  eval cases, runner, and JSONL records
- `g6explanation.visualization`: local inspection API over current context
  packets

Keep explanation generation downstream of `context_engine`; keep real-game
evaluation downstream of both.

Do not add a web server, database, model server, user accounts, or broad app
scaffolding until a concrete vertical slice requires it.

## Naming Rules

- Name modules after domain responsibility.
- Do not create production `utils.py`, `common.py`, `helpers.py`, `models.py`,
  `providers.py`, or `heuristics.py`.
- Keep `g6explanation.__init__` limited to stable public exports.
- Keep schema contracts in `contracts.py`; treat JSON shapes as product
  contracts.
- Keep deterministic move-evaluation signals under `context_engine/signals/`.
- Keep candidate assembly, findability, practicality, and recommendation
  policy under `context_engine/candidate_moves/`.
- Keep model provider adapters, prompt assembly, explanation-output schemas,
  baseline rendering, and explanation-text verification outside
  `context_engine`.
- Do not keep compatibility wrapper modules after internal package refactors.
  Update callers to the canonical module path and delete the obsolete module in
  the same change.
- Keep test helpers inside the relevant test package.

## Testing Rules

Every behavior change needs tests at the risk boundary. Prioritize failures
that would make the coach lie:

- wrong side or score perspective
- illegal move accepted
- mate treated as centipawns
- exactly-one-legal-move positions treated as ordinary mistakes instead of
  `forced`
- immediate checkmates treated as neutral alternatives because another mate was
  ranked first
- high-WDL winning moves labeled as ordinary mistakes or blunders
- hard engine move presented as obvious
- Maia probability treated as quality
- unsupported tactic, material, or PV claim
- real model output returned before deterministic explanation verification

Use deterministic static providers for most tests. Use Stockfish only in small
integration tests that can skip when the binary is unavailable, and keep every
depth-limited Stockfish integration/evaluation/visualization context at depth 16
or deeper. Do not reduce real Stockfish depth for speed; replace the test with a
static provider when the expensive engine call is not the behavior under test.
Use the opt-in real Maia gate only for integration/evaluation work that needs
the actual optional runtime. Use the real LLM evaluation gate when prompt,
verifier, or generation changes need proof against actual OpenRouter output.

## Required Checks

Run after substantial changes:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
```

If formatting fails, run:

```text
uv run ruff format .
```

Then rerun the full check set. Report any skipped check and residual risk.

## Dependency Rules

- Runtime dependencies go in `[project].dependencies`.
- Test, lint, and type tooling goes in `[dependency-groups].dev`.
- Do not add dependencies for behavior covered cleanly by the standard library
  or `python-chess`.
- Keep external integrations behind provider protocols so tests can use static
  providers.
