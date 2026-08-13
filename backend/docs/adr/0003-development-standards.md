# ADR 0003: Development Standards

Date: 2026-04-30
Status: Accepted

## Decision

Use a conservative Python `src/` layout. Current implementation boundaries are
`g6explanation.context_engine` for chess truth,
`g6explanation.explanation_generation` for verified model wording,
`g6explanation.game_analysis` for Redis-backed asynchronous full-game
orchestration, `g6explanation.game_imports` for user-requested PGN acquisition,
`g6explanation.real_game_evaluation` for no-mock provider evals,
`g6explanation.api` for public HTTP composition, and
`g6explanation.visualization` for local inspection data. The React application
lives at `frontend/` in the same repository and consumes the generated public
API contract. Keep documentation split by purpose:

- `docs/product/` for product scope, context, model behavior, and prompts
- `docs/development/` for workflow, quality, testing, and structure
- `docs/adr/` for only durable, high-signal decisions

## Rules

- Do not scaffold packages or services before a concrete vertical slice needs
  them.
- Name production modules after domain responsibility.
- Do not create production catch-all modules named `utils`, `common`,
  `helpers`, `models`, `providers`, or `heuristics`.
- Keep external integrations behind provider protocols.
- Keep deterministic move signals under `context_engine/signals/` and candidate
  move policy under `context_engine/candidate_moves/`.
- Do not keep compatibility wrappers for internal package refactors; update
  imports to canonical paths and remove obsolete modules in the same change.
- Keep visualization API transport separate from context-engine truth building.
- Do not cache visualization context output in the catalog; manual inspection
  should exercise the current production context-building path on each context
  request.
- Keep `explanation_generation` downstream of `context_engine`; model adapters
  may produce raw schema-shaped output only for deterministic verification.
- Keep `game_analysis` downstream of context and generation. It may parallelize
  per-ply work and persist polling snapshots, but it must not define chess-truth
  or explanation-verification policy.
- Keep `game_imports` as an acquisition boundary. It may validate URLs, call
  source APIs, parse PGN, cache resolved imports, and attach source-rights
  metadata, but it must hand canonical PGN to `game_analysis` for all chess
  analysis.
- Keep `real_game_evaluation` downstream of context and generation; it may call
  real providers and record JSONL eval results but must not define chess truth.
- Keep tests mirrored to package paths when it improves navigation.
- Do not recreate top-level guide documents under `docs/`.
- Keep ADRs concise; update product/development docs for operational detail.

## Validation

The tree stays small, checks pass, new behavior has tests, and agents can find
current guidance without reading historical decision logs.
