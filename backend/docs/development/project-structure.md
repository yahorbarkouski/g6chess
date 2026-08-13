# Project Structure

## Current Layout

```text
.
  AGENTS.md
  README.md
  LICENSE
  contracts/
    openapi.json
  frontend/
    src/
    public/
    package.json
  backend/
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
        context_engine/
          candidate_moves/
          signals/
        explanation_generation/
        game_analysis/
        game_imports/
        real_game_evaluation/
        visualization/
    tests/
      g6explanation/
  tools/
    prove.sh
```

## Strategy

- Use `backend/src/` layout so tests import the installed package shape.
- Keep the root package small and stable.
- Put code under the bounded context it serves.
- Mirror tests by package path when it improves navigation.
- Keep product decisions under `docs/product/`.
- Keep implementation workflow, testing, and quality rules under
  `docs/development/`.
- Keep ADRs under `docs/adr/`.
- Add top-level folders only for real implementation boundaries.
- Keep `frontend/` and `backend/` independently runnable. The frontend consumes
  the backend-owned generated API contract and requests fresh analysis data
  rather than relying on cached context packets.

## Production Module Rules

- Use domain names, not generic names.
- Avoid production modules named `utils`, `common`, `helpers`, `models`,
  `providers`, or `heuristics`.
- Name modules after the reason they change, such as
  `signals/quality.py`, `candidate_moves/findability.py`,
  `position_reconstruction.py`, or `stockfish_analysis.py`.
- Use `context_engine/signals/` for deterministic signal policies such as
  quality, significance, and beauty.
- Use `context_engine/candidate_moves/` for candidate assembly, findability,
  practicality, recommendation policy, and key-candidate selection.
- Use `visualization/` only for the local inspection API and real-game
  experiment metadata. It must consume context packets instead of becoming a
  truth-building layer.
- Use `explanation_generation/` for output contracts, baseline rendering,
  explanation verification, provider protocol, concrete model adapters, and the
  `explain_move` orchestration service.
- Use `game_analysis/` for asynchronous full-game job contracts, Redis snapshot
  persistence, real provider setup, and background orchestration over existing
  per-move context and explanation services. It must stay downstream of
  `context_engine` and `explanation_generation`.
- Use `game_imports/` for user-requested acquisition only: URL validation,
  source API calls, PGN parsing, import caching, and source-rights metadata. It
  must hand canonical PGN to `game_analysis` and must not define chess truth,
  explanation policy, or training eligibility beyond explicit source metadata.
- Use `real_game_evaluation/` for curated PGNs, no-mock real-provider eval
  cases, and JSONL evaluation records. It must stay downstream of
  `context_engine` and `explanation_generation`.
- Delete obsolete internal modules during package refactors instead of leaving
  compatibility wrappers. Only documented public exports may preserve backward
  compatibility.
- Keep external integrations behind explicit provider protocols and concrete
  adapter modules.

## When To Add A Package

Add a package only when there is a real boundary with a different reason to
change, such as an API transport layer or an LLM generation layer. Do not create
empty packages for future ideas.
