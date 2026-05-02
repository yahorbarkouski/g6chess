# Agent Operating Guide

This repository is for a chess explanation engine. The product is not an LLM
that calculates chess. The product is an evidence-grounded coach:

```text
Stockfish + Maia + rules + verifiers = truth and diagnosis
LLM = coach-quality wording for one verified move explanation
```

Every agent must preserve that separation.

## Required Reading

Before making implementation changes, read this startup set:

1. `docs/product/product-understanding.md`
2. `docs/product/end-goal.md`
3. `docs/development/development-flow.md`
4. `docs/development/quality-gates.md`
5. `docs/adr/README.md` and the ADRs that govern the change

Then read the slice-specific docs before touching that slice:

- Context engine or chess truth: `docs/product/context-engine.md`,
  `docs/development/implementation-quality.md`,
  `docs/development/project-structure.md`,
  `docs/development/testing-playbook.md`,
  `docs/development/agent-capabilities.md`, and
  `docs/adr/0002-context-contract-and-verification.md`.
- Explanation generation or model behavior:
  `docs/product/explanation-generation.md`,
  `docs/product/prompt-guidelines.md`, `docs/product/context-engine.md`,
  `docs/development/testing-playbook.md`, and
  `docs/adr/0001-product-truth-boundary.md` plus
  `docs/adr/0002-context-contract-and-verification.md`.
- Visualization or local inspection API:
  `docs/development/project-structure.md`,
  `docs/development/implementation-quality.md`,
  `docs/development/testing-playbook.md`, and
  `docs/adr/0003-development-standards.md`.
- Documentation-only changes: `docs/README.md`,
  `docs/development/development-flow.md`,
  `docs/development/project-structure.md`, `docs/adr/README.md`, and any
  product or development doc being changed.

For cross-cutting, architectural, schema, verifier, data, model, or uncertain
changes, read the full product, development, and ADR set in `docs/README.md`.

If a change affects architecture, data rights, model behavior, schema contracts,
or verification policy, update the concise ADR set before or with the
implementation.

## Working Principles

- Do not scaffold application code before there is a concrete implementation
  need.
- Prefer vertical slices over broad empty structure.
- Keep chess truth outside the LLM.
- Treat structured schemas as product contracts, not implementation details.
- Make illegal states hard to represent.
- Name production modules and classes after concrete domain responsibilities.
  Avoid catch-all names such as `heuristics`, `models`, `providers`, `utils`,
  and `common`.
- Split a module when it has multiple reasons to change, especially when chess
  truth, recommendation policy, provider I/O, and LLM-facing agenda construction
  start living together.
- Do not keep compatibility wrapper modules after internal package refactors.
  Update imports to the canonical module path and delete the obsolete module in
  the same change. Compatibility belongs only to documented public exports.
- Add deterministic checks before relying on model judgment.
- Keep source/data licenses explicit and traceable.
- Never train global models on user-imported games unless rights are explicit.
- Never train global models on Chess.com-derived data without a license.
- Do not let generated explanations enter training data until they pass schema,
  deterministic chess verification, and quality review gates.

## Current Product Slice

The context engine is implemented as the current truth-building layer. It
produces verified evidence packets and compact `LLMContext` objects, with
Stockfish depth 16 or deeper required for real engine-backed contexts.

The next product slice is explanation generation. Build it downstream of
`g6explanation.context_engine`, not inside the context engine. The first
generation implementation must add strict explanation output contracts, a
deterministic baseline renderer, an explanation-text verifier, static provider
tests, retry or fallback behavior, and only then a real model adapter.

## Context Intake Protocol

When starting work:

1. Inspect the actual repo state with `rg --files`, `find`, and targeted reads.
2. Read the startup and slice-specific docs and ADRs.
3. Identify the narrowest product slice being changed.
4. Find existing tests and quality checks before editing.
5. State assumptions if the codebase does not yet encode a decision.
6. Check `git status --short` and avoid mixing unrelated changes.

When reviewing or modifying code:

1. Verify side-to-move and evaluation perspective carefully.
2. Check legality of all chess moves that cross a module boundary.
3. Preserve version metadata for Stockfish, Maia, schemas, and prompts.
4. Add tests for every bug fix and every new behavior contract.
5. Run the smallest relevant checks first, then broader checks if risk warrants it.

## Chess Correctness Rules

- Normalize engine scores from the analyzed player's point of view at the system
  boundary where incidents are created.
- Use Stockfish depth 16 or deeper for every real Stockfish-backed context,
  integration test, evaluation, and visualization packet. Do not lower depth for
  speed; use static providers for cheap deterministic tests instead.
- Represent mate scores separately from centipawns.
- Store UCI moves for computation and SAN only for display/explanation.
- Verify that all model-mentioned moves are legal or present in supplied engine
  evidence.
- Do not allow an explanation string to introduce PV moves that were not supplied in
  the incident packet.
- Do not accept vague statements like "wins material" unless a deterministic
  material or line check supports them.

## Model Behavior Rules

The public API returns one explanation string. Internally, generation should be
validated through a strict response contract, such as a schema with a single
`explanation` string field plus private verification metadata.

Model provider adapters may return raw schema-shaped output only to the
generation layer. They must not modify Stockfish, Maia, candidate, quality,
significance, beauty, or agenda decisions from the context engine.

The coach model may:

- summarize what changed
- explain the human reason for a mistake
- adapt wording to rating level
- state the move quality clearly
- explain the better move or idea when supported by evidence

The coach model may not:

- invent chess lines
- override Stockfish, Maia, tablebases, or legal-move checks
- make unsupported tactic claims
- silently change the best move
- convert mate claims into centipawn claims

## Quality Bar

A change is not complete until:

- Relevant tests pass.
- `uv run ruff format --check .` passes, or formatting is applied and rechecked.
- `uv run ruff check .` passes.
- `uv run mypy src tests` passes.
- `uv run pyright` passes.
- `uv run pytest -q` passes.
- New behavior has tests or a written reason tests are not applicable.
- Schemas, ADRs, or docs are updated when contracts change.
- Verification failures are treated as blockers, not warnings.
- Any skipped checks are reported with the reason and residual risk.

After every major code change, run the full local check set:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
```

If a check cannot be run, report why and what risk remains.

## Commit Checkpoints

After every major coherent change, create a Git checkpoint commit with a clear
conventional-style message, after the required checks pass.

Examples:

```text
feat(context-engine): add candidate practicality scoring
refactor(context-engine): mirror tests by package path
docs(flow): require commit checkpoints after major changes
```

Keep commits atomic. Do not mix unrelated changes, generated caches, or local
environment files. If checks cannot run or fail, do not commit unless the user
explicitly approves a work-in-progress checkpoint.

## Documentation Discipline

Documentation should be operational. Avoid speculative documents that do not help
future implementation, review, testing, or product decisions.

Put product scope, model behavior, context, and prompt guidance under
`docs/product/`. Put workflow, testing, quality, and structure guidance under
`docs/development/`. Do not recreate top-level guide documents under `docs/`.

ADRs are concise current-state decision records, not historical logs. Keep them
small, consolidate when possible, and put operational detail in product or
development docs.

## Nested AGENTS.md Policy

Add nested `AGENTS.md` files only when a real implementation area has local rules
that differ from this root guide. Good examples include engine workers, model
evaluation pipelines, verifier logic, or API surfaces.

Do not create nested agent files for empty directories or speculative packages.
