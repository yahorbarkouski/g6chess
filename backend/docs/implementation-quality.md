# Implementation Quality

This document defines the code quality bar for the first implementation.

The current product target is one API that explains one move. The implementation
should therefore stay narrow and deterministic.

## Design Rules

- Keep the LLM outside the context engine.
- Make board reconstruction deterministic and testable.
- Keep Stockfish access behind a small provider interface.
- Keep human-likeness probabilities behind a small provider interface.
- Prefer dataclasses and pure functions over framework-heavy abstractions.
- Add an abstraction only when it protects a real boundary, such as external
  engine I/O or optional human probability data.
- Return structured evidence and LLM context before any explanation generation.

## First Package Boundary

Use the standard Python `src/` layout. Keep the root package as a small public
API, and place the current bounded context under `g6explanation.context_engine`.

Current implementation structure:

```text
src/g6explanation/
  __init__.py
  py.typed
  context_engine/
    __init__.py
    candidate_policy.py
    contracts.py
    exceptions.py
    explanation_agenda.py
    maia_likelihood.py
    move_context_builder.py
    move_quality.py
    position_reconstruction.py
    provider_protocols.py
    stockfish_analysis.py

tests/g6explanation/context_engine/
  helpers.py
  test_golden_packet_fixtures.py
  test_maia_likelihood.py
  test_move_context_builder.py
  test_position_reconstruction.py
  test_real_game_significance_examples.py
  test_schema_contracts.py
  test_stockfish_analysis.py
```

The first code implements:

```text
MoveContextRequest
  -> board reconstruction
  -> engine analysis provider
  -> candidate recommendation policy
  -> evidence packet
  -> compact LLM context
```

The first code should not implement:

- a web server
- a database
- model serving
- user accounts
- broad app scaffolding

## Structure Rules

- Use `src/` layout so tests exercise the package import shape.
- Keep domain modules near the bounded context they serve.
- Use specific module names that describe the domain responsibility. Do not add
  production catch-all modules named `models`, `providers`, `heuristics`,
  `utils`, or `common`.
- Mirror test folders to the package path under test when it improves
  navigation, such as `tests/g6explanation/context_engine/` for
  `src/g6explanation/context_engine/`.
- Keep `g6explanation.__init__` focused on stable public exports.
- Do not add empty package folders for future features.
- Do not create production `utils.py`; name modules after domain responsibility.

## Testing Rules

Use static providers for most tests. They make score normalization,
findability, practicality, and context selection deterministic.

Use Stockfish only in a small integration smoke test that can skip when the
binary is unavailable.

Every test should protect a product failure mode:

- wrong side perspective
- illegal move accepted
- hard engine move presented as obvious
- Maia probability treated as quality
- mate scores converted to centipawns
- practical alternative ignored when engine best is only marginally better

## Required Local Checks

Use `uv` as the project runner.

After every major code change, run:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
```

Use `uv run ruff format .` to apply formatting when the format check fails.

Do not mark code work complete until Ruff, mypy, Pyright, and tests pass. If a
check cannot run, record the reason and residual risk in the completion note.

After major coherent changes, follow `docs/development-flow.md` and create a
checkpoint commit with a clear conventional-style message.

## Dependency Rules

- Add runtime dependencies under `[project].dependencies`.
- Add test/lint/dev tooling under `[dependency-groups].dev`.
- Do not add a dependency for behavior that the standard library or
  `python-chess` already covers cleanly.
- Keep external engine/model integrations behind provider interfaces so tests can
  use deterministic static providers.
