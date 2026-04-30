# ADR 0003: Development Standards

Date: 2026-04-30
Status: Accepted

## Decision

Use a conservative Python `src/` layout with the current bounded context under
`g6explanation.context_engine`. Keep documentation split by purpose:

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
- Keep tests mirrored to package paths when it improves navigation.
- Do not recreate top-level guide documents under `docs/`.
- Keep ADRs concise; update product/development docs for operational detail.

## Validation

The tree stays small, checks pass, new behavior has tests, and agents can find
current guidance without reading historical decision logs.
