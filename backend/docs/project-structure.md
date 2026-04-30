# Project Structure

This repository uses a conservative Python `src/` layout. The goal is to make
imports, packaging, tests, and future refactors predictable without creating
empty folders for features that do not exist yet.

## Current Structure

```text
.
  AGENTS.md
  pyproject.toml
  uv.lock
  docs/
  src/
    g6explanation/
      __init__.py
      py.typed
      context_engine/
        __init__.py
        board.py
        engine.py
        exceptions.py
        heuristics.py
        models.py
        providers.py
  tests/
    g6explanation/
      context_engine/
        helpers.py
        test_board_reconstruction.py
        test_context_engine.py
        test_stockfish_provider.py
```

## Strategy

- Use `src/` layout so tests import the installed package shape, not accidental
  local modules.
- Keep the root package small. `g6explanation.__init__` should expose stable
  public API objects only.
- Put code under the bounded context it serves. The current bounded context is
  `g6explanation.context_engine`.
- Mirror tests by package path when that improves navigation. For example,
  `src/g6explanation/context_engine/` maps to
  `tests/g6explanation/context_engine/`.
- Keep docs at the repo root under `docs/` because they guide the whole product,
  not one package.
- Add new top-level folders only when real implementation requires them.

## Module Naming Rules

- Use domain names, not generic names.
- Avoid `utils.py`, `common.py`, and `helpers.py` in production code.
- Keep test-only helpers inside the relevant test package.
- Keep external integrations behind provider modules or classes.

## When To Add A New Package

Add a new package only when there is a real boundary with a different reason to
change. Good future examples might include an API transport layer or an LLM
generation layer. Do not create those packages before implementation needs them.
