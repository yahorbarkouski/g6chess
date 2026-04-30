# Architecture Decision Records

ADRs are short current-state records for durable decisions. They are not a
history log. Keep only decisions that an agent must know before changing product
truth, schema contracts, verifier policy, data rights, model behavior, or core
development standards.

## Current ADRs

- `0001-product-truth-boundary.md`
- `0002-context-contract-and-verification.md`
- `0003-development-standards.md`

## Rules

- Prefer updating `docs/product/` or `docs/development/` for operational detail.
- Add an ADR only when the decision is durable and cross-cutting.
- Keep ADRs under 80 lines.
- Consolidate or delete stale ADRs instead of accumulating logs.
- Use `Status: Accepted`, `Superseded`, or `Rejected` only when useful.
