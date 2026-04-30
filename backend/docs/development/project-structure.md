# Project Structure

## Current Layout

```text
.
  AGENTS.md
  pyproject.toml
  uv.lock
  docs/
    README.md
    product/
    development/
    adr/
  src/
    g6explanation/
      __init__.py
      py.typed
      context_engine/
  tests/
    g6explanation/
      context_engine/
```

## Strategy

- Use `src/` layout so tests import the installed package shape.
- Keep the root package small and stable.
- Put code under the bounded context it serves.
- Mirror tests by package path when it improves navigation.
- Keep product decisions under `docs/product/`.
- Keep implementation workflow, testing, and quality rules under
  `docs/development/`.
- Keep ADRs under `docs/adr/`.
- Add top-level folders only for real implementation boundaries.
- Keep `/Users/yahorbarkouski/g6explanation-frontend` as the companion local
  React visualization app for inspecting context packets from the Python API.
  It should use real-game experiment metadata and request fresh per-ply context
  packets from the API rather than relying on cached/static example packets.

## Production Module Rules

- Use domain names, not generic names.
- Avoid production modules named `utils`, `common`, `helpers`, `models`,
  `providers`, or `heuristics`.
- Name modules after the reason they change, such as `move_quality.py`,
  `candidate_policy.py`, `position_reconstruction.py`, or
  `stockfish_analysis.py`.
- Keep external integrations behind explicit provider protocols and concrete
  adapter modules.

## When To Add A Package

Add a package only when there is a real boundary with a different reason to
change, such as an API transport layer or an LLM generation layer. Do not create
empty packages for future ideas.
