# ADR 0003: Development Standards

Date: 2026-04-30
Status: Accepted

## Decision

Use a conservative Python `src/` layout with the current bounded context under
`g6explanation.context_engine`. The local React visualization app lives in the
companion `/Users/yahorbarkouski/g6explanation-frontend` folder and consumes a narrow
`g6explanation.visualization` HTTP API for real-game experiment metadata and
fresh per-ply verified context packets. Keep
documentation split by purpose:

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
- Keep tests mirrored to package paths when it improves navigation.
- Do not recreate top-level guide documents under `docs/`.
- Keep ADRs concise; update product/development docs for operational detail.

## Validation

The tree stays small, checks pass, new behavior has tests, and agents can find
current guidance without reading historical decision logs.
