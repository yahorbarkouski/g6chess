# ADR 0002: Product End Goal

Date: 2026-04-30
Status: Superseded
Superseded by: ADR 0003

## Context

The project needs a clear implementation destination before code exists. Without
that destination, future work could optimize for the wrong product: a chat layer
over FEN, a friendly Stockfish UI, or a broad training planner disconnected from
verified chess evidence.

The repository already has operating rules, quality gates, and testing guidance.
It now needs a product end-state document that future implementation can be
judged against.

## Decision

The product end goal is documented in `docs/product/end-goal.md`.

The implementation target is a chess improvement system that turns a player's
own games into verified, rating-appropriate explanations, drills, weakness
memory, and training plans.

The core product loop is:

```text
user game
  -> important moments
  -> verified incidents
  -> explanations
  -> drills
  -> weakness memory
  -> training plan
  -> improved future games
```

The smallest first useful slice remains:

```text
input: FEN or PGN position + played move + player rating
output: verified incident packet + structured explanation + simple drill
```

## Consequences

Future implementation should be evaluated by whether it strengthens the product
loop: diagnosis, explanation, training, memory, and measurement.

This decision rules out treating the system as only:

- an LLM chess calculator
- a prose layer over engine output
- a generic puzzle generator
- a training-plan generator without evidence from user games

It also keeps early implementation focused. The first vertical slice should
prove the end-to-end evidence, explanation, verification, and drill contract
before broader application structure is introduced.

## Alternatives Considered

### Engine analysis product

Rejected. It would be useful but not differentiated. The product needs coaching,
drills, memory, and improvement tracking.

### General chess tutor

Rejected as the primary target. The system may tutor, but its advantage comes
from grounding lessons in the user's own verified positions.

### LLM-first chess explainer

Rejected. The LLM should explain verified evidence, not produce chess truth.

## Validation

This decision is working if future features:

- start from verified chess incidents
- produce structured explanations
- pass deterministic verification
- generate actions or drills when appropriate
- preserve recurring weakness memory
- improve frozen eval or human coaching scores
- avoid broad scaffolding before a concrete vertical slice requires it
