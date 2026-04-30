# Development Flow

This document defines how implementation work should move through the repo.

## Default Flow

For every meaningful change:

1. Read the relevant product and quality docs.
2. Inspect the current repo state.
3. Make the smallest coherent change.
4. Add or update tests for changed behavior.
5. Run the required local checks.
6. Review the diff.
7. Commit a checkpoint with a clear message.

The goal is a history of understandable, reversible steps.

## Required Checks Before Commit

Run:

```text
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
```

If formatting is needed, run:

```text
uv run ruff format .
```

Then rerun the full check set.

Do not commit code when required checks are failing unless the commit is
explicitly marked as a work-in-progress checkpoint and the user has approved
that tradeoff.

## Commit Checkpoints

Create a commit after every major coherent change, such as:

- adding a new bounded feature
- completing a refactor
- changing a public contract
- adding a verifier or quality gate
- updating architecture docs or ADRs
- fixing a bug with regression coverage

Do not wait until many unrelated changes pile up. A good checkpoint should be
easy to review and easy to revert.

## Commit Message Format

Use concise conventional-style messages:

```text
type(scope): imperative summary
```

Examples:

```text
feat(context-engine): add candidate practicality scoring
test(context-engine): cover hard engine move caveats
refactor(context-engine): move modules into bounded package
docs(flow): require commit checkpoints after major changes
chore(tooling): add ruff and uv checks
```

Preferred types:

- `feat`: user-facing or product capability
- `fix`: bug fix
- `test`: test-only change
- `refactor`: behavior-preserving code structure change
- `docs`: documentation-only change
- `chore`: tooling, metadata, or maintenance

Use the body when useful:

```text
Why:
- ...

Checks:
- uv run ruff format --check .
- uv run ruff check .
- uv run pytest -q
```

## Atomicity Rules

- Do not mix unrelated changes in one commit.
- Do not commit generated caches or local environment files.
- Do not include broad scaffolding unless the implemented slice requires it.
- Keep docs, tests, and code together when they describe the same behavior.
- If a change affects an ADR-level decision, include the ADR update in the same
  checkpoint or in an immediately adjacent docs commit.

## Before Starting Another Major Change

Check:

```text
git status --short
```

If there are uncommitted changes from a previous task, decide whether they should
be committed, split, or intentionally left uncommitted before continuing.
