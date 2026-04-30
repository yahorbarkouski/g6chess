# Documentation Index

These documents are the initial operating base for the project. They are meant
to guide implementation, not replace it.

## Start Here

- `../AGENTS.md`: required operating instructions for agents.
- `end-goal.md`: end-state product target for actual implementation.
- `context-engine.md`: how to build the evidence and coach context for the LLM.
- `implementation-quality.md`: code quality and testing bar for implementation.
- `project-structure.md`: Python package and test folder structure strategy.
- `development-flow.md`: local checks, commit checkpoints, and commit messages.
- `product-understanding.md`: product thesis, domain boundaries, and core
  concepts.
- `quality-gates.md`: required checks before code, datasets, explanations, or
  models are promoted.
- `testing-playbook.md`: how to create tests once implementation begins.
- `agent-capabilities.md`: future agent capabilities, checks, and review
  checklists.
- `adr/README.md`: how to record durable decisions.

## Current State

The repository intentionally has no application scaffold yet. The first code
should be created for a concrete vertical slice, not for a guessed architecture.

The first expected implementation slice is:

```text
single PGN/FEN game context
  -> one analyzed move
  -> Stockfish evidence
  -> normalized incident packet
  -> deterministic checks
  -> prompted explanation string
  -> verified API response
```

## Maintenance Rules

- Update docs when implementation changes a contract.
- Add an ADR when a decision should persist beyond the current task.
- Do not add broad placeholder docs. Every document should help implementation,
  testing, review, product quality, or model governance.
- Keep examples small and executable once code exists.

## Local Checks

Use `uv` for local development:

```text
uv sync --all-groups
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
```
