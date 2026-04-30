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

tests/g6explanation/context_engine/
```

The current bounded context is `g6explanation.context_engine`.

Do not add a web server, database, model server, user accounts, or broad app
scaffolding until a concrete vertical slice requires it.

## Naming Rules

- Name modules after domain responsibility.
- Do not create production `utils.py`, `common.py`, `helpers.py`, `models.py`,
  `providers.py`, or `heuristics.py`.
- Keep `g6explanation.__init__` limited to stable public exports.
- Keep schema contracts in `contracts.py`; treat JSON shapes as product
  contracts.
- Keep test helpers inside the relevant test package.

## Testing Rules

Every behavior change needs tests at the risk boundary. Prioritize failures
that would make the coach lie:

- wrong side or score perspective
- illegal move accepted
- mate treated as centipawns
- hard engine move presented as obvious
- Maia probability treated as quality
- unsupported tactic, material, or PV claim

Use deterministic static providers for most tests. Use Stockfish only in small
integration tests that can skip when the binary is unavailable. Use the opt-in
real Maia gate from ADR 0010 only for integration/evaluation work that needs the
actual optional runtime.

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
