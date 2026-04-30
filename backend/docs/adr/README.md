# Architecture Decision Records

ADRs capture decisions that future agents must not rediscover or silently
reverse.

## Location

All ADRs live in `docs/adr/`.

## Numbering

Use monotonically increasing four-digit numbers:

```text
0001-initial-operating-model.md
0002-clean-data-policy.md
0003-stockfish-analysis-budget.md
```

## Status Values

Use one of:

- `Proposed`
- `Accepted`
- `Superseded`
- `Rejected`

Accepted ADRs should not be edited except for typo fixes. If a decision changes,
write a new ADR and mark the old one as superseded.

## ADR Template

```markdown
# ADR NNNN: Title

Date: YYYY-MM-DD
Status: Proposed | Accepted | Superseded | Rejected

## Context

What problem or pressure requires a decision?

## Decision

What are we deciding?

## Consequences

What becomes easier, harder, safer, or more expensive?

## Alternatives Considered

Which credible options were rejected and why?

## Validation

How will we know this decision is working?
```

## When To Write An ADR

Write an ADR when changing:

- data source policy
- training data eligibility
- engine analysis depth/nodes
- Stockfish options
- Maia integration approach
- schema contracts
- verifier pass/fail rules
- model family or serving stack
- use of closed-model judges
- model promotion criteria
- production explanation shape
