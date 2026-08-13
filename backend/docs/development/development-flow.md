# Development Flow

## Default Flow

For every meaningful change:

1. Inspect the repo with `rg --files`, `find`, and targeted reads.
2. Read the relevant product, development, and ADR docs.
3. Identify the narrowest product slice, contract, provider boundary, and
   required gate.
4. Make the smallest coherent change.
5. Add or update tests for changed behavior.
6. Run required checks and any no-mock gate required by the changed boundary.
7. Review the diff.
8. Commit a checkpoint with a conventional-style message.

## Required Checks Before Commit

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pyright
uv run pytest -q
```

Do not commit failing code unless the user explicitly approves a work-in-progress
checkpoint.

## Commit Messages

Use:

```text
type(scope): imperative summary
```

Examples:

```text
feat(context-engine): add candidate practicality scoring
test(context-engine): cover hard engine move caveats
docs(flow): clarify checkpoint rules
```

Preferred types: `feat`, `fix`, `test`, `refactor`, `docs`, `chore`.

## Atomicity

- Do not mix unrelated changes.
- Do not commit generated caches or local environment files.
- Keep docs, tests, and code together when they describe the same behavior.
- Update the concise ADR set when the change affects durable architecture, data,
  schema, verifier, or model behavior.

## Before Starting Another Major Change

Run:

```text
git status --short
```

Handle existing uncommitted changes before layering on new work.
